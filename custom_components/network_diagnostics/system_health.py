"""System health for Network Diagnostics."""

from __future__ import annotations

from homeassistant.components import system_health
from homeassistant.core import HomeAssistant, callback

from .const import DOMAIN


@callback
def async_register(
    hass: HomeAssistant, register: system_health.SystemHealthRegistration
) -> None:
    register.async_register_info(system_health_info)


async def system_health_info(hass: HomeAssistant) -> dict[str, object]:
    entries = hass.config_entries.async_entries(DOMAIN)
    if not entries:
        return {"loaded": False}
    runtime = getattr(entries[0], "runtime_data", None)
    if runtime is None:
        return {"loaded": False}
    current = runtime.current
    return {
        "loaded": True,
        "configured": runtime.discovery.configured,
        "configured_monitors": len(runtime.discovery.bindings),
        "unassigned_monitors": len(runtime.discovery.unassigned_monitors),
        "diagnosis": current.diagnosis.diagnosis if current else "initializing",
        "evidence_fresh": current.freshness.get("fresh") if current else None,
        "active_incident": runtime.active_incident is not None,
    }
