"""Base entity for Network Diagnostics."""

from __future__ import annotations

from homeassistant.core import callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import Entity

from .const import DOMAIN, NAME
from .runtime import NetworkDiagnosticsRuntime


class NetworkDiagnosticsEntity(Entity):
    """Base entity backed by the runtime's event-driven state."""

    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(self, runtime: NetworkDiagnosticsRuntime, key: str) -> None:
        self.runtime = runtime
        self._attr_unique_id = f"{runtime.entry.entry_id}_{key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, runtime.entry.entry_id)},
            name=NAME,
            manufacturer="Network Diagnostics",
            model="Topology-aware RCA",
        )
        self._remove_runtime_listener = None

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        self._remove_runtime_listener = self.runtime.add_update_listener(
            self._handle_runtime_update
        )

    async def async_will_remove_from_hass(self) -> None:
        if self._remove_runtime_listener:
            self._remove_runtime_listener()
            self._remove_runtime_listener = None
        await super().async_will_remove_from_hass()

    @callback
    def _handle_runtime_update(self) -> None:
        self.async_write_ha_state()
