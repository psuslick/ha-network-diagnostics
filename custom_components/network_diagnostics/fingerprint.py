"""Stable causal identity for compact incident recurrence grouping."""

from __future__ import annotations

import hashlib

from .classifier import DiagnosisResult
from .observations import ObservationSet


def incident_fingerprint(result: DiagnosisResult, observations: ObservationSet) -> str:
    """Include affected stable IDs even if no current monitor reports DOWN."""
    domains = sorted(cause.domain for cause in result.root_causes) or [result.diagnosis]
    failed_ids = sorted(
        item.binding.monitor_id
        for item in observations.observations
        if item.status is False
    )
    affected_names = {name for cause in result.root_causes for name in cause.affected}
    affected_ids = sorted(
        item.binding.monitor_id
        for item in observations.observations
        if item.binding.name in affected_names
    )
    raw = "|".join([*domains, *failed_ids, *affected_ids])
    return hashlib.sha256(raw.encode()).hexdigest()[:16]
