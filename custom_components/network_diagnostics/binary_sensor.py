"""Binary sensors for Network Diagnostics."""

from __future__ import annotations

from typing import Any

from homeassistant.components.binary_sensor import BinarySensorEntity
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
    async_add_entities([MonitoringProblemSensor(runtime), ActiveIncidentSensor(runtime)])


class MonitoringProblemSensor(NetworkDiagnosticsEntity, BinarySensorEntity):
    _attr_translation_key = "monitoring_problem"
    _attr_icon = "mdi:monitor-alert"

    def __init__(self, runtime: NetworkDiagnosticsRuntime) -> None:
        super().__init__(runtime, "monitoring_problem")

    @property
    def is_on(self) -> bool:
        return bool(
            self.runtime.current and self.runtime.current.diagnosis.monitoring_problem
        )

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        if not self.runtime.current:
            return {}
        return {
            "monitoring_gaps": list(
                self.runtime.current.diagnosis.monitoring_gaps
            ),
            "coverage_gaps": list(self.runtime.current.diagnosis.coverage_gaps),
            "evidence_fresh": self.runtime.current.freshness.get("fresh"),
        }


class ActiveIncidentSensor(NetworkDiagnosticsEntity, BinarySensorEntity):
    _attr_translation_key = "active_incident"
    _attr_icon = "mdi:alert-circle-outline"

    def __init__(self, runtime: NetworkDiagnosticsRuntime) -> None:
        super().__init__(runtime, "active_incident")

    @property
    def is_on(self) -> bool:
        return self.runtime.active_incident is not None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        incident = self.runtime.active_incident
        if not incident:
            return {}
        return {
            "incident_id": incident.id,
            "started_at": incident.started_at,
            "diagnosis": incident.current_diagnosis,
            "confidence": incident.confidence,
            "summary": incident.summary,
            "transition_count": len(incident.transitions),
            "fingerprint": incident.fingerprint,
        }
