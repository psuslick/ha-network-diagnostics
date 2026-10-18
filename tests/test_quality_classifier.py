from custom_components.network_diagnostics.classifier import HEALTHY, classify
from custom_components.network_diagnostics.const import ROLE_FIXED_CLIENT, ROLE_GATEWAY
from custom_components.network_diagnostics.quality import QualityAssessment


def test_healthy_client_flapping_is_not_mislabeled_healthy(
    make_binding, make_observation, make_set
):
    gateway = make_binding("g", "Gateway A", ROLE_GATEWAY)
    client = make_binding("c", "Client A", ROLE_FIXED_CLIENT, parent_id="g")
    observations = make_set([make_observation(gateway), make_observation(client)])
    result = classify(
        observations,
        unstable_nodes={"c": QualityAssessment(recent_outages=2, flapping=True)},
    )
    assert result.diagnosis == "Client A intermittent reachability"
    assert result.confidence == "medium"
    assert "parent" in result.evidence[1].lower()


def test_single_recovered_drop_is_not_an_intermitttent_incident(
    make_binding, make_observation, make_set
):
    client = make_binding("c", "Client A", ROLE_FIXED_CLIENT)
    result = classify(
        make_set([make_observation(client)]),
        unstable_nodes={"c": QualityAssessment(recent_outages=1)},
    )
    assert result.diagnosis == HEALTHY


def test_flapping_does_not_double_count_a_currently_down_client(
    make_binding, make_observation, make_set
):
    gateway = make_binding("g", "Gateway A", ROLE_GATEWAY)
    client = make_binding("c", "Client A", ROLE_FIXED_CLIENT, parent_id="g")
    result = classify(
        make_set([make_observation(gateway), make_observation(client, status=False)]),
        unstable_nodes={"c": QualityAssessment(recent_outages=2, flapping=True)},
    )
    assert "intermittent" not in result.diagnosis.lower()

