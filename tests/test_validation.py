from custom_components.network_diagnostics.const import (
    ROLE_DNS_NEUTRAL,
    ROLE_FIXED_CLIENT,
    ROLE_GATEWAY,
    ROLE_IPV4_CONTROL,
    ROLE_IPV6_CONTROL,
    ROLE_MESH_NODE,
    ROLE_SERVICE_DNS,
    ROLE_SERVICE_PATH,
)
from custom_components.network_diagnostics.validation import (
    coverage_capabilities,
    coverage_gaps,
    validate_bindings,
)


def test_duplicate_independent_endpoint_is_blocking(make_binding):
    bindings = [
        make_binding("a", "IPv4 A", ROLE_IPV4_CONTROL, target_fingerprint="same"),
        make_binding("b", "IPv4 B", ROLE_IPV4_CONTROL, target_fingerprint="same"),
    ]
    _warnings, blockers = validate_bindings(bindings)
    assert any("distinct endpoints" in item for item in blockers)
    assert coverage_capabilities(bindings)["ipv4_specific_failure"] is False


def test_ip_family_mismatch_is_blocking(make_binding):
    binding = make_binding(
        "v6", "Control A", ROLE_IPV4_CONTROL, target_ip_version=6
    )
    _warnings, blockers = validate_bindings([binding])
    assert any("IPv6 literal" in item for item in blockers)


def test_service_roles_require_a_group(make_binding):
    binding = make_binding("dns", "Service DNS A", ROLE_SERVICE_DNS, monitor_type="dns")
    _warnings, blockers = validate_bindings([binding])
    assert any("service group" in item for item in blockers)


def test_unknown_target_is_warning_not_blocker(make_binding):
    binding = make_binding("a", "IPv4 A", ROLE_IPV4_CONTROL, target_fingerprint=None)
    warnings, blockers = validate_bindings([binding])
    assert any("independence cannot be verified" in item for item in warnings)
    assert not blockers


def test_full_generic_evidence_reports_key_capabilities(make_binding):
    bindings = [
        make_binding("g", "Gateway A", ROLE_GATEWAY, target_fingerprint="g"),
        make_binding("m", "Mesh A", ROLE_MESH_NODE, parent_id="g", target_fingerprint="m"),
        make_binding("c1", "Client A", ROLE_FIXED_CLIENT, parent_id="m", target_fingerprint="c1"),
        make_binding("c2", "Client B", ROLE_FIXED_CLIENT, parent_id="m", target_fingerprint="c2"),
        make_binding("v4a", "IPv4 A", ROLE_IPV4_CONTROL, target_fingerprint="v4a"),
        make_binding("v4b", "IPv4 B", ROLE_IPV4_CONTROL, target_fingerprint="v4b"),
        make_binding("v6a", "IPv6 A", ROLE_IPV6_CONTROL, target_fingerprint="v6a"),
        make_binding("v6b", "IPv6 B", ROLE_IPV6_CONTROL, target_fingerprint="v6b"),
        make_binding("d", "DNS A", ROLE_DNS_NEUTRAL, monitor_type="dns", target_fingerprint="d"),
        make_binding("sd", "Service DNS", ROLE_SERVICE_DNS, service="Service A", monitor_type="dns", target_fingerprint="sd"),
        make_binding("sp", "Service Path", ROLE_SERVICE_PATH, service="Service A", target_fingerprint="sp"),
    ]
    caps = coverage_capabilities(bindings)
    assert caps["gateway_failure"]
    assert caps["topology_node_localization"]
    assert caps["downstream_path_discrimination"]
    assert caps["adaptive_latency_degradation"]
    assert caps["ipv4_specific_failure"]
    assert caps["ipv6_specific_failure"]
    assert caps["service_dns_path_separation"]


def test_coverage_gaps_are_advisory(make_binding):
    caps = coverage_capabilities([make_binding("g", "Gateway A", ROLE_GATEWAY)])
    gaps = coverage_gaps(caps)
    assert gaps
    assert not caps["ipv4_specific_failure"]
