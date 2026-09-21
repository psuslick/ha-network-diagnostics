"""Load pure integration modules without requiring a Home Assistant install."""

from __future__ import annotations

from pathlib import Path
import sys
import types

import pytest

ROOT = Path(__file__).resolve().parents[1]
CC = ROOT / "custom_components"
PKG = CC / "network_diagnostics"

custom_components = types.ModuleType("custom_components")
custom_components.__path__ = [str(CC)]
sys.modules.setdefault("custom_components", custom_components)

network_diagnostics = types.ModuleType("custom_components.network_diagnostics")
network_diagnostics.__path__ = [str(PKG)]
sys.modules.setdefault("custom_components.network_diagnostics", network_diagnostics)

from custom_components.network_diagnostics.observations import (  # noqa: E402
    MonitorBinding,
    Observation,
    ObservationSet,
)


@pytest.fixture
def make_binding():
    def _make(
        monitor_id: str,
        name: str,
        role: str,
        *,
        parent_id: str | None = None,
        service: str | None = None,
        monitor_type: str | None = "ping",
        target_fingerprint: str | None = None,
        target_ip_version: int | None = None,
    ) -> MonitorBinding:
        return MonitorBinding(
            monitor_id=monitor_id,
            name=name,
            role=role,
            status_entity=f"sensor.{monitor_id}_status",
            response_entity=f"sensor.{monitor_id}_response",
            heartbeat_entities=(f"sensor.{monitor_id}_response",),
            parent_id=parent_id,
            service=service,
            monitor_type=monitor_type,
            target_fingerprint=target_fingerprint,
            target_ip_version=target_ip_version,
        )

    return _make


@pytest.fixture
def make_observation():
    def _make(
        binding: MonitorBinding,
        status: bool | None = True,
        *,
        response_ms: float | None = 5.0,
        fresh: bool = True,
        baseline_state: str = "normal",
        baseline_median_ms: float | None = 5.0,
        baseline_ratio: float | None = 1.0,
        baseline_sample_count: int = 20,
    ) -> Observation:
        raw = "up" if status is True else "down" if status is False else "unknown"
        return Observation(
            binding=binding,
            status=status,
            raw_status=raw,
            response_ms=response_ms,
            fresh=fresh,
            age_seconds=1.0,
            baseline_state=baseline_state,
            baseline_median_ms=baseline_median_ms,
            baseline_mad_ms=1.0,
            baseline_ratio=baseline_ratio,
            baseline_sample_count=baseline_sample_count,
        )

    return _make


@pytest.fixture
def make_set():
    def _make(observations, **kwargs) -> ObservationSet:
        return ObservationSet(observations=list(observations), **kwargs)

    return _make
