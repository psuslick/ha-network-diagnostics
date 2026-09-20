"""Frontend registration for Network Diagnostics."""

from __future__ import annotations

from pathlib import Path

from homeassistant.components import frontend, panel_custom
from homeassistant.components.http import StaticPathConfig
from homeassistant.core import HomeAssistant

from .const import DOMAIN, PANEL_ICON, PANEL_TITLE, PANEL_URL_PATH, STATIC_URL, VERSION

FRONTEND_DIR = Path(__file__).parent / "frontend"
PANEL_JS = f"{STATIC_URL}/network-diagnostics-panel.js?v={VERSION}"
PANEL_ELEMENT = "network-diagnostics-panel"


async def async_register_frontend(hass: HomeAssistant) -> bool:
    """Serve and register the integration-owned admin sidebar panel.

    Returns True only when this integration created the panel. A URL collision
    fails soft so the diagnostic backend still works.
    """
    data = hass.data.setdefault(DOMAIN, {})
    if not data.get("static_registered"):
        await hass.http.async_register_static_paths(
            [StaticPathConfig(STATIC_URL, str(FRONTEND_DIR), True)]
        )
        data["static_registered"] = True

    if frontend.async_panel_exists(hass, PANEL_URL_PATH):
        return bool(data.get("panel_owned"))

    await panel_custom.async_register_panel(
        hass=hass,
        frontend_url_path=PANEL_URL_PATH,
        webcomponent_name=PANEL_ELEMENT,
        module_url=PANEL_JS,
        sidebar_title=PANEL_TITLE,
        sidebar_icon=PANEL_ICON,
        require_admin=True,
        config={},
    )
    data["panel_owned"] = True
    return True


def async_unregister_frontend(hass: HomeAssistant) -> None:
    """Remove only the panel this integration registered."""
    data = hass.data.get(DOMAIN, {})
    if data.get("panel_owned") and frontend.async_panel_exists(hass, PANEL_URL_PATH):
        frontend.async_remove_panel(hass, PANEL_URL_PATH)
    data["panel_owned"] = False
