from __future__ import annotations

from custom_components.network_diagnostics.models import IncidentRecord, IncidentTransition


def test_incident_roundtrip():
    record = IncidentRecord(
        id="abc",
        started_at="2026-09-19T12:00:00+00:00",
        initial_diagnosis="A",
        current_diagnosis="B",
        confidence="high",
        summary="summary",
        transitions=[IncidentTransition("2026-09-19T12:00:00+00:00", "A", "high", "s", ["e"])],
        start_snapshot={"x": 1},
        latest_snapshot={"x": 2},
        fingerprint="f123",
        ended_at="2026-09-19T12:01:00+00:00",
        duration_seconds=60,
        recovered_snapshot={"x": 3},
    )
    assert IncidentRecord.from_dict(record.as_dict()).as_dict() == record.as_dict()


def test_incident_old_shape_defaults():
    data = {
        "id": "abc",
        "started_at": "2026-09-19T12:00:00+00:00",
        "initial_diagnosis": "A",
        "transitions": [],
    }
    restored = IncidentRecord.from_dict(data)
    assert restored.current_diagnosis == "A"
    assert restored.confidence == "unknown"
    assert restored.fingerprint == ""
