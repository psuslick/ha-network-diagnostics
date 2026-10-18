from custom_components.network_diagnostics.classifier import DiagnosisResult, RootCause
from custom_components.network_diagnostics.const import ROLE_FIXED_CLIENT
from custom_components.network_diagnostics.fingerprint import incident_fingerprint


def _result(name):
    return DiagnosisResult(
        diagnosis=f"{name} intermittent reachability",
        summary="synthetic", confidence="medium",
        root_causes=(RootCause(name=f"{name} intermittent reachability", domain="intermittent", confidence="medium", affected=(name,)),),
    )


def test_recovered_events_at_distinct_monitors_do_not_share_fingerprint(
    make_binding, make_observation, make_set
):
    first = make_binding("first-id", "First Client", ROLE_FIXED_CLIENT)
    second = make_binding("second-id", "Second Client", ROLE_FIXED_CLIENT)
    obs = make_set([make_observation(first), make_observation(second)])
    assert incident_fingerprint(_result("First Client"), obs) != incident_fingerprint(
        _result("Second Client"), obs
    )


def test_renaming_monitor_does_not_change_its_causal_fingerprint(
    make_binding, make_observation, make_set
):
    before = make_set([make_observation(make_binding("stable-id", "Old Client", ROLE_FIXED_CLIENT))])
    after = make_set([make_observation(make_binding("stable-id", "New Client", ROLE_FIXED_CLIENT))])
    assert incident_fingerprint(_result("Old Client"), before) == incident_fingerprint(
        _result("New Client"), after
    )
