"""Event-driven runtime for Network Diagnostics."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
import hashlib
import logging
from typing import Any
from uuid import uuid4

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.helpers.event import async_call_later, async_track_state_change_event, async_track_time_interval
from homeassistant.helpers.storage import Store

from .classifier import DiagnosisResult, HEALTHY, MONITORING_INCOMPLETE, classify
from .const import (
    BAD_STATUS,
    BEHAVIOR_DEFAULTS,
    CONF_FAILURE_CONFIRM_SECONDS,
    CONF_INCIDENT_RETENTION,
    CONF_MESH_DEGRADATION_SECONDS,
    CONF_MESH_LATENCY_MS,
    CONF_RECOVERY_CONFIRM_SECONDS,
    CONF_STALE_SECONDS,
    DEFAULT_FAILURE_CONFIRM_SECONDS,
    DEFAULT_INCIDENT_RETENTION,
    DEFAULT_MESH_DEGRADATION_SECONDS,
    DEFAULT_MESH_LATENCY_MS,
    DEFAULT_RECOVERY_CONFIRM_SECONDS,
    DEFAULT_STALE_SECONDS,
    GOOD_STATUS,
    ROLE_GATEWAY,
    ROLE_MESH,
    STORAGE_KEY_PREFIX,
    STORAGE_VERSION,
    UNUSABLE_STATUSES,
    VERSION,
)
from .discovery import DiscoveryResult, discover_kuma_monitors
from .models import IncidentRecord, IncidentTransition, RuntimeSnapshot
from .observations import Observation, ObservationSet

_LOGGER = logging.getLogger(__name__)

UpdateListener = Callable[[], None]
IncidentListener = Callable[[str, dict[str, Any]], None]


class _IncidentStore(Store[dict[str, Any]]):
    """Persistent incident store with an explicit v0.1 -> v0.2 migration.

    The v0.2 storage payload intentionally remains backwards compatible with
    the first package layout. Home Assistant's ``Store`` helper refuses a
    major-version mismatch unless a migration function is supplied, so keep
    the migration explicit instead of silently abandoning existing incidents.
    """

    async def _async_migrate_func(
        self,
        old_major_version: int,
        old_minor_version: int,
        old_data: dict[str, Any],
    ) -> dict[str, Any]:
        if old_major_version == 1:
            return old_data
        if old_major_version == STORAGE_VERSION:
            # Future minor-version changes may remain data-compatible.
            return old_data
        raise NotImplementedError


class NetworkDiagnosticsRuntime:
    """Observe Uptime Kuma entities and turn them into diagnoses/incidents."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        self.hass = hass
        self.entry = entry
        self._store: Store[dict[str, Any]] = _IncidentStore(
            hass,
            STORAGE_VERSION,
            f"{STORAGE_KEY_PREFIX}.{entry.entry_id}",
            atomic_writes=True,
            serialize_in_event_loop=False,
        )
        self.current: RuntimeSnapshot | None = None
        self.discovery = DiscoveryResult()
        self.incidents: list[IncidentRecord] = []
        self.active_incident: IncidentRecord | None = None
        self.last_manual_analysis: str | None = None
        self._pending_abnormal: tuple[str, datetime] | None = None
        self._pending_recovery_since: datetime | None = None
        self._mesh_high_since: dict[str, datetime | None] = {}
        self._update_listeners: list[UpdateListener] = []
        self._incident_listeners: list[IncidentListener] = []
        self._unsub_state: Callable[[], None] | None = None
        self._unsub_deferred: Callable[[], None] | None = None
        self._unsub_incident_confirmation: Callable[[], None] | None = None
        self._unsub_degradation_confirmation: Callable[[], None] | None = None
        self._unsub_watchdog: Callable[[], None] | None = None
        self._kuma_coordinators: dict[str, tuple[Any, Callable[[], None]]] = {}
        self._provider_heartbeat: dict[str, datetime] = {}
        self._provider_success: dict[str, bool] = {}
        self._analysis_lock = asyncio.Lock()
        self._closed = False
        self._subscribed_entities: tuple[str, ...] = ()

    def option(self, key: str) -> Any:
        if key in self.entry.options:
            return self.entry.options[key]
        return BEHAVIOR_DEFAULTS[key]

    async def async_start(self) -> None:
        stored = await self._store.async_load() or {}
        self.incidents = []
        for item in stored.get("incidents", []):
            try:
                self.incidents.append(IncidentRecord.from_dict(item))
            except (KeyError, TypeError, ValueError) as err:
                _LOGGER.warning("Skipping malformed stored Network Diagnostics incident: %s", err)
        retention = max(10, int(self.option(CONF_INCIDENT_RETENTION)))
        self.incidents = self.incidents[-retention:]
        active = stored.get("active_incident")
        if active:
            try:
                self.active_incident = IncidentRecord.from_dict(active)
            except (KeyError, TypeError, ValueError) as err:
                _LOGGER.warning(
                    "Ignoring malformed active Network Diagnostics incident: %s", err
                )
                self.active_incident = None
        self.last_manual_analysis = stored.get("last_manual_analysis")
        self._refresh_kuma_coordinator_subscriptions()
        self._rediscover()
        self._subscribe_sources()
        self._start_watchdog()
        await self.async_analyze()

    async def async_stop(self) -> None:
        self._closed = True
        for unsub_name in (
            "_unsub_state",
            "_unsub_deferred",
            "_unsub_incident_confirmation",
            "_unsub_degradation_confirmation",
            "_unsub_watchdog",
        ):
            unsub = getattr(self, unsub_name)
            if unsub:
                unsub()
                setattr(self, unsub_name, None)
        for _entry_id, (_coordinator, unsub) in tuple(self._kuma_coordinators.items()):
            unsub()
        self._kuma_coordinators.clear()
        await self._async_save()

    @callback
    def add_update_listener(self, listener: UpdateListener) -> Callable[[], None]:
        self._update_listeners.append(listener)

        @callback
        def _remove() -> None:
            if listener in self._update_listeners:
                self._update_listeners.remove(listener)

        return _remove

    @callback
    def add_incident_listener(self, listener: IncidentListener) -> Callable[[], None]:
        self._incident_listeners.append(listener)

        @callback
        def _remove() -> None:
            if listener in self._incident_listeners:
                self._incident_listeners.remove(listener)

        return _remove

    def _refresh_kuma_coordinator_subscriptions(self) -> None:
        """Listen to the official Uptime Kuma coordinators without polling them.

        DataUpdateCoordinator notifies listeners when a refresh succeeds or when
        its success state changes. This gives us an authoritative provider
        heartbeat even when a monitor is DOWN and its response-time sensor is
        unknown, and even when an unchanged status entity has an old HA timestamp.
        """
        entries = {
            entry.entry_id: entry
            for entry in self.hass.config_entries.async_entries("uptime_kuma")
        }
        for entry_id in set(self._kuma_coordinators) - set(entries):
            _coordinator, unsub = self._kuma_coordinators.pop(entry_id)
            unsub()
            self._provider_heartbeat.pop(entry_id, None)
            self._provider_success.pop(entry_id, None)

        now = datetime.now(UTC)
        for entry_id, entry in entries.items():
            coordinator = getattr(entry, "runtime_data", None)
            add_listener = getattr(coordinator, "async_add_listener", None)
            if not callable(add_listener):
                continue
            existing = self._kuma_coordinators.get(entry_id)
            if existing and existing[0] is coordinator:
                continue
            if existing:
                existing[1]()

            self._provider_success[entry_id] = bool(
                getattr(coordinator, "last_update_success", False)
            )
            if self._provider_success[entry_id]:
                # We may attach between coordinator refreshes. Treat the currently
                # loaded successful snapshot as fresh now; if refreshes stop, this
                # naturally expires at stale_seconds.
                self._provider_heartbeat[entry_id] = now

            @callback
            def _coordinator_updated(
                entry_id: str = entry_id, coordinator: Any = coordinator
            ) -> None:
                if self._closed:
                    return
                self._provider_success[entry_id] = bool(
                    getattr(coordinator, "last_update_success", False)
                )
                self._provider_heartbeat[entry_id] = datetime.now(UTC)
                # Monitor additions/removals and renames arrive through the same
                # coordinator. Defer briefly so HA's own entities finish updating.
                if self._rediscover():
                    self._subscribe_sources()
                self._schedule_analysis()

            unsub = add_listener(_coordinator_updated)
            self._kuma_coordinators[entry_id] = (coordinator, unsub)

    @callback
    def _schedule_analysis(self) -> None:
        if self._closed or self._unsub_deferred:
            return

        @callback
        def _run(_: datetime) -> None:
            self._unsub_deferred = None
            self.hass.async_create_task(self.async_analyze())

        self._unsub_deferred = async_call_later(self.hass, 0.35, _run)

    def _rediscover(self) -> bool:
        previous = {
            (item.monitor_id, item.status_entity, item.response_entity, item.role, item.group)
            for item in self.discovery.bindings
        }
        self.discovery = discover_kuma_monitors(self.hass)
        current = {
            (item.monitor_id, item.status_entity, item.response_entity, item.role, item.group)
            for item in self.discovery.bindings
        }
        return current != previous

    def _subscribe_sources(self) -> None:
        entity_ids = sorted(
            {
                entity_id
                for binding in self.discovery.bindings
                for entity_id in (
                    binding.status_entity,
                    binding.response_entity,
                    binding.monitor_type_entity,
                    binding.target_entity,
                )
                if entity_id
            }
        )
        signature = tuple(entity_ids)
        if signature == self._subscribed_entities:
            return
        if self._unsub_state:
            self._unsub_state()
            self._unsub_state = None
        self._subscribed_entities = signature
        if entity_ids:
            self._unsub_state = async_track_state_change_event(
                self.hass, entity_ids, self._handle_source_event
            )

    def _start_watchdog(self) -> None:
        """Re-analyze locally and discover newly-created Kuma monitors."""
        if self._unsub_watchdog:
            self._unsub_watchdog()
        interval_seconds = max(30, min(60, int(self.option(CONF_STALE_SECONDS)) // 2))

        @callback
        def _watchdog(_: datetime) -> None:
            if self._closed:
                return
            self._refresh_kuma_coordinator_subscriptions()
            if self._rediscover():
                self._subscribe_sources()
            self.hass.async_create_task(self.async_analyze())

        self._unsub_watchdog = async_track_time_interval(
            self.hass, _watchdog, timedelta(seconds=interval_seconds)
        )

    @callback
    def _handle_source_event(self, event: Event) -> None:
        # Fallback and UI-state path. The coordinator listener above is the
        # provider heartbeat; state events merely ensure prompt recomputation.
        self._schedule_analysis()

    async def async_analyze(self, *, manual: bool = False) -> RuntimeSnapshot:
        async with self._analysis_lock:
            now = datetime.now(UTC)
            if manual:
                self._refresh_kuma_coordinator_subscriptions()
                if self._rediscover():
                    self._subscribe_sources()
            observations = self._collect_observations(now)
            degraded_mesh = self._update_mesh_degradation(now, observations)
            result = classify(observations, degraded_mesh=degraded_mesh)
            snapshot = RuntimeSnapshot(
                at=now.isoformat(),
                diagnosis=result,
                observations=[self._observation_dict(item) for item in observations.observations],
                discovery=self.discovery.as_dict(),
                provider_freshness={
                    "fresh": observations.provider_fresh,
                    "max_age_seconds": observations.provider_age_seconds,
                    "entries": self._provider_freshness_payload(now),
                },
                manual=manual,
            )
            self.current = snapshot
            if manual:
                self.last_manual_analysis = snapshot.at
            await self._process_incident(now, snapshot)
            self._notify_update()
            if manual:
                await self._async_save()
            return snapshot

    def _provider_entry_state(
        self, entry_id: str | None, now: datetime
    ) -> tuple[bool, float | None, bool | None]:
        if not entry_id:
            return False, None, None
        heartbeat = self._provider_heartbeat.get(entry_id)
        age = max(0.0, (now - heartbeat).total_seconds()) if heartbeat else None
        success = self._provider_success.get(entry_id)
        fresh = (
            success is True
            and age is not None
            and age <= int(self.option(CONF_STALE_SECONDS))
        )
        return fresh, age, success

    def _provider_freshness_payload(self, now: datetime) -> dict[str, Any]:
        payload: dict[str, Any] = {}
        used_entries = {
            binding.source_entry_id
            for binding in self.discovery.bindings
            if binding.source_entry_id
        }
        for entry_id in sorted(used_entries):
            fresh, age, success = self._provider_entry_state(entry_id, now)
            payload[entry_id] = {
                "fresh": fresh,
                "age_seconds": round(age, 1) if age is not None else None,
                "last_update_success": success,
            }
        return payload

    def _collect_observations(self, now: datetime) -> ObservationSet:
        result = ObservationSet(
            coverage_gaps=list(self.discovery.coverage_gaps),
            required_gaps=list(self.discovery.required_gaps),
            unassigned_monitors=list(self.discovery.unassigned_monitors),
            metadata={"profile": self.discovery.profile},
        )
        provider_states: dict[str, tuple[bool, float | None, bool | None]] = {}
        used_entries = {
            binding.source_entry_id
            for binding in self.discovery.bindings
            if binding.source_entry_id
        }
        for entry_id in used_entries:
            provider_states[entry_id] = self._provider_entry_state(entry_id, now)
            fresh, age, success = provider_states[entry_id]
            if not fresh:
                if success is False:
                    detail = "last Uptime Kuma coordinator refresh failed"
                elif age is None:
                    detail = "no Uptime Kuma coordinator heartbeat has been observed"
                else:
                    detail = f"Uptime Kuma coordinator heartbeat is stale ({age:.0f}s old)"
                result.monitoring_gaps.append(f"Uptime Kuma source {entry_id}: {detail}")

        for binding in self.discovery.bindings:
            provider_fresh, provider_age, _success = provider_states.get(
                binding.source_entry_id or "", (False, None, None)
            )
            state = self.hass.states.get(binding.status_entity)
            if state is None:
                result.monitoring_gaps.append(
                    f"{binding.label} status entity {binding.status_entity} does not exist"
                )
                result.observations.append(
                    Observation(binding, None, "missing", None, False, provider_age)
                )
                continue

            raw = str(state.state).strip().lower()
            if not provider_fresh:
                status: bool | None = None
            elif raw == GOOD_STATUS:
                status = True
            elif raw == BAD_STATUS:
                status = False
            elif raw in UNUSABLE_STATUSES:
                status = None
                result.monitoring_gaps.append(
                    f"{binding.label} status is {raw or 'empty'} despite a fresh Kuma feed"
                )
            else:
                status = None
                result.monitoring_gaps.append(
                    f"{binding.label} has unrecognized Kuma status {state.state!r}"
                )

            # Response time is supporting evidence only. A DOWN Kuma monitor often
            # has an unknown/unavailable response time; that must not invalidate a
            # fresh, authoritative DOWN status.
            response_ms: float | None = None
            if binding.response_entity:
                response_state = self.hass.states.get(binding.response_entity)
                if response_state is not None:
                    try:
                        response_ms = float(response_state.state)
                    except (TypeError, ValueError):
                        response_ms = None

            result.observations.append(
                Observation(
                    binding,
                    status,
                    raw,
                    response_ms,
                    provider_fresh,
                    provider_age,
                )
            )

        if self.discovery.disabled_status_monitors:
            result.monitoring_gaps.extend(
                f"{name} status entity is disabled in Home Assistant"
                for name in self.discovery.disabled_status_monitors
            )

        if used_entries:
            states = [provider_states[entry_id] for entry_id in used_entries]
            result.provider_fresh = all(item[0] for item in states)
            ages = [item[1] for item in states if item[1] is not None]
            result.provider_age_seconds = round(max(ages), 1) if ages else None
        else:
            result.provider_fresh = False
            result.provider_age_seconds = None

        return result

    def _update_mesh_degradation(self, now: datetime, obs: ObservationSet) -> set[str]:
        threshold = float(self.option(CONF_MESH_LATENCY_MS))
        duration = int(self.option(CONF_MESH_DEGRADATION_SECONDS))
        gateway_values = [
            item.response_ms
            for item in obs.by_role(ROLE_GATEWAY)
            if item.response_ms is not None and item.status is True
        ]
        gateway_latency = min(gateway_values) if gateway_values else None
        active_labels = {item.binding.label for item in obs.by_role(ROLE_MESH)}
        for stale_label in set(self._mesh_high_since) - active_labels:
            self._mesh_high_since.pop(stale_label, None)

        degraded: set[str] = set()
        for item in obs.by_role(ROLE_MESH):
            label = item.binding.label
            value = item.response_ms
            high = (
                item.status is True
                and value is not None
                and value >= threshold
                and (
                    gateway_latency is None
                    or value >= max(threshold, gateway_latency + 15.0)
                )
            )
            if high:
                since = self._mesh_high_since.get(label)
                if since is None:
                    self._mesh_high_since[label] = now
                    self._schedule_degradation_confirmation(duration)
                elif (now - since).total_seconds() >= duration:
                    degraded.add(label)
            else:
                self._mesh_high_since[label] = None
        return degraded

    @staticmethod
    def _observation_dict(item: Observation) -> dict[str, Any]:
        return {
            "monitor_id": item.binding.monitor_id,
            "name": item.binding.name,
            "label": item.binding.label,
            "role": item.binding.role,
            "group": item.binding.group,
            "role_source": item.binding.role_source,
            "monitor_type": item.binding.monitor_type,
            "target": item.binding.target,
            "source_entry_id": item.binding.source_entry_id,
            "status": item.status,
            "raw_status": item.raw_status,
            "response_ms": item.response_ms,
            "fresh": item.fresh,
            "age_seconds": item.age_seconds,
            "status_entity": item.binding.status_entity,
            "response_entity": item.binding.response_entity,
        }

    @staticmethod
    def _fingerprint(result: DiagnosisResult) -> str:
        parts = [result.diagnosis, *sorted(result.affected_components)]
        return hashlib.sha256("|".join(parts).encode()).hexdigest()[:16]

    async def _process_incident(self, now: datetime, snapshot: RuntimeSnapshot) -> None:
        result = snapshot.diagnosis
        if result.healthy:
            self._pending_abnormal = None
            if self.active_incident is None:
                self._pending_recovery_since = None
                return
            recovery_confirm = int(self.option(CONF_RECOVERY_CONFIRM_SECONDS))
            if recovery_confirm <= 0:
                await self._close_incident(now, snapshot)
                return
            if self._pending_recovery_since is None:
                self._pending_recovery_since = now
                self._schedule_incident_confirmation(recovery_confirm)
                return
            if (now - self._pending_recovery_since).total_seconds() >= int(
                self.option(CONF_RECOVERY_CONFIRM_SECONDS)
            ):
                await self._close_incident(now, snapshot)
            return

        # Loss of monitoring is evidence loss, not network recovery. Keep any active
        # incident open and record the transition if the diagnosis changes.
        self._pending_recovery_since = None
        if self.active_incident is None:
            failure_confirm = int(self.option(CONF_FAILURE_CONFIRM_SECONDS))
            if failure_confirm <= 0:
                await self._start_incident(now, snapshot)
                return
            if self._pending_abnormal is None or self._pending_abnormal[0] != result.diagnosis:
                self._pending_abnormal = (result.diagnosis, now)
                self._schedule_incident_confirmation(failure_confirm)
                return
            if (now - self._pending_abnormal[1]).total_seconds() >= int(
                self.option(CONF_FAILURE_CONFIRM_SECONDS)
            ):
                await self._start_incident(now, snapshot)
            return

        self._pending_abnormal = None
        if self.active_incident.current_diagnosis != result.diagnosis:
            await self._update_incident(now, snapshot)

    async def _start_incident(self, now: datetime, snapshot: RuntimeSnapshot) -> None:
        result = snapshot.diagnosis
        transition = IncidentTransition(
            at=now.isoformat(),
            diagnosis=result.diagnosis,
            confidence=result.confidence,
            summary=result.summary,
            evidence=list(result.evidence),
        )
        self.active_incident = IncidentRecord(
            id=uuid4().hex,
            started_at=now.isoformat(),
            initial_diagnosis=result.diagnosis,
            current_diagnosis=result.diagnosis,
            confidence=result.confidence,
            summary=result.summary,
            transitions=[transition],
            start_snapshot=snapshot.as_dict(),
            latest_snapshot=snapshot.as_dict(),
            fingerprint=self._fingerprint(result),
        )
        self._pending_abnormal = None
        await self._async_save()
        self._emit_incident("started", self.active_incident)

    async def _update_incident(self, now: datetime, snapshot: RuntimeSnapshot) -> None:
        assert self.active_incident is not None
        result = snapshot.diagnosis
        self.active_incident.current_diagnosis = result.diagnosis
        self.active_incident.confidence = result.confidence
        self.active_incident.summary = result.summary
        self.active_incident.latest_snapshot = snapshot.as_dict()
        if result.diagnosis != MONITORING_INCOMPLETE:
            self.active_incident.fingerprint = self._fingerprint(result)
        self.active_incident.transitions.append(
            IncidentTransition(
                at=now.isoformat(),
                diagnosis=result.diagnosis,
                confidence=result.confidence,
                summary=result.summary,
                evidence=list(result.evidence),
            )
        )
        if len(self.active_incident.transitions) > 100:
            self.active_incident.transitions = [
                self.active_incident.transitions[0],
                *self.active_incident.transitions[-99:],
            ]
        await self._async_save()
        self._emit_incident("updated", self.active_incident)

    async def _close_incident(self, now: datetime, snapshot: RuntimeSnapshot) -> None:
        assert self.active_incident is not None
        started = datetime.fromisoformat(self.active_incident.started_at)
        self.active_incident.ended_at = now.isoformat()
        self.active_incident.duration_seconds = max(
            0, int((now - started).total_seconds())
        )
        self.active_incident.recovered_snapshot = snapshot.as_dict()
        self.active_incident.latest_snapshot = snapshot.as_dict()
        closed = self.active_incident
        self.incidents.append(closed)
        retention = max(10, int(self.option(CONF_INCIDENT_RETENTION)))
        self.incidents = self.incidents[-retention:]
        self.active_incident = None
        self._pending_recovery_since = None
        await self._async_save()
        self._emit_incident("recovered", closed)

    def _schedule_incident_confirmation(self, seconds: int) -> None:
        if self._unsub_incident_confirmation:
            self._unsub_incident_confirmation()

        @callback
        def _run(_: datetime) -> None:
            self._unsub_incident_confirmation = None
            if not self._closed:
                self.hass.async_create_task(self.async_analyze())

        self._unsub_incident_confirmation = async_call_later(
            self.hass, max(1, seconds) + 0.1, _run
        )

    def _schedule_degradation_confirmation(self, seconds: int) -> None:
        if self._unsub_degradation_confirmation:
            self._unsub_degradation_confirmation()

        @callback
        def _run(_: datetime) -> None:
            self._unsub_degradation_confirmation = None
            if not self._closed:
                self.hass.async_create_task(self.async_analyze())

        self._unsub_degradation_confirmation = async_call_later(
            self.hass, max(1, seconds) + 0.1, _run
        )

    async def _async_save(self) -> None:
        data = {
            "incidents": [item.as_dict() for item in self.incidents],
            "active_incident": self.active_incident.as_dict()
            if self.active_incident
            else None,
            "last_manual_analysis": self.last_manual_analysis,
        }
        await self._store.async_save(data)

    @callback
    def _notify_update(self) -> None:
        for listener in tuple(self._update_listeners):
            listener()

    @callback
    def _emit_incident(self, kind: str, incident: IncidentRecord) -> None:
        payload = {
            "incident_id": incident.id,
            "diagnosis": incident.current_diagnosis,
            "confidence": incident.confidence,
            "summary": incident.summary,
            "started_at": incident.started_at,
            "ended_at": incident.ended_at,
            "duration_seconds": incident.duration_seconds,
            "fingerprint": incident.fingerprint,
        }
        for listener in tuple(self._incident_listeners):
            listener(kind, payload)
        self._notify_update()

    @property
    def incidents_24h(self) -> int:
        cutoff = datetime.now(UTC) - timedelta(hours=24)
        count = sum(
            datetime.fromisoformat(item.started_at) >= cutoff for item in self.incidents
        )
        if (
            self.active_incident
            and datetime.fromisoformat(self.active_incident.started_at) >= cutoff
        ):
            count += 1
        return count

    def similar_incident_count(self, fingerprint: str | None = None) -> int:
        target = fingerprint or (
            self.active_incident.fingerprint if self.active_incident else ""
        )
        if not target:
            return 0
        return sum(item.fingerprint == target for item in self.incidents) + (
            1 if self.active_incident and self.active_incident.fingerprint == target else 0
        )

    @staticmethod
    def _panel_incident(incident: IncidentRecord) -> dict[str, Any]:
        """Return the compact incident shape needed by the frontend.

        Full source snapshots stay in persistent storage/downloadable diagnostics;
        sending them for every sidebar refresh would needlessly inflate the HA
        WebSocket payload.
        """
        return {
            "id": incident.id,
            "started_at": incident.started_at,
            "ended_at": incident.ended_at,
            "duration_seconds": incident.duration_seconds,
            "initial_diagnosis": incident.initial_diagnosis,
            "current_diagnosis": incident.current_diagnosis,
            "confidence": incident.confidence,
            "summary": incident.summary,
            "fingerprint": incident.fingerprint,
            "transitions": [
                {
                    "at": item.at,
                    "diagnosis": item.diagnosis,
                    "confidence": item.confidence,
                    "summary": item.summary,
                    "evidence": list(item.evidence),
                }
                for item in incident.transitions
            ],
        }

    def panel_payload(self) -> dict[str, Any]:
        return {
            "version": VERSION,
            "current": self.current.as_dict() if self.current else None,
            "active_incident": self._panel_incident(self.active_incident)
            if self.active_incident
            else None,
            "recent_incidents": [
                self._panel_incident(item) for item in self.incidents[-25:]
            ][::-1],
            "incidents_24h": self.incidents_24h,
            "similar_incident_count": self.similar_incident_count(),
            "last_manual_analysis": self.last_manual_analysis,
            "discovery": self.discovery.as_dict(),
        }
