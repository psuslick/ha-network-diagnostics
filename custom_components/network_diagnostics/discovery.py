"""Discover Uptime Kuma monitor devices and bind them to diagnostic roles."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from .kuma_ids import split_kuma_unique_id
from .observations import MonitorBinding
from .roles import parse_monitor_name
from .targets import sanitize_target, target_fingerprint
from .validation import validate_bindings

UPTIME_KUMA_DOMAIN = "uptime_kuma"

# When enough of these names are present, the installation is recognized as the
# Orbi + NextDNS profile used to design and validate the first release. Missing
# required monitors can then be reported explicitly rather than silently reducing
# diagnostic coverage.
ORBI_NEXTDNS_SENTINELS = {
    "Orbi LAN",
    "Internet IPv4",
    "DNS via Cloudflare",
    "DNS via Orbi",
}
ORBI_NEXTDNS_REQUIRED = {
    "Orbi LAN",
    "Orbi Satellite 1",
    "Orbi Sarah Room",
    "Internet IPv4",
    "Google IPv4",
    "Internet IPv6",
    "Google IPv6",
    "DNS via Cloudflare",
    "DNS via Orbi",
    "Internet HTTPS",
    "DNS via NextDNS 1",
    "DNS via NextDNS 2",
    "NextDNS IPv4 1",
    "NextDNS IPv4 2",
    "NextDNS IPv6 1",
    "NextDNS IPv6 2",
    "NextDNS TCP 443 1",
    "NextDNS TCP 443 2",
}
@dataclass(slots=True)
class DiscoveryResult:
    bindings: list[MonitorBinding] = field(default_factory=list)
    unassigned_monitors: list[str] = field(default_factory=list)
    disabled_status_monitors: list[str] = field(default_factory=list)
    coverage_gaps: list[str] = field(default_factory=list)
    required_gaps: list[str] = field(default_factory=list)
    limitations: list[str] = field(default_factory=list)
    profile: str = "generic"
    kuma_entry_ids: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            "profile": self.profile,
            "kuma_entry_ids": list(self.kuma_entry_ids),
            "bindings": [
                {
                    "monitor_id": item.monitor_id,
                    "name": item.name,
                    "role": item.role,
                    "group": item.group,
                    "label": item.label,
                    "status_entity": item.status_entity,
                    "response_entity": item.response_entity,
                    "monitor_type_entity": item.monitor_type_entity,
                    "target_entity": item.target_entity,
                    "device_id": item.device_id,
                    "role_source": item.role_source,
                    "source_entry_id": item.source_entry_id,
                    "monitor_type": item.monitor_type,
                    "target": item.target,
                    "target_fingerprint": item.target_fingerprint,
                }
                for item in self.bindings
            ],
            "unassigned_monitors": list(self.unassigned_monitors),
            "disabled_status_monitors": list(self.disabled_status_monitors),
            "coverage_gaps": list(self.coverage_gaps),
            "required_gaps": list(self.required_gaps),
            "limitations": list(self.limitations),
        }


def _device_name(device: dr.DeviceEntry | None, fallback: str) -> str:
    if device is None:
        return fallback
    return str(device.name_by_user or device.name or fallback)


def _coordinator_monitors(config_entry: Any) -> dict[str, Any] | None:
    """Return currently-active coordinator monitors without doing network I/O."""
    coordinator = getattr(config_entry, "runtime_data", None)
    data = getattr(coordinator, "data", None)
    if not isinstance(data, dict):
        return None
    return {str(key): value for key, value in data.items()}


def _state_value(hass: HomeAssistant, entity: Any | None) -> str | None:
    if entity is None:
        return None
    state = hass.states.get(entity.entity_id)
    if state is None or str(state.state).lower() in {"unknown", "unavailable", "none", ""}:
        return None
    return str(state.state)


def _target_from_monitor(monitor: Any | None) -> str | None:
    """Return the monitor target used only for display/semantic validation.

    HTTP-family monitors expose a URL. Host/port monitors expose separate
    hostname and port fields; include both so two TCP checks against different
    ports are not accidentally treated as the same endpoint.
    """
    if monitor is None:
        return None
    url = getattr(monitor, "monitor_url", None)
    if url not in (None, "", "null"):
        return str(url)
    hostname = getattr(monitor, "monitor_hostname", None)
    port = getattr(monitor, "monitor_port", None)
    if hostname not in (None, "", "null"):
        if port not in (None, "", "null"):
            return f"{hostname}:{port}"
        return str(hostname)
    if port not in (None, "", "null"):
        return str(port)
    return None


def _monitor_type_from_monitor(monitor: Any | None) -> str | None:
    if monitor is None:
        return None
    value = getattr(monitor, "monitor_type", None)
    if value is None:
        return None
    return str(getattr(value, "value", value))


def _monitor_name(monitor: Any | None, device: dr.DeviceEntry | None, fallback: str) -> str:
    # The role contract is the Uptime Kuma monitor name. Prefer coordinator data
    # over the HA device name because the latter can be renamed independently.
    if monitor is not None:
        value = getattr(monitor, "monitor_name", None)
        if value:
            return str(value)
    return _device_name(device, fallback)


def discover_kuma_monitors(hass: HomeAssistant) -> DiscoveryResult:
    """Discover all core Uptime Kuma monitor devices synchronously in the event loop."""
    entity_registry = er.async_get(hass)
    device_registry = dr.async_get(hass)
    config_entries = hass.config_entries.async_entries(UPTIME_KUMA_DOMAIN)
    result = DiscoveryResult(kuma_entry_ids=[entry.entry_id for entry in config_entries])

    by_monitor: dict[tuple[str, str], dict[str, Any]] = defaultdict(dict)
    device_for_monitor: dict[tuple[str, str], str | None] = {}
    coordinator_data: dict[str, dict[str, Any] | None] = {
        entry.entry_id: _coordinator_monitors(entry) for entry in config_entries
    }

    for config_entry in config_entries:
        active = coordinator_data[config_entry.entry_id]
        for entity in er.async_entries_for_config_entry(entity_registry, config_entry.entry_id):
            if entity.platform != UPTIME_KUMA_DOMAIN:
                continue
            parsed_id = split_kuma_unique_id(entity.unique_id, config_entry.entry_id)
            if parsed_id is None:
                continue
            monitor_id, suffix = parsed_id
            # When coordinator data is available it is the authoritative current
            # monitor inventory. This filters stale registry devices left behind by
            # a deleted Kuma monitor without making an extra request to Kuma.
            if active is not None and monitor_id not in active:
                continue
            key = (config_entry.entry_id, monitor_id)
            by_monitor[key][suffix] = entity
            device_for_monitor[key] = entity.device_id

    names_seen: set[str] = set()
    for (entry_id, monitor_id), entities in sorted(by_monitor.items()):
        status = entities.get("status")
        if status is None:
            continue
        device_id = device_for_monitor[(entry_id, monitor_id)]
        device = device_registry.async_get(device_id) if device_id else None
        monitor = (coordinator_data.get(entry_id) or {}).get(monitor_id)
        name = _monitor_name(monitor, device, status.entity_id)
        names_seen.add(name)
        parsed = parse_monitor_name(name)
        if parsed is None:
            result.unassigned_monitors.append(name)
            continue

        if status.disabled_by is not None:
            result.disabled_status_monitors.append(name)

        response = entities.get("response_time")
        monitor_type_entity = entities.get("type")
        target_entity = entities.get("url") or entities.get("hostname") or entities.get("port")
        monitor_type = _monitor_type_from_monitor(monitor) or _state_value(hass, monitor_type_entity)
        raw_target = _target_from_monitor(monitor) or _state_value(hass, target_entity)
        target = sanitize_target(raw_target)
        result.bindings.append(
            MonitorBinding(
                monitor_id=f"{entry_id}:{monitor_id}",
                name=name,
                role=parsed.role,
                group=parsed.group,
                label=parsed.label or name,
                status_entity=status.entity_id,
                response_entity=response.entity_id if response else None,
                monitor_type_entity=monitor_type_entity.entity_id if monitor_type_entity else None,
                target_entity=target_entity.entity_id if target_entity else None,
                device_id=device_id,
                role_source=parsed.source,
                source_entry_id=entry_id,
                monitor_type=monitor_type,
                target=target,
                target_fingerprint=target_fingerprint(raw_target),
            )
        )

    if len(names_seen & ORBI_NEXTDNS_SENTINELS) >= 3:
        result.profile = "orbi_nextdns"
        missing = sorted(ORBI_NEXTDNS_REQUIRED - names_seen)
        missing_messages = [
            f"Missing expected Kuma monitor for Orbi + NextDNS profile: {name}"
            for name in missing
        ]
        result.coverage_gaps.extend(missing_messages)
        result.required_gaps.extend(missing_messages)
        result.limitations.append(
            "Orbi backhaul/link-quality state is not directly observable through the current Kuma/HA evidence; a reachable satellite with an amber ring can remain software-healthy when reachability and latency are normal."
        )
    elif any(name.startswith("[ND:") for name in names_seen):
        result.profile = "named_roles"

    if not config_entries:
        message = "Home Assistant Uptime Kuma integration is not configured"
        result.coverage_gaps.append(message)
        result.required_gaps.append(message)
    if not result.bindings and config_entries:
        message = (
            "No Uptime Kuma monitors have recognized Network Diagnostics roles. "
            "Use [ND:role] monitor names or a supported profile."
        )
        result.coverage_gaps.append(message)
        result.required_gaps.append(message)

    semantic_warnings, semantic_blockers = validate_bindings(result.bindings)
    result.coverage_gaps.extend(semantic_warnings)
    result.coverage_gaps.extend(semantic_blockers)
    result.required_gaps.extend(semantic_blockers)
    result.coverage_gaps = list(dict.fromkeys(result.coverage_gaps))
    result.required_gaps = list(dict.fromkeys(result.required_gaps))
    result.limitations = list(dict.fromkeys(result.limitations))
    result.unassigned_monitors = sorted(set(result.unassigned_monitors))
    result.disabled_status_monitors = sorted(set(result.disabled_status_monitors))
    return result
