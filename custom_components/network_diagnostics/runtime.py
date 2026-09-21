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
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.event import (
    async_call_later,
    async_track_state_change_event,
    async_track_time_interval,
)
from homeassistant.helpers.storage import Store

from .baseline import BaselineAssessment, BaselineTracker
from .classifier import DiagnosisResult, MONITORING_INCOMPLETE, classify
from .const import (
    BAD_STATUS,
    BEHAVIOR_DEFAULTS,
    CONF_BASELINE_MIN_DELTA_MS,
    CONF_BASELINE_MIN_SAMPLES,
    CONF_BASELINE_RATIO,
    CONF_BASELINE_WINDOW_MINUTES,
    CONF_DEGRADATION_SECONDS,
    CONF_FAILURE_CONFIRM_SECONDS,
    CONF_INCIDENT_RETENTION,
    CONF_RECOVERY_CONFIRM_SECONDS,
    CONF_STALE_SECONDS,
    GOOD_STATUS,
    ISSUE_CONFIGURATION_REQUIRED,
    ISSUE_CONFIGURED_MONITOR_MISSING,
    ISSUE_INVALID_CONFIGURATION,
    ISSUE_STALE_PROVIDER,
    ROLE_DISPLAY_NAMES,
    ROLE_GATEWAY,
    ROLE_MESH_NODE,
    ROLE_NETWORK_NODE,
    STORAGE_KEY_PREFIX,
    STORAGE_VERSION,
    UNUSABLE_STATUSES,
    VERSION,
)
from .discovery import DiscoveryResult, configured_bindings
from .models import IncidentRecord, IncidentTransition, RuntimeSnapshot
from .observations import Observation, ObservationSet
from .topology import topology_payload
from .validation import coverage_capabilities, coverage_gaps, validate_bindings

_LOGGER = logging.getLogger(__name__)

UpdateListener = Callable[[], None]
IncidentListener = Callable[[str, dict[str, Any]], None]


class _IncidentStore(Store[dict[str, Any]]):
    """Persist compact derived incidents, never raw monitor time series."""

    async def _async_migrate_func(
        self,
        old_major_version: int,
        old_minor_version: int,
        old_data: dict[str, Any],
    ) -> dict[str, Any]:
        if old_major_version < 3:
            return {"incidents": [], "active_incident": None, "last_manual_analysis": None}
        if old_major_version == STORAGE_VERSION:
            return old_data
        raise NotImplementedError


class NetworkDiagnosticsRuntime:
    """Observe existing Kuma entities and derive diagnoses/incidents locally."""

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
        self._update_listeners: list[UpdateListener] = []
        self._incident_listeners: list[IncidentListener] = []
        self._unsub_state: Callable[[], None] | None = None
        self._unsub_deferred: Callable[[], None] | None = None
        self._unsub_incident_confirmation: Callable[[], None] | None = None
        self._unsub_watchdog: Callable[[], None] | None = None
        self._analysis_lock = asyncio.Lock()
        self._closed = False
        self._subscribed_entities: tuple[str, ...] = ()
        self._baseline = BaselineTracker(
            window_minutes=int(self.option(CONF_BASELINE_WINDOW_MINUTES)),
            min_samples=int(self.option(CONF_BASELINE_MIN_SAMPLES)),
            ratio_threshold=float(self.option(CONF_BASELINE_RATIO)),
            min_delta_ms=float(self.option(CONF_BASELINE_MIN_DELTA_MS)),
            degradation_seconds=int(self.option(CONF_DEGRADATION_SECONDS)),
        )

    def option(self, key: str) -> Any:
        return self.entry.options.get(key, BEHAVIOR_DEFAULTS[key])

    async def async_start(self) -> None:
        stored = await self._store.async_load() or {}
        for item in stored.get("incidents", []):
            try:
                self.incidents.append(IncidentRecord.from_dict(item))
            except (KeyError, TypeError, ValueError) as err:
                _LOGGER.warning(
                    "Skipping malformed stored Network Diagnostics incident: %s", err
                )
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
        self.last_manual_analysis = stored.get("last_manual_analysis")
        self._rediscover()
        self._subscribe_sources()
        self._start_watchdog()
        await self.async_analyze()

    async def async_stop(self) -> None:
        self._closed = True
        for name in (
            "_unsub_state",
            "_unsub_deferred",
            "_unsub_incident_confirmation",
            "_unsub_watchdog",
        ):
            unsub = getattr(self, name)
            if unsub:
                unsub()
                setattr(self, name, None)
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
            (
                item.monitor_id,
                item.name,
                item.status_entity,
                item.response_entity,
                item.role,
                item.parent_id,
                item.service,
            )
            for item in self.discovery.bindings
        }
        self.discovery = configured_bindings(self.hass, dict(self.entry.data))
        warnings, blockers = validate_bindings(self.discovery.bindings)
        capabilities = coverage_capabilities(self.discovery.bindings)
        self.discovery.coverage_capabilities = capabilities
        self.discovery.coverage_gaps.extend(warnings)
        self.discovery.coverage_gaps.extend(coverage_gaps(capabilities))
        self.discovery.required_gaps.extend(blockers)
        self.discovery.coverage_gaps = list(dict.fromkeys(self.discovery.coverage_gaps))
        self.discovery.required_gaps = list(dict.fromkeys(self.discovery.required_gaps))
        self.discovery.limitations = [
            "Adaptive latency baselines are intentionally RAM-only and relearn after a Home Assistant restart.",
            "Kuma Tags are optional setup hints. Confirmed role/topology assignments are stored in this integration's config entry.",
            "Network Diagnostics can only diagnose properties represented by configured monitors; vendor-specific link/backhaul quality is not inferred from reachability alone.",
        ]
        valid_ids = {item.monitor_id for item in self.discovery.bindings}
        self._baseline.remove_unknown(valid_ids)
        self._sync_configuration_repairs()
        current = {
            (
                item.monitor_id,
                item.name,
                item.status_entity,
                item.response_entity,
                item.role,
                item.parent_id,
                item.service,
            )
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
                    *binding.heartbeat_entities,
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
        if self._unsub_watchdog:
            self._unsub_watchdog()

        @callback
        def _watchdog(_: datetime) -> None:
            if self._closed:
                return
            if self._rediscover():
                self._subscribe_sources()
            self.hass.async_create_task(self.async_analyze())

        self._unsub_watchdog = async_track_time_interval(
            self.hass, _watchdog, timedelta(seconds=60)
        )

    @callback
    def _handle_source_event(self, event: Event) -> None:
        self._schedule_analysis()

    @staticmethod
    def _reported_at(state: Any) -> datetime | None:
        if state is None:
            return None
        value = getattr(state, "last_reported", None) or getattr(
            state, "last_updated", None
        )
        if value is None:
            return None
        if value.tzinfo is None:
            value = value.replace(tzinfo=UTC)
        return value

    def _binding_freshness(
        self, binding: Any, now: datetime
    ) -> tuple[bool, float | None, datetime | None]:
        reports: list[datetime] = []
        for entity_id in binding.heartbeat_entities or (
            binding.response_entity,
            binding.status_entity,
        ):
            if not entity_id:
                continue
            state = self.hass.states.get(entity_id)
            reported = self._reported_at(state)
            if reported:
                reports.append(reported)
        if not reports:
            return False, None, None
        newest = max(reports)
        age = max(0.0, (now - newest).total_seconds())
        return age <= int(self.option(CONF_STALE_SECONDS)), age, newest

    def _response_value(
        self, entity_id: str | None
    ) -> tuple[float | None, datetime | None]:
        if not entity_id:
            return None, None
        state = self.hass.states.get(entity_id)
        if state is None:
            return None, None
        try:
            value = float(state.state)
        except (TypeError, ValueError):
            return None, self._reported_at(state)
        return value, self._reported_at(state)

    def _collect_observations(
        self, now: datetime
    ) -> tuple[ObservationSet, dict[str, BaselineAssessment]]:
        result = ObservationSet(
            coverage_gaps=list(self.discovery.coverage_gaps),
            required_gaps=list(self.discovery.required_gaps),
            unassigned_monitors=list(self.discovery.unassigned_monitors),
        )
        degraded: dict[str, BaselineAssessment] = {}
        ages: list[float] = []

        for binding in self.discovery.bindings:
            state = self.hass.states.get(binding.status_entity)
            fresh, age, heartbeat_at = self._binding_freshness(binding, now)
            if age is not None:
                ages.append(age)
            if state is None:
                result.monitoring_gaps.append(
                    f"{binding.name} status entity is unavailable"
                )
                raw = "missing"
                status = None
            else:
                raw = str(state.state).strip().lower()
                if not fresh:
                    status = None
                    result.monitoring_gaps.append(
                        f"{binding.name} has not received a fresh Kuma update within {int(self.option(CONF_STALE_SECONDS))} seconds"
                    )
                elif raw == GOOD_STATUS:
                    status = True
                elif raw == BAD_STATUS:
                    status = False
                elif raw in UNUSABLE_STATUSES:
                    status = None
                    result.monitoring_gaps.append(
                        f"{binding.name} status is {raw or 'empty'}"
                    )
                else:
                    status = None
                    result.monitoring_gaps.append(
                        f"{binding.name} has unrecognized Kuma status {state.state!r}"
                    )

            response_ms, response_at = self._response_value(binding.response_entity)
            sample_at = response_at or heartbeat_at or now
            assessment = self._baseline.update(
                binding.monitor_id,
                observed_at=sample_at,
                response_ms=response_ms if fresh and status is True else None,
            )
            if binding.role in {ROLE_GATEWAY, ROLE_NETWORK_NODE, ROLE_MESH_NODE}:
                degraded[binding.monitor_id] = assessment
            result.observations.append(
                Observation(
                    binding=binding,
                    status=status,
                    raw_status=raw,
                    response_ms=response_ms,
                    fresh=fresh,
                    age_seconds=age,
                    baseline_state=assessment.state,
                    baseline_median_ms=assessment.median_ms,
                    baseline_mad_ms=assessment.mad_ms,
                    baseline_ratio=assessment.ratio,
                    baseline_sample_count=assessment.sample_count,
                )
            )

        result.provider_fresh = bool(result.observations) and not any(
            item.fresh is False for item in result.observations
        )
        result.provider_age_seconds = max(ages) if ages else None
        return result, degraded

    def _observation_dict(self, item: Observation) -> dict[str, Any]:
        parent_names = {
            binding.monitor_id: binding.name for binding in self.discovery.bindings
        }
        return {
            "name": item.binding.name,
            "role": item.binding.role,
            "role_name": ROLE_DISPLAY_NAMES.get(item.binding.role, item.binding.role),
            "parent_name": parent_names.get(item.binding.parent_id),
            "service": item.binding.service,
            "monitor_type": item.binding.monitor_type,
            "status": item.status,
            "raw_status": item.raw_status,
            "response_ms": item.response_ms,
            "fresh": item.fresh,
            "age_seconds": round(item.age_seconds, 1)
            if item.age_seconds is not None
            else None,
            "baseline_state": item.baseline_state,
            "baseline_median_ms": round(item.baseline_median_ms, 1)
            if item.baseline_median_ms is not None
            else None,
            "baseline_mad_ms": round(item.baseline_mad_ms, 1)
            if item.baseline_mad_ms is not None
            else None,
            "baseline_ratio": round(item.baseline_ratio, 2)
            if item.baseline_ratio is not None
            else None,
            "baseline_sample_count": item.baseline_sample_count,
        }

    async def async_analyze(self, *, manual: bool = False) -> RuntimeSnapshot:
        async with self._analysis_lock:
            now = datetime.now(UTC)
            if manual and self._rediscover():
                self._subscribe_sources()
            observations, degraded = self._collect_observations(now)
            result = classify(observations, degraded_nodes=degraded)
            snapshot = RuntimeSnapshot(
                at=now.isoformat(),
                diagnosis=result,
                observations=[
                    self._observation_dict(item) for item in observations.observations
                ],
                discovery=self.discovery.as_dict(),
                topology=topology_payload(self.discovery.bindings),
                freshness={
                    "fresh": observations.provider_fresh,
                    "max_age_seconds": round(observations.provider_age_seconds, 1)
                    if observations.provider_age_seconds is not None
                    else None,
                    "stale_monitors": [
                        item.binding.name
                        for item in observations.observations
                        if not item.fresh
                    ],
                },
                manual=manual,
            )
            self.current = snapshot
            if manual:
                self.last_manual_analysis = snapshot.at
            self._sync_runtime_repairs(observations)
            await self._process_incident(now, snapshot, observations)
            self._notify_update()
            if manual:
                await self._async_save()
            return snapshot

    def _sync_configuration_repairs(self) -> None:
        self._set_issue(
            ISSUE_CONFIGURATION_REQUIRED,
            bool(not self.discovery.configured),
            severity=ir.IssueSeverity.WARNING,
            translation_key="configuration_required",
        )
        self._set_issue(
            ISSUE_CONFIGURED_MONITOR_MISSING,
            bool(self.discovery.missing_configured_monitors),
            severity=ir.IssueSeverity.WARNING,
            translation_key="configured_monitor_missing",
            placeholders={
                "count": str(len(self.discovery.missing_configured_monitors))
            },
        )
        invalid = [
            item
            for item in self.discovery.required_gaps
            if self.discovery.configured
            and "no longer available" not in item.casefold()
        ]
        self._set_issue(
            ISSUE_INVALID_CONFIGURATION,
            bool(invalid),
            severity=ir.IssueSeverity.ERROR,
            translation_key="invalid_configuration",
            placeholders={
                "details": "; ".join(invalid[:3]) or "unknown configuration error"
            },
        )

    def _sync_runtime_repairs(self, observations: ObservationSet) -> None:
        self._set_issue(
            ISSUE_STALE_PROVIDER,
            bool(self.discovery.bindings and not observations.provider_fresh),
            severity=ir.IssueSeverity.WARNING,
            translation_key="stale_provider",
        )

    def _set_issue(
        self,
        issue_id: str,
        active: bool,
        *,
        severity: ir.IssueSeverity,
        translation_key: str,
        placeholders: dict[str, str] | None = None,
    ) -> None:
        if active:
            ir.async_create_issue(
                self.hass,
                "network_diagnostics",
                issue_id,
                is_fixable=False,
                severity=severity,
                translation_key=translation_key,
                translation_placeholders=placeholders,
            )
        else:
            ir.async_delete_issue(self.hass, "network_diagnostics", issue_id)

    def _fingerprint(
        self, result: DiagnosisResult, observations: ObservationSet
    ) -> str:
        domains = sorted(cause.domain for cause in result.root_causes) or [
            result.diagnosis
        ]
        failed_ids = sorted(
            item.binding.monitor_id
            for item in observations.observations
            if item.status is False
        )
        raw = "|".join([*domains, *failed_ids])
        return hashlib.sha256(raw.encode()).hexdigest()[:16]

    async def _process_incident(
        self, now: datetime, snapshot: RuntimeSnapshot, observations: ObservationSet
    ) -> None:
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
            if (
                now - self._pending_recovery_since
            ).total_seconds() >= recovery_confirm:
                await self._close_incident(now, snapshot)
            return

        # Missing/stale/invalid evidence is a monitoring/configuration problem,
        # not a new network outage. If a real incident was already open, keep it
        # open and record evidence loss rather than declaring false recovery.
        if result.monitoring_problem:
            self._pending_abnormal = None
            self._pending_recovery_since = None
            if (
                self.active_incident is not None
                and self.active_incident.current_diagnosis != result.diagnosis
            ):
                await self._update_incident(now, snapshot, observations)
            return

        self._pending_recovery_since = None
        if self.active_incident is None:
            failure_confirm = int(self.option(CONF_FAILURE_CONFIRM_SECONDS))
            if failure_confirm <= 0:
                await self._start_incident(now, snapshot, observations)
                return
            if (
                self._pending_abnormal is None
                or self._pending_abnormal[0] != result.diagnosis
            ):
                self._pending_abnormal = (result.diagnosis, now)
                self._schedule_incident_confirmation(failure_confirm)
                return
            if (now - self._pending_abnormal[1]).total_seconds() >= failure_confirm:
                await self._start_incident(now, snapshot, observations)
            return

        self._pending_abnormal = None
        if self.active_incident.current_diagnosis != result.diagnosis:
            await self._update_incident(now, snapshot, observations)

    async def _start_incident(
        self, now: datetime, snapshot: RuntimeSnapshot, observations: ObservationSet
    ) -> None:
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
            start_snapshot=snapshot.incident_snapshot(),
            latest_snapshot=snapshot.incident_snapshot(),
            fingerprint=self._fingerprint(result, observations),
        )
        self._pending_abnormal = None
        await self._async_save()
        self._emit_incident("started", self.active_incident)

    async def _update_incident(
        self, now: datetime, snapshot: RuntimeSnapshot, observations: ObservationSet
    ) -> None:
        assert self.active_incident is not None
        result = snapshot.diagnosis
        self.active_incident.current_diagnosis = result.diagnosis
        self.active_incident.confidence = result.confidence
        self.active_incident.summary = result.summary
        self.active_incident.latest_snapshot = snapshot.incident_snapshot()
        if result.diagnosis != MONITORING_INCOMPLETE:
            self.active_incident.fingerprint = self._fingerprint(result, observations)
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

    async def _close_incident(
        self, now: datetime, snapshot: RuntimeSnapshot
    ) -> None:
        assert self.active_incident is not None
        started = datetime.fromisoformat(self.active_incident.started_at)
        self.active_incident.ended_at = now.isoformat()
        self.active_incident.duration_seconds = max(
            0, int((now - started).total_seconds())
        )
        self.active_incident.recovered_snapshot = snapshot.incident_snapshot()
        self.active_incident.latest_snapshot = snapshot.incident_snapshot()
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

    async def _async_save(self) -> None:
        await self._store.async_save(
            {
                "incidents": [item.as_dict() for item in self.incidents],
                "active_incident": self.active_incident.as_dict()
                if self.active_incident
                else None,
                "last_manual_analysis": self.last_manual_analysis,
            }
        )

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
            1
            if self.active_incident and self.active_incident.fingerprint == target
            else 0
        )

    @staticmethod
    def _panel_incident(incident: IncidentRecord) -> dict[str, Any]:
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
