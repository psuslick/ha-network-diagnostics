"""Pure observation data structures used by discovery and classification."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True, slots=True)
class MonitorBinding:
    monitor_id: str
    name: str
    role: str
    group: str | None
    label: str
    status_entity: str
    response_entity: str | None = None
    monitor_type_entity: str | None = None
    target_entity: str | None = None
    device_id: str | None = None
    role_source: str = "marker"
    source_entry_id: str | None = None
    monitor_type: str | None = None
    target: str | None = None
    target_fingerprint: str | None = None


@dataclass(frozen=True, slots=True)
class Observation:
    binding: MonitorBinding
    status: bool | None
    raw_status: str
    response_ms: float | None
    fresh: bool
    age_seconds: float | None

    @property
    def failed(self) -> bool:
        return self.status is False

    @property
    def healthy(self) -> bool:
        return self.status is True


@dataclass(slots=True)
class ObservationSet:
    observations: list[Observation] = field(default_factory=list)
    monitoring_gaps: list[str] = field(default_factory=list)
    coverage_gaps: list[str] = field(default_factory=list)
    required_gaps: list[str] = field(default_factory=list)
    unassigned_monitors: list[str] = field(default_factory=list)
    provider_fresh: bool = True
    provider_age_seconds: float | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def by_role(self, role: str) -> list[Observation]:
        return [item for item in self.observations if item.binding.role == role]

    def by_service(self, role: str, group: str) -> list[Observation]:
        return [
            item
            for item in self.observations
            if item.binding.role == role and (item.binding.group or "").casefold() == group.casefold()
        ]

    @property
    def service_groups(self) -> list[str]:
        groups = {
            item.binding.group
            for item in self.observations
            if item.binding.group
        }
        return sorted(group for group in groups if group)
