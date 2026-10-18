from custom_components.network_diagnostics.classifier import DiagnosisResult
from custom_components.network_diagnostics.models import RuntimeSnapshot
from custom_components.network_diagnostics.triage import triage_recommendations


def _snapshot(diagnosis, observations=()):
    return RuntimeSnapshot(
        at="2026-01-01T00:00:00+00:00",
        diagnosis=DiagnosisResult(diagnosis=diagnosis, summary="synthetic", confidence="medium"),
        observations=list(observations),
        discovery={}, topology=[], freshness={},
    )


def test_reachable_devices_do_not_rule_out_command_failures():
    checks = triage_recommendations(_snapshot("Healthy", [{"status": True}]))
    assert any("application" in item for item in checks)


def test_flapping_and_latency_each_produce_distinct_checks():
    checks = triage_recommendations(_snapshot("Intermittent", [
        {"status": True, "flapping": True, "baseline_state": "degraded"}
    ]))
    assert any("Kuma status drops" in item for item in checks)
    assert any("slow endpoint" in item for item in checks)


def test_missing_evidence_comes_before_network_fault_speculation():
    checks = triage_recommendations(_snapshot("Monitoring incomplete"))
    assert any("Restore fresh" in item for item in checks)
    assert not any("device failure" in item for item in checks)

