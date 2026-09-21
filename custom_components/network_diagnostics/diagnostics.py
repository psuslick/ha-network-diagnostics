"""Privacy-reduced diagnostics support for Network Diagnostics."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from homeassistant.core import HomeAssistant

from . import NetworkDiagnosticsConfigEntry
from .const import VERSION


def _aliases(runtime: Any) -> tuple[dict[str, str], dict[str, str], dict[str, str]]:
    bindings = sorted(runtime.discovery.bindings, key=lambda item: item.monitor_id)
    id_alias = {
        item.monitor_id: f"monitor_{index}"
        for index, item in enumerate(bindings, start=1)
    }
    name_alias = {
        item.name: f"Monitor {index}"
        for index, item in enumerate(bindings, start=1)
        if item.name
    }
    services = sorted(
        {item.service for item in bindings if item.service}, key=str.casefold
    )
    service_alias = {
        service: f"Service {index}"
        for index, service in enumerate(services, start=1)
    }
    return id_alias, name_alias, service_alias


def _replace_text(
    value: str,
    *,
    id_alias: dict[str, str],
    name_alias: dict[str, str],
    service_alias: dict[str, str],
) -> str:
    out = value
    replacements = {**id_alias, **name_alias, **service_alias}
    for source in sorted(replacements, key=len, reverse=True):
        if source:
            out = out.replace(source, replacements[source])
    return out


def _redact(
    value: Any,
    *,
    id_alias: dict[str, str],
    name_alias: dict[str, str],
    service_alias: dict[str, str],
) -> Any:
    if isinstance(value, str):
        return _replace_text(
            value,
            id_alias=id_alias,
            name_alias=name_alias,
            service_alias=service_alias,
        )
    if isinstance(value, list):
        return [
            _redact(
                item,
                id_alias=id_alias,
                name_alias=name_alias,
                service_alias=service_alias,
            )
            for item in value
        ]
    if isinstance(value, tuple):
        return [
            _redact(
                item,
                id_alias=id_alias,
                name_alias=name_alias,
                service_alias=service_alias,
            )
            for item in value
        ]
    if isinstance(value, dict):
        return {
            str(key): _redact(
                item,
                id_alias=id_alias,
                name_alias=name_alias,
                service_alias=service_alias,
            )
            for key, item in value.items()
            if str(key) not in {"source_entry_id", "target_fingerprint"}
        }
    return value


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: NetworkDiagnosticsConfigEntry
) -> dict[str, Any]:
    """Return bounded diagnostics without targets or deployment names."""
    runtime = getattr(entry, "runtime_data", None)
    if runtime is None:
        return {"version": VERSION, "loaded": False}

    payload = {
        "version": VERSION,
        "loaded": True,
        "discovery": runtime.discovery.as_dict(),
        "behavior_options": dict(entry.options),
        "current": runtime.current.as_dict() if runtime.current else None,
        "active_incident": runtime.active_incident.as_dict()
        if runtime.active_incident
        else None,
        "recent_incidents": [item.as_dict() for item in runtime.incidents[-20:]],
        "last_manual_analysis": runtime.last_manual_analysis,
    }
    id_alias, name_alias, service_alias = _aliases(runtime)
    return _redact(
        deepcopy(payload),
        id_alias=id_alias,
        name_alias=name_alias,
        service_alias=service_alias,
    )
