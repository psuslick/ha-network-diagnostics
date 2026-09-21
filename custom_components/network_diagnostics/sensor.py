"""Sensor entities for Network Diagnostics."""

from __future__ import annotations

from typing import Any

from homeassistant.components.sensor import SensorEntity
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
    async_add_entities(
        [
            DiagnosisSensor(runtime),
            ConfidenceSensor(runtime),
            CoverageSensor(runtime),
            LastIncidentSensor(runtime),
            Incidents24hSensor(runtime),
        ]
    )


class DiagnosisSensor(NetworkDiagnosticsEntity, SensorEntity):
    _attr_translation_key = "status"
    _attr_icon = "mdi:stethoscope"

    def __init__(self, runtime: NetworkDiagnosticsRuntime) -> None:
        super().__init__(runtime, "status")

    @property
    def native_value(self) -> str:
        return (
            self.runtime.current.diagnosis.diagnosis
            if self.runtime.current
            else "Initializing"
        )

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        current = self.runtime.current
        if current is None:
            return {}
        result = current.diagnosis
        return {
            "summary": result.summary,
            "confidence": result.confidence,
            "evidence": list(result.evidence),
            "contradictions": list(result.contradictions),
            "downstream": list(result.downstream),
            "unaffected": list(result.unaffected),
            "failed_controls": list(result.failed_controls),
            "affected_components": list(result.affected_components),
            "monitoring_gaps": list(result.monitoring_gaps),
            "coverage_gaps": list(result.coverage_gaps),
            "unassigned_monitors": list(result.unassigned_monitors),
            "root_causes": [
                {
                    "name": cause.name,
                    "domain": cause.domain,
                    "confidence": cause.confidence,
                    "supporting": list(cause.supporting),
                    "contradicting": list(cause.contradicting),
                    "downstream": list(cause.downstream),
                    "affected": list(cause.affected),
                    "causal_path": list(cause.causal_path),
                }
                for cause in result.root_causes
            ],
            "evidence_fresh": current.freshness.get("fresh"),
            "configured": current.discovery.get("configured"),
            "last_manual_analysis": self.runtime.last_manual_analysis,
        }


class ConfidenceSensor(NetworkDiagnosticsEntity, SensorEntity):
    _attr_translation_key = "confidence"
    _attr_icon = "mdi:gauge"

    def __init__(self, runtime: NetworkDiagnosticsRuntime) -> None:
        super().__init__(runtime, "confidence")

    @property
    def native_value(self) -> str:
        return (
            self.runtime.current.diagnosis.confidence
            if self.runtime.current
            else "unknown"
        )


class CoverageSensor(NetworkDiagnosticsEntity, SensorEntity):
    _attr_translation_key = "coverage"
    _attr_icon = "mdi:radar"

    def __init__(self, runtime: NetworkDiagnosticsRuntime) -> None:
        super().__init__(runtime, "coverage")

    @property
    def native_value(self) -> str:
        if not self.runtime.current:
            return "Initializing"
        return (
            "Complete"
            if not self.runtime.current.diagnosis.coverage_gaps
            else "Partial"
        )

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        if not self.runtime.current:
            return {}
        return {
            "coverage_gaps": list(self.runtime.current.diagnosis.coverage_gaps),
            "capabilities": dict(
                self.runtime.current.discovery.get("coverage_capabilities", {})
            ),
            "unassigned_monitors": list(
                self.runtime.current.diagnosis.unassigned_monitors
            ),
            "configured_monitor_count": len(
                self.runtime.current.discovery.get("bindings", [])
            ),
        }


class LastIncidentSensor(NetworkDiagnosticsEntity, SensorEntity):
    _attr_translation_key = "last_incident"
    _attr_icon = "mdi:timeline-alert"

    def __init__(self, runtime: NetworkDiagnosticsRuntime) -> None:
        super().__init__(runtime, "last_incident")

    @property
    def native_value(self) -> str:
        if self.runtime.active_incident:
            return self.runtime.active_incident.current_diagnosis
        if self.runtime.incidents:
            return self.runtime.incidents[-1].current_diagnosis
        return "None"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        incident = self.runtime.active_incident or (
            self.runtime.incidents[-1] if self.runtime.incidents else None
        )
        if incident is None:
            return {}
        return {
            "incident_id": incident.id,
            "started_at": incident.started_at,
            "ended_at": incident.ended_at,
            "duration_seconds": incident.duration_seconds,
            "confidence": incident.confidence,
            "summary": incident.summary,
            "transition_count": len(incident.transitions),
            "fingerprint": incident.fingerprint,
            "similar_incident_count": self.runtime.similar_incident_count(
                incident.fingerprint
            ),
            "active": self.runtime.active_incident is not None,
        }


class Incidents24hSensor(NetworkDiagnosticsEntity, SensorEntity):
    _attr_translation_key = "incidents_24h"
    _attr_icon = "mdi:counter"

    def __init__(self, runtime: NetworkDiagnosticsRuntime) -> None:
        super().__init__(runtime, "incidents_24h")

    @property
    def native_value(self) -> int:
        return self.runtime.incidents_24h
