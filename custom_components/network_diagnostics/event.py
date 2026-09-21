"""Event entity for Network Diagnostics incident lifecycle changes."""

from __future__ import annotations

from typing import Any

from homeassistant.components.event import EventEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .entity import NetworkDiagnosticsEntity
from .runtime import NetworkDiagnosticsRuntime


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    runtime: NetworkDiagnosticsRuntime = entry.runtime_data
    async_add_entities([IncidentEvent(runtime)])


class IncidentEvent(NetworkDiagnosticsEntity, EventEntity):
    _attr_translation_key = "incident"
    _attr_icon = "mdi:alert-decagram-outline"
    _attr_event_types = ["started", "updated", "recovered"]

    def __init__(self, runtime: NetworkDiagnosticsRuntime) -> None:
        super().__init__(runtime, "incident")
        self._remove_incident_listener = None

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        self._remove_incident_listener = self.runtime.add_incident_listener(
            self._handle_incident
        )

    async def async_will_remove_from_hass(self) -> None:
        if self._remove_incident_listener:
            self._remove_incident_listener()
            self._remove_incident_listener = None
        await super().async_will_remove_from_hass()

    @callback
    def _handle_incident(self, kind: str, payload: dict[str, Any]) -> None:
        self._trigger_event(kind, payload)
        self.async_write_ha_state()
