"""Network Diagnostics integration."""

from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import DOMAIN, PLATFORMS
from .frontend import async_register_frontend, async_unregister_frontend
from .runtime import NetworkDiagnosticsRuntime
from .websocket import async_register_websocket_commands

_LOGGER = logging.getLogger(__name__)

type NetworkDiagnosticsConfigEntry = ConfigEntry[NetworkDiagnosticsRuntime]


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Set up integration-global frontend APIs."""
    async_register_websocket_commands(hass)
    return True


async def async_setup_entry(
    hass: HomeAssistant, entry: NetworkDiagnosticsConfigEntry
) -> bool:
    """Set up Network Diagnostics."""
    runtime = NetworkDiagnosticsRuntime(hass, entry)
    entry.runtime_data = runtime
    await runtime.async_start()
    try:
        await async_register_frontend(hass)
    except (ValueError, RuntimeError) as err:
        # A panel collision must never disable diagnostics.
        _LOGGER.warning("Network Diagnostics sidebar panel was not registered: %s", err)
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(
    hass: HomeAssistant, entry: NetworkDiagnosticsConfigEntry
) -> bool:
    """Unload Network Diagnostics."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        await entry.runtime_data.async_stop()
        async_unregister_frontend(hass)
    return unload_ok


async def async_migrate_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Migrate the v0.1 manual-mapping config entry to automatic discovery."""
    if entry.version < 2:
        # v0.2 intentionally discards manual entity-map options. Behavior options
        # keep the same key names where possible; stale mapping options are ignored.
        keep = {
            key: value
            for key, value in entry.options.items()
            if key
            in {
                "stale_seconds",
                "failure_confirm_seconds",
                "recovery_confirm_seconds",
                "incident_retention",
                "mesh_latency_ms",
                "mesh_degradation_seconds",
            }
        }
        # Map old satellite behavior keys to the generic mesh equivalents.
        if "satellite_latency_ms" in entry.options:
            keep["mesh_latency_ms"] = entry.options["satellite_latency_ms"]
        if "satellite_degradation_seconds" in entry.options:
            keep["mesh_degradation_seconds"] = entry.options[
                "satellite_degradation_seconds"
            ]
        hass.config_entries.async_update_entry(entry, version=2, options=keep)
    return True
