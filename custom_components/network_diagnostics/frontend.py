"""Register the Network Diagnostics admin-only sidebar panel."""

from __future__ import annotations

from pathlib import Path

from homeassistant.components import frontend, panel_custom
from homeassistant.components.http import StaticPathConfig
from homeassistant.core import HomeAssistant

from .const import DOMAIN, PANEL_ICON, PANEL_TITLE, PANEL_URL_PATH, STATIC_URL, VERSION

_REGISTERED = False


async def async_register_frontend(hass: HomeAssistant) -> None:
    """Register static assets and the integration-owned panel once."""
    global _REGISTERED
    if _REGISTERED:
        return
    path = Path(__file__).parent / "frontend"
    await hass.http.async_register_static_paths(
        [StaticPathConfig(STATIC_URL, str(path), False)]
    )
    await panel_custom.async_register_panel(
        hass,
        frontend_url_path=PANEL_URL_PATH,
        webcomponent_name="network-diagnostics-panel",
        sidebar_title=PANEL_TITLE,
        sidebar_icon=PANEL_ICON,
        module_url=f"{STATIC_URL}/network-diagnostics-panel.js?v={VERSION}",
        require_admin=True,
        config={},
        config_panel_domain=DOMAIN,
    )
    _REGISTERED = True


def async_unregister_frontend(hass: HomeAssistant) -> None:
    """Remove the sidebar panel."""
    global _REGISTERED
    if not _REGISTERED:
        return
    frontend.async_remove_panel(hass, PANEL_URL_PATH)
    _REGISTERED = False
