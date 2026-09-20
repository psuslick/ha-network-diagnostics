"""Button entity for Network Diagnostics."""

from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .entity import NetworkDiagnosticsEntity
from .runtime import NetworkDiagnosticsRuntime


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    runtime: NetworkDiagnosticsRuntime = entry.runtime_data
    async_add_entities([AnalyzeNowButton(runtime)])


class AnalyzeNowButton(NetworkDiagnosticsEntity, ButtonEntity):
    _attr_name = "Analyze now"
    _attr_icon = "mdi:stethoscope"

    def __init__(self, runtime: NetworkDiagnosticsRuntime) -> None:
        super().__init__(runtime, "analyze_now")

    async def async_press(self) -> None:
        await self.runtime.async_analyze(manual=True)
