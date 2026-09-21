"""Network Diagnostics integration."""

from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import CONF_CONFIGURED, CONF_MONITORS, CONFIG_VERSION, PLATFORMS
from .frontend import async_register_frontend, async_unregister_frontend
from .runtime import NetworkDiagnosticsRuntime
from .websocket import async_register_websocket_commands

_LOGGER = logging.getLogger(__name__)

type NetworkDiagnosticsConfigEntry = ConfigEntry[NetworkDiagnosticsRuntime]


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Set up integration-global APIs."""
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
    """Migrate prototype config entries to the generic v0.3 topology model."""
    if entry.version < CONFIG_VERSION:
        hass.config_entries.async_update_entry(
            entry,
            version=CONFIG_VERSION,
            data={CONF_CONFIGURED: False, CONF_MONITORS: {}},
        )
    return True
