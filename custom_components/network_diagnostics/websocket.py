"""WebSocket API for the Network Diagnostics panel."""

from __future__ import annotations

import voluptuous as vol

from homeassistant.components import websocket_api
from homeassistant.core import HomeAssistant, callback

from .const import DOMAIN


def _runtime(hass: HomeAssistant):
    """Return the loaded runtime without assuming every entry has runtime_data."""
    entries = hass.config_entries.async_entries(DOMAIN)
    if not entries:
        return None
    return getattr(entries[0], "runtime_data", None)


@websocket_api.require_admin
@websocket_api.websocket_command({vol.Required("type"): "network_diagnostics/get_snapshot"})
@callback
def websocket_get_snapshot(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict,
) -> None:
    """Return the current diagnostic snapshot and recent incidents."""
    runtime = _runtime(hass)
    if runtime is None:
        connection.send_error(msg["id"], "not_loaded", "Network Diagnostics is not loaded")
        return
    connection.send_result(msg["id"], runtime.panel_payload())


@websocket_api.require_admin
@websocket_api.websocket_command({vol.Required("type"): "network_diagnostics/analyze"})
@websocket_api.async_response
async def websocket_analyze(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict,
) -> None:
    """Run a local analysis pass; this performs no network I/O."""
    runtime = _runtime(hass)
    if runtime is None:
        connection.send_error(msg["id"], "not_loaded", "Network Diagnostics is not loaded")
        return
    await runtime.async_analyze(manual=True)
    connection.send_result(msg["id"], runtime.panel_payload())


def async_register_websocket_commands(hass: HomeAssistant) -> None:
    """Register commands once per Home Assistant process."""
    data = hass.data.setdefault(DOMAIN, {})
    if data.get("websocket_registered"):
        return
    websocket_api.async_register_command(hass, websocket_get_snapshot)
    websocket_api.async_register_command(hass, websocket_analyze)
    data["websocket_registered"] = True
