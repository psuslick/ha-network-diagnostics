"""Base entity for Network Diagnostics."""

from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import Entity

from .const import DOMAIN, NAME, VERSION
from .runtime import NetworkDiagnosticsRuntime


class NetworkDiagnosticsEntity(Entity):
    """Base entity tied to the integration runtime."""

    _attr_has_entity_name = True

    def __init__(self, runtime: NetworkDiagnosticsRuntime, key: str) -> None:
        self.runtime = runtime
        self._attr_unique_id = f"{runtime.entry.entry_id}_{key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, runtime.entry.entry_id)},
            name=NAME,
            model="Uptime Kuma diagnostic correlation layer",
            sw_version=VERSION,
        )
        self._remove_listener = None

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        self._remove_listener = self.runtime.add_update_listener(self.async_write_ha_state)

    async def async_will_remove_from_hass(self) -> None:
        if self._remove_listener:
            self._remove_listener()
            self._remove_listener = None
        await super().async_will_remove_from_hass()
