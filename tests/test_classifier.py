from custom_components.network_diagnostics.baseline import BaselineAssessment
from custom_components.network_diagnostics.classifier import (
    HEALTHY,
    MONITORING_INCOMPLETE,
    MULTIPLE,
    classify,
)
from custom_components.network_diagnostics.const import (
    ROLE_DNS_LOCAL,
    ROLE_DNS_NEUTRAL,
    ROLE_FIXED_CLIENT,
    ROLE_GATEWAY,
    ROLE_HTTPS_CONTROL,
    ROLE_IPV4_CONTROL,
    ROLE_IPV6_CONTROL,
    ROLE_LAN_CONTROL,
    ROLE_MESH_NODE,
    ROLE_NETWORK_NODE,
    ROLE_SERVICE_DNS,
    ROLE_SERVICE_PATH,
)


def assessment(state="normal", *, sustained=False, median=5.0, ratio=1.0):
    return BaselineAssessment(
        state=state,
        sample_count=20,
        median_ms=median,
        mad_ms=1.0,
        ratio=ratio,
        delta_ms=(median * ratio - median) if ratio is not None else None,
        abnormal=state in {"abnormal", "degraded"},
        sustained=sustained,
        abnormal_seconds=120.0 if sustained else None,
    )


def test_healthy_with_partial_coverage_is_not_monitoring_incomplete(
    make_binding, make_observation, make_set
):
    gateway = make_binding("g", "Gateway A", ROLE_GATEWAY)
    obs = make_set(
        [make_observation(gateway)],
        coverage_gaps=["IPv6-specific failure is not covered"],
    )
    result = classify(obs)
    assert result.diagnosis == HEALTHY
    assert result.confidence == "medium"
    assert result.coverage_gaps


def test_required_gap_blocks_health(make_binding, make_observation, make_set):
    gateway = make_binding("g", "Gateway A", ROLE_GATEWAY)
    result = classify(
        make_set(
            [make_observation(gateway)],
            required_gaps=["Configured evidence is invalid"],
        )
    )
    assert result.diagnosis == MONITORING_INCOMPLETE
    assert result.confidence == "insufficient"


def test_stale_provider_blocks_health(make_binding, make_observation, make_set):
    gateway = make_binding("g", "Gateway A", ROLE_GATEWAY)
    result = classify(
        make_set(
            [make_observation(gateway)],
            provider_fresh=False,
            provider_age_seconds=240,
        )
    )
    assert result.diagnosis == MONITORING_INCOMPLETE
    assert any("stale" in gap.lower() for gap in result.monitoring_gaps)


def test_gateway_probe_down_but_internet_up_is_management_reachability(
    make_binding, make_observation, make_set
):
    gateway = make_binding("g", "Gateway A", ROLE_GATEWAY)
    internet = make_binding("i", "Internet A", ROLE_IPV4_CONTROL)
    result = classify(
        make_set([make_observation(gateway, False), make_observation(internet, True)])
    )
    assert result.diagnosis == "Gateway management/reachability failure"


def test_failed_parent_suppresses_failed_descendant(
    make_binding, make_observation, make_set
):
    gateway = make_binding("g", "Gateway A", ROLE_GATEWAY)
    node = make_binding("n", "Network Node A", ROLE_NETWORK_NODE, parent_id="g")
    child = make_binding("m", "Mesh Node A", ROLE_MESH_NODE, parent_id="n")
    result = classify(
        make_set(
            [
                make_observation(gateway, True),
                make_observation(node, False),
                make_observation(child, False),
            ]
        )
    )
    assert result.diagnosis == "Network Node A unreachable"
    assert "Mesh Node A" in result.downstream


def test_two_failed_mesh_siblings_are_one_mesh_layer_failure(
    make_binding, make_observation, make_set
):
    gateway = make_binding("g", "Gateway A", ROLE_GATEWAY)
    mesh_a = make_binding("m1", "Mesh Node A", ROLE_MESH_NODE, parent_id="g")
    mesh_b = make_binding("m2", "Mesh Node B", ROLE_MESH_NODE, parent_id="g")
    result = classify(
        make_set(
            [
                make_observation(gateway, True),
                make_observation(mesh_a, False),
                make_observation(mesh_b, False),
            ]
        )
    )
    assert result.diagnosis == "Mesh / wireless layer failure"
    assert result.confidence == "high"


def test_one_fixed_child_is_ambiguous(make_binding, make_observation, make_set):
    gateway = make_binding("g", "Gateway A", ROLE_GATEWAY)
    mesh = make_binding("m", "Mesh Node A", ROLE_MESH_NODE, parent_id="g")
    client = make_binding("c", "Fixed Client A", ROLE_FIXED_CLIENT, parent_id="m")
    result = classify(
        make_set(
            [
                make_observation(gateway, True),
                make_observation(mesh, True),
                make_observation(client, False),
            ]
        )
    )
    assert result.diagnosis == "Mesh Node A downstream path/client failure"
    assert result.confidence == "medium"


def test_two_fixed_children_support_forwarding_path(make_binding, make_observation, make_set):
    gateway = make_binding("g", "Gateway A", ROLE_GATEWAY)
    mesh = make_binding("m", "Mesh Node A", ROLE_MESH_NODE, parent_id="g")
    a = make_binding("a", "Fixed Client A", ROLE_FIXED_CLIENT, parent_id="m")
    b = make_binding("b", "Fixed Client B", ROLE_FIXED_CLIENT, parent_id="m")
    result = classify(
        make_set(
            [
                make_observation(gateway, True),
                make_observation(mesh, True),
                make_observation(a, False),
                make_observation(b, False),
            ]
        )
    )
    assert result.diagnosis == "Mesh Node A downstream/forwarding path failure"
    assert result.confidence == "high"


def test_localized_latency_uses_parent_and_sibling_context(
    make_binding, make_observation, make_set
):
    gateway = make_binding("g", "Gateway A", ROLE_GATEWAY)
    a = make_binding("a", "Mesh Node A", ROLE_MESH_NODE, parent_id="g")
    b = make_binding("b", "Mesh Node B", ROLE_MESH_NODE, parent_id="g")
    observations = make_set(
        [
            make_observation(gateway, True),
            make_observation(a, True, response_ms=35, baseline_state="degraded", baseline_ratio=7.0),
            make_observation(b, True),
        ]
    )
    result = classify(
        observations,
        degraded_nodes={
            "g": assessment(),
            "a": assessment("degraded", sustained=True, median=5.0, ratio=7.0),
            "b": assessment(),
        },
    )
    assert result.diagnosis == "Mesh Node A latency degradation"
    assert result.confidence == "high"
    assert any("Sibling" in line for line in result.evidence)


def test_two_degraded_mesh_siblings_become_layer_degradation(
    make_binding, make_observation, make_set
):
    gateway = make_binding("g", "Gateway A", ROLE_GATEWAY)
    a = make_binding("a", "Mesh Node A", ROLE_MESH_NODE, parent_id="g")
    b = make_binding("b", "Mesh Node B", ROLE_MESH_NODE, parent_id="g")
    result = classify(
        make_set([make_observation(gateway), make_observation(a), make_observation(b)]),
        degraded_nodes={
            "g": assessment(),
            "a": assessment("degraded", sustained=True, ratio=5.0),
            "b": assessment("degraded", sustained=True, ratio=4.0),
        },
    )
    assert result.diagnosis == "Mesh / wireless layer latency degradation"


def test_degraded_ancestor_suppresses_descendant_degradation(
    make_binding, make_observation, make_set
):
    gateway = make_binding("g", "Gateway A", ROLE_GATEWAY)
    node = make_binding("n", "Network Node A", ROLE_NETWORK_NODE, parent_id="g")
    mesh = make_binding("m", "Mesh Node A", ROLE_MESH_NODE, parent_id="n")
    result = classify(
        make_set([make_observation(gateway), make_observation(node), make_observation(mesh)]),
        degraded_nodes={
            "g": assessment(),
            "n": assessment("degraded", sustained=True, ratio=4.0),
            "m": assessment("degraded", sustained=True, ratio=5.0),
        },
    )
    assert result.diagnosis == "Network Node A latency degradation"


def test_ipv4_failure_is_separated_from_healthy_ipv6(
    make_binding, make_observation, make_set
):
    v4a = make_binding("4a", "IPv4 A", ROLE_IPV4_CONTROL)
    v4b = make_binding("4b", "IPv4 B", ROLE_IPV4_CONTROL)
    v6 = make_binding("6a", "IPv6 A", ROLE_IPV6_CONTROL)
    result = classify(
        make_set(
            [
                make_observation(v4a, False),
                make_observation(v4b, False),
                make_observation(v6, True),
            ]
        )
    )
    assert result.diagnosis == "General IPv4 failure"
    assert result.confidence == "high"


def test_wan_failure_with_reachable_gateway(make_binding, make_observation, make_set):
    gateway = make_binding("g", "Gateway A", ROLE_GATEWAY)
    v4 = make_binding("4", "IPv4 A", ROLE_IPV4_CONTROL)
    v6 = make_binding("6", "IPv6 A", ROLE_IPV6_CONTROL)
    result = classify(
        make_set(
            [make_observation(gateway, True), make_observation(v4, False), make_observation(v6, False)]
        )
    )
    assert result.diagnosis == "Upstream Internet / WAN failure"
    assert result.confidence == "high"


def test_local_dns_failure_requires_independent_dns_healthy(
    make_binding, make_observation, make_set
):
    internet = make_binding("i", "Internet A", ROLE_IPV4_CONTROL)
    neutral = make_binding("n", "Independent DNS", ROLE_DNS_NEUTRAL)
    local = make_binding("l", "Local DNS", ROLE_DNS_LOCAL)
    result = classify(
        make_set(
            [make_observation(internet, True), make_observation(neutral, True), make_observation(local, False)]
        )
    )
    assert result.diagnosis == "Local DNS forwarder/upstream failure"


def test_service_path_failure_uses_service_group(make_binding, make_observation, make_set):
    internet = make_binding("i", "Internet A", ROLE_IPV4_CONTROL)
    neutral = make_binding("n", "Independent DNS", ROLE_DNS_NEUTRAL)
    service_dns = make_binding("sd", "Service DNS", ROLE_SERVICE_DNS, service="Service A")
    service_path = make_binding("sp", "Service Path", ROLE_SERVICE_PATH, service="Service A")
    result = classify(
        make_set(
            [
                make_observation(internet, True),
                make_observation(neutral, True),
                make_observation(service_dns, False),
                make_observation(service_path, False),
            ]
        )
    )
    assert result.diagnosis == "Service A routing/path failure"


def test_https_specific_failure(make_binding, make_observation, make_set):
    internet = make_binding("i", "Internet A", ROLE_IPV4_CONTROL)
    neutral = make_binding("n", "Independent DNS", ROLE_DNS_NEUTRAL)
    https = make_binding("h", "HTTPS A", ROLE_HTTPS_CONTROL)
    result = classify(
        make_set(
            [make_observation(internet, True), make_observation(neutral, True), make_observation(https, False)]
        )
    )
    assert result.diagnosis == "HTTPS-specific failure"


def test_independent_local_and_internet_faults_are_concurrent(
    make_binding, make_observation, make_set
):
    gateway = make_binding("g", "Gateway A", ROLE_GATEWAY)
    lan = make_binding("l", "LAN Control A", ROLE_LAN_CONTROL)
    v4a = make_binding("4a", "IPv4 A", ROLE_IPV4_CONTROL)
    v4b = make_binding("4b", "IPv4 B", ROLE_IPV4_CONTROL)
    v6 = make_binding("6", "IPv6 A", ROLE_IPV6_CONTROL)
    result = classify(
        make_set(
            [
                make_observation(gateway, True),
                make_observation(lan, False),
                make_observation(v4a, False),
                make_observation(v4b, False),
                make_observation(v6, True),
            ]
        )
    )
    assert result.diagnosis == MULTIPLE
    assert len(result.root_causes) == 2
