from custom_components.network_diagnostics.classifier import DiagnosisResult
from custom_components.network_diagnostics.models import (
    IncidentRecord,
    IncidentTransition,
    RuntimeSnapshot,
)


def test_incident_round_trip():
    record = IncidentRecord(
        id="abc",
        started_at="2026-01-01T00:00:00+00:00",
        initial_diagnosis="Test fault",
        current_diagnosis="Test fault",
        confidence="medium",
        summary="summary",
        transitions=[
            IncidentTransition(
                at="2026-01-01T00:00:00+00:00",
                diagnosis="Test fault",
                confidence="medium",
                summary="summary",
                evidence=["A failed"],
            )
        ],
        start_snapshot={"a": 1},
        latest_snapshot={"a": 2},
        fingerprint="deadbeef",
    )
    restored = IncidentRecord.from_dict(record.as_dict())
    assert restored.id == "abc"
    assert restored.transitions[0].evidence == ["A failed"]
    assert restored.fingerprint == "deadbeef"


def test_incident_snapshot_is_compact_and_contains_no_target_fields():
    snapshot = RuntimeSnapshot(
        at="2026-01-01T00:00:00+00:00",
        diagnosis=DiagnosisResult(
            diagnosis="Healthy", summary="ok", confidence="high"
        ),
        observations=[
            {
                "name": "Monitor A",
                "role": "gateway",
                "role_name": "Gateway",
                "status": True,
                "response_ms": 5,
                "baseline_state": "normal",
                "baseline_median_ms": 4,
                "baseline_ratio": 1.25,
                "target": "must-not-copy",
                "target_fingerprint": "must-not-copy",
            }
        ],
        discovery={},
        topology=[],
        freshness={"fresh": True},
    )
    compact = snapshot.incident_snapshot()
    assert compact["observations"][0]["name"] == "Monitor A"
    assert "target" not in compact["observations"][0]
    assert "target_fingerprint" not in compact["observations"][0]
