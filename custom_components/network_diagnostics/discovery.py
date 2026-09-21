"""Discover Uptime Kuma monitors through Home Assistant public registries/states."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from .const import (
    CONF_MONITORS,
    CONF_PARENT,
    CONF_ROLE,
    CONF_SERVICE,
    ROLE_DISPLAY_NAMES,
    ROLE_IGNORE,
)
from .kuma_ids import split_kuma_unique_id
from .observations import MonitorBinding
from .tag_hints import TagHint, parse_tag_hint
from .targets import select_raw_target, target_fingerprint, target_ip_version

UPTIME_KUMA_DOMAIN = "uptime_kuma"


@dataclass(frozen=True, slots=True)
class KumaMonitor:
    """One monitor visible through the official Home Assistant integration."""

    monitor_id: str
    monitor_key: str
    name: str
    status_entity: str
    response_entity: str | None
    heartbeat_entities: tuple[str, ...]
    monitor_type_entity: str | None
    tags_entity: str | None
    source_entry_id: str
    monitor_type: str | None
    target_fingerprint: str | None
    target_ip_version: int | None
    tag_hint: TagHint


@dataclass(slots=True)
class DiscoveryResult:
    bindings: list[MonitorBinding] = field(default_factory=list)
    available_monitors: list[KumaMonitor] = field(default_factory=list)
    unassigned_monitors: list[str] = field(default_factory=list)
    missing_configured_monitors: list[str] = field(default_factory=list)
    coverage_gaps: list[str] = field(default_factory=list)
    required_gaps: list[str] = field(default_factory=list)
    limitations: list[str] = field(default_factory=list)
    coverage_capabilities: dict[str, bool] = field(default_factory=dict)
    configured: bool = False

    def as_dict(self) -> dict[str, Any]:
        """Return a privacy-reduced UI representation; targets are never included."""
        parent_names = {item.monitor_id: item.name for item in self.bindings}
        return {
            "configured": self.configured,
            "bindings": [
                {
                    "monitor_id": item.monitor_id,
                    "name": item.name,
                    "role": item.role,
                    "role_name": ROLE_DISPLAY_NAMES.get(item.role, item.role),
                    "parent_id": item.parent_id,
                    "parent_name": parent_names.get(item.parent_id),
                    "service": item.service,
                    "monitor_type": item.monitor_type,
                }
                for item in self.bindings
            ],
            "available_monitor_count": len(self.available_monitors),
            "unassigned_monitors": list(self.unassigned_monitors),
            "missing_configured_monitors": list(self.missing_configured_monitors),
            "coverage_gaps": list(self.coverage_gaps),
            "required_gaps": list(self.required_gaps),
            "limitations": list(self.limitations),
            "coverage_capabilities": dict(self.coverage_capabilities),
        }


def _state_value(hass: HomeAssistant, entity: Any | None) -> str | None:
    if entity is None:
        return None
    state = hass.states.get(entity.entity_id)
    if state is None:
        return None
    value = str(state.state).strip()
    if value.casefold() in {"unknown", "unavailable", "none", ""}:
        return None
    return value


def _state_attributes(hass: HomeAssistant, entity: Any | None) -> dict[str, Any] | None:
    if entity is None:
        return None
    state = hass.states.get(entity.entity_id)
    return dict(state.attributes) if state is not None else None


def discover_kuma_inventory(hass: HomeAssistant) -> list[KumaMonitor]:
    """Enumerate Kuma monitors using only public HA registry/state interfaces."""
    entity_registry = er.async_get(hass)
    device_registry = dr.async_get(hass)
    config_entries = hass.config_entries.async_entries(UPTIME_KUMA_DOMAIN)

    by_monitor: dict[tuple[str, str], dict[str, Any]] = defaultdict(dict)
    device_for_monitor: dict[tuple[str, str], str | None] = {}

    for config_entry in config_entries:
        for entity in er.async_entries_for_config_entry(entity_registry, config_entry.entry_id):
            if entity.platform != UPTIME_KUMA_DOMAIN:
                continue
            parsed_id = split_kuma_unique_id(entity.unique_id, config_entry.entry_id)
            if parsed_id is None:
                continue
            monitor_id, suffix = parsed_id
            key = (config_entry.entry_id, monitor_id)
            by_monitor[key][suffix] = entity
            device_for_monitor[key] = entity.device_id

    monitors: list[KumaMonitor] = []
    for (entry_id, monitor_id), entities in sorted(by_monitor.items()):
        status = entities.get("status")
        if status is None:
            continue
        device_id = device_for_monitor[(entry_id, monitor_id)]
        device = device_registry.async_get(device_id) if device_id else None
        # DeviceEntry.name is integration-provided; name_by_user is intentionally not
        # used, so the canonical human name remains the Uptime Kuma monitor name.
        name = str((device.name if device else None) or status.original_name or status.entity_id)
        monitor_key = f"{entry_id}:{monitor_id}"
        response = entities.get("response_time")
        monitor_type_entity = entities.get("type")
        tags_entity = entities.get("tags")
        url_entity = entities.get("url")
        hostname_entity = entities.get("hostname")
        port_entity = entities.get("port")
        raw_target = select_raw_target(
            url=_state_value(hass, url_entity),
            hostname=_state_value(hass, hostname_entity),
            port=_state_value(hass, port_entity),
        )
        monitors.append(
            KumaMonitor(
                monitor_id=monitor_id,
                monitor_key=monitor_key,
                name=name,
                status_entity=status.entity_id,
                response_entity=response.entity_id if response else None,
                heartbeat_entities=tuple(
                    entity.entity_id
                    for key in ("response_time", "uptime_1d", "avg_response_time_1d", "status")
                    if (entity := entities.get(key)) is not None
                ),
                monitor_type_entity=(
                    monitor_type_entity.entity_id if monitor_type_entity else None
                ),
                tags_entity=tags_entity.entity_id if tags_entity else None,
                source_entry_id=entry_id,
                monitor_type=_state_value(hass, monitor_type_entity),
                target_fingerprint=target_fingerprint(raw_target),
                target_ip_version=target_ip_version(raw_target),
                tag_hint=parse_tag_hint(_state_attributes(hass, tags_entity)),
            )
        )
    return monitors


def configured_bindings(
    hass: HomeAssistant, entry_data: dict[str, Any]
) -> DiscoveryResult:
    """Resolve stored role/topology configuration against current Kuma inventory."""
    inventory = discover_kuma_inventory(hass)
    by_key = {item.monitor_key: item for item in inventory}
    config = entry_data.get(CONF_MONITORS, {}) if isinstance(entry_data, dict) else {}
    result = DiscoveryResult(
        available_monitors=inventory,
        configured=bool(entry_data.get("configured")) if isinstance(entry_data, dict) else False,
    )

    if not result.configured:
        result.required_gaps.append(
            "Network Diagnostics topology has not been configured. Reconfigure the integration to assign Kuma monitors to diagnostic roles."
        )

    for monitor_key, raw in config.items():
        if not isinstance(raw, dict):
            result.required_gaps.append("Stored monitor configuration is malformed")
            continue
        role = str(raw.get(CONF_ROLE, ROLE_IGNORE))
        if role == ROLE_IGNORE:
            continue
        monitor = by_key.get(monitor_key)
        if monitor is None:
            display = str(raw.get("name") or "Configured Kuma monitor")
            result.missing_configured_monitors.append(display)
            continue
        result.bindings.append(
            MonitorBinding(
                monitor_id=monitor.monitor_key,
                name=monitor.name,
                role=role,
                parent_id=raw.get(CONF_PARENT) or None,
                service=(
                    str(raw.get(CONF_SERVICE)).strip() if raw.get(CONF_SERVICE) else None
                ),
                status_entity=monitor.status_entity,
                response_entity=monitor.response_entity,
                heartbeat_entities=monitor.heartbeat_entities,
                monitor_type_entity=monitor.monitor_type_entity,
                tags_entity=monitor.tags_entity,
                source_entry_id=monitor.source_entry_id,
                monitor_type=monitor.monitor_type,
                target_fingerprint=monitor.target_fingerprint,
                target_ip_version=monitor.target_ip_version,
            )
        )

    assigned = {item.monitor_id for item in result.bindings}
    result.unassigned_monitors = sorted(
        item.name for item in inventory if item.monitor_key not in assigned
    )
    if result.missing_configured_monitors:
        result.required_gaps.append(
            "One or more configured Kuma monitors are no longer available through Home Assistant"
        )
    return result
