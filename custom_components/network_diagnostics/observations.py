"""Pure observation data structures used by discovery and classification."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True, slots=True)
class MonitorBinding:
    """One configured Uptime Kuma monitor mapped to a diagnostic role."""

    monitor_id: str
    name: str
    role: str
    status_entity: str
    response_entity: str | None = None
    heartbeat_entities: tuple[str, ...] = ()
    monitor_type_entity: str | None = None
    tags_entity: str | None = None
    source_entry_id: str | None = None
    parent_id: str | None = None
    service: str | None = None
    monitor_type: str | None = None
    target_fingerprint: str | None = None
    target_ip_version: int | None = None


@dataclass(frozen=True, slots=True)
class Observation:
    binding: MonitorBinding
    status: bool | None
    raw_status: str
    response_ms: float | None
    fresh: bool
    age_seconds: float | None
    baseline_state: str = "unavailable"
    baseline_median_ms: float | None = None
    baseline_mad_ms: float | None = None
    baseline_ratio: float | None = None
    baseline_sample_count: int = 0

    @property
    def failed(self) -> bool:
        return self.status is False

    @property
    def healthy(self) -> bool:
        return self.status is True


@dataclass(slots=True)
class ObservationSet:
    configured: bool = True
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

    def by_service(self, role: str, service: str) -> list[Observation]:
        return [
            item
            for item in self.observations
            if item.binding.role == role
            and (item.binding.service or "").casefold() == service.casefold()
        ]

    def by_id(self, monitor_id: str) -> Observation | None:
        return next(
            (item for item in self.observations if item.binding.monitor_id == monitor_id),
            None,
        )

    @property
    def service_groups(self) -> list[str]:
        groups = {item.binding.service for item in self.observations if item.binding.service}
        return sorted(group for group in groups if group)
