"""Diagnostics support for Network Diagnostics."""

from __future__ import annotations

from typing import Any

from homeassistant.core import HomeAssistant

from . import NetworkDiagnosticsConfigEntry
from .const import VERSION


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: NetworkDiagnosticsConfigEntry
) -> dict[str, Any]:
    """Return a bounded, credential-free diagnostics payload."""
    runtime = entry.runtime_data
    return {
        "version": VERSION,
        "discovery": runtime.discovery.as_dict(),
        "behavior_options": dict(entry.options),
        "current": runtime.current.as_dict() if runtime.current else None,
        "active_incident": runtime.active_incident.as_dict()
        if runtime.active_incident
        else None,
        "recent_incidents": [item.as_dict() for item in runtime.incidents[-20:]],
        "last_manual_analysis": runtime.last_manual_analysis,
    }
