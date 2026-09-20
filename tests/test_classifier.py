from __future__ import annotations

from custom_components.network_diagnostics.classifier import (
    HEALTHY,
    MIXED,
    MONITORING_INCOMPLETE,
    MULTIPLE,
    classify,
)
from custom_components.network_diagnostics.const import *
from custom_components.network_diagnostics.observations import (
    MonitorBinding,
    Observation,
    ObservationSet,
)


def obs(name: str, role: str, state: bool | None, *, group: str | None = None, response: float | None = 5.0):
    binding = MonitorBinding(
        monitor_id=name,
        name=name,
        role=role,
        group=group,
        label=name,
        status_entity=f"sensor.{name.lower().replace(' ', '_')}_status",
        response_entity=f"sensor.{name.lower().replace(' ', '_')}_response",
    )
    raw = "up" if state is True else "down" if state is False else "unknown"
    return Observation(binding, state, raw, response, True, 1.0)


def healthy_set() -> ObservationSet:
    return ObservationSet(
        observations=[
            obs("Gateway", ROLE_GATEWAY, True, response=1),
            obs("Satellite 1", ROLE_MESH, True, response=3),
            obs("Sarah Room", ROLE_MESH, True, response=3),
            obs("IPv4 A", ROLE_IPV4, True),
            obs("IPv4 B", ROLE_IPV4, True),
            obs("IPv6 A", ROLE_IPV6, True),
            obs("IPv6 B", ROLE_IPV6, True),
            obs("Cloudflare DNS", ROLE_DNS_NEUTRAL, True),
            obs("Orbi DNS", ROLE_DNS_LOCAL, True),
            obs("HTTPS", ROLE_HTTPS, True),
            obs("NextDNS DNS 1", ROLE_SERVICE_DNS, True, group="NextDNS"),
            obs("NextDNS DNS 2", ROLE_SERVICE_DNS, True, group="NextDNS"),
            obs("NextDNS Path 1", ROLE_SERVICE_PATH, True, group="NextDNS"),
            obs("NextDNS Path 2", ROLE_SERVICE_PATH, True, group="NextDNS"),
        ]
    )


def replace_state(data: ObservationSet, name: str, state: bool | None) -> None:
    out = []
    for item in data.observations:
        if item.binding.name == name:
            out.append(obs(item.binding.name, item.binding.role, state, group=item.binding.group, response=item.response_ms))
        else:
            out.append(item)
    data.observations = out


def test_healthy():
    result = classify(healthy_set())
    assert result.diagnosis == HEALTHY
    assert result.confidence == "high"


def test_provider_stale_blocks_diagnosis():
    data = healthy_set()
    data.provider_fresh = False
    data.provider_age_seconds = 400
    result = classify(data)
    assert result.diagnosis == MONITORING_INCOMPLETE


def test_monitoring_gap_blocks_healthy():
    data = healthy_set()
    data.monitoring_gaps.append("Gateway status unavailable")
    assert classify(data).diagnosis == MONITORING_INCOMPLETE


def test_gateway_monitor_down_but_internet_healthy_is_management_reachability():
    data = healthy_set()
    replace_state(data, "Gateway", False)
    data.observations.append(obs("Wired LAN Control", ROLE_LAN_CONTROL, True))
    result = classify(data)
    assert result.diagnosis == "Gateway management/reachability failure"
    assert result.confidence == "medium"
    assert result.contradictions


def test_gateway_management_failure_does_not_hide_independent_provider_failure():
    data = healthy_set()
    replace_state(data, "Gateway", False)
    data.observations.append(obs("Wired LAN Control", ROLE_LAN_CONTROL, True))
    for name in ("NextDNS DNS 1", "NextDNS DNS 2", "NextDNS Path 1", "NextDNS Path 2"):
        replace_state(data, name, False)
    result = classify(data)
    assert result.diagnosis == MULTIPLE
    assert {cause.domain for cause in result.root_causes} == {"local", "service:NextDNS"}


def test_gateway_failure_with_lan_control_and_external_loss():
    data = healthy_set()
    replace_state(data, "Gateway", False)
    data.observations.append(obs("Wired LAN Control", ROLE_LAN_CONTROL, True))
    for name in ("IPv4 A", "IPv4 B", "IPv6 A", "IPv6 B"):
        replace_state(data, name, False)
    result = classify(data)
    assert result.diagnosis == "Gateway/router failure"
    assert "wired lan control" in result.evidence[0].lower()


def test_gateway_path_ambiguity_without_lan_control():
    data = healthy_set()
    replace_state(data, "Gateway", False)
    assert classify(data).diagnosis == "Gateway / local path failure"


def test_gateway_and_lan_control_down():
    data = healthy_set()
    replace_state(data, "Gateway", False)
    data.observations.append(obs("Wired LAN Control", ROLE_LAN_CONTROL, False))
    assert classify(data).diagnosis == "Local LAN / Home Assistant path failure"


def test_one_mesh_node_down():
    data = healthy_set()
    replace_state(data, "Sarah Room", False)
    result = classify(data)
    assert result.diagnosis == "Sarah Room unreachable"
    assert result.confidence == "high"


def test_both_mesh_nodes_down():
    data = healthy_set()
    replace_state(data, "Satellite 1", False)
    replace_state(data, "Sarah Room", False)
    assert classify(data).diagnosis == "Mesh satellite/AP layer failure"


def test_mesh_latency_degradation():
    result = classify(healthy_set(), degraded_mesh={"Sarah Room"})
    assert result.diagnosis == "Sarah Room latency degradation"


def test_general_ipv4_failure():
    data = healthy_set()
    replace_state(data, "IPv4 A", False)
    replace_state(data, "IPv4 B", False)
    assert classify(data).diagnosis == "General IPv4 failure"


def test_general_ipv6_failure():
    data = healthy_set()
    replace_state(data, "IPv6 A", False)
    replace_state(data, "IPv6 B", False)
    assert classify(data).diagnosis == "General IPv6 failure"


def test_upstream_wan_failure_suppresses_dns_https_symptoms():
    data = healthy_set()
    for name in ("IPv4 A", "IPv4 B", "IPv6 A", "IPv6 B", "Cloudflare DNS", "Orbi DNS", "HTTPS"):
        replace_state(data, name, False)
    result = classify(data)
    assert result.diagnosis == "Upstream Internet / WAN failure"
    assert "Cloudflare DNS" in result.downstream
    assert "HTTPS" in result.downstream


def test_partial_internet_target_path_failure():
    data = healthy_set()
    replace_state(data, "IPv4 A", False)
    assert classify(data).diagnosis == "Partial Internet target/path failure"


def test_general_dns_failure():
    data = healthy_set()
    replace_state(data, "Cloudflare DNS", False)
    replace_state(data, "Orbi DNS", False)
    assert classify(data).diagnosis == "General DNS failure"


def test_local_dns_forwarder_failure():
    data = healthy_set()
    replace_state(data, "Orbi DNS", False)
    assert classify(data).diagnosis == "Local DNS forwarder/upstream failure"


def test_nextdns_routing_path_failure():
    data = healthy_set()
    for name in ("NextDNS DNS 1", "NextDNS DNS 2", "NextDNS Path 1", "NextDNS Path 2"):
        replace_state(data, name, False)
    result = classify(data)
    assert result.diagnosis == "NextDNS routing/path failure"
    assert any("neutral DNS" in x for x in result.evidence)


def test_nextdns_dns_service_failure():
    data = healthy_set()
    replace_state(data, "NextDNS DNS 1", False)
    replace_state(data, "NextDNS DNS 2", False)
    assert classify(data).diagnosis == "NextDNS DNS-service failure"


def test_partial_nextdns_endpoint_failure():
    data = healthy_set()
    replace_state(data, "NextDNS Path 1", False)
    assert classify(data).diagnosis == "Partial NextDNS endpoint/path failure"


def test_https_specific_failure():
    data = healthy_set()
    replace_state(data, "HTTPS", False)
    assert classify(data).diagnosis == "HTTPS-specific failure"


def test_mesh_plus_provider_failure_is_multiple():
    data = healthy_set()
    replace_state(data, "Sarah Room", False)
    for name in ("NextDNS DNS 1", "NextDNS DNS 2", "NextDNS Path 1", "NextDNS Path 2"):
        replace_state(data, name, False)
    assert classify(data).diagnosis == MULTIPLE


def test_failed_lan_control_is_localized_when_gateway_is_healthy():
    data = healthy_set()
    data.observations.append(obs("Wired LAN Control", ROLE_LAN_CONTROL, False))
    result = classify(data)
    assert result.diagnosis == "LAN control endpoint/path failure"
    assert result.confidence == "medium"


def test_missing_core_coverage_never_claims_healthy():
    data = ObservationSet(
        observations=[
            obs("Gateway", ROLE_GATEWAY, True),
            obs("IPv4", ROLE_IPV4, True),
        ]
    )
    result = classify(data)
    assert result.diagnosis == MONITORING_INCOMPLETE
    assert result.confidence == "insufficient"
    assert result.coverage_gaps


def test_down_status_is_authoritative_even_without_response_time():
    data = healthy_set()
    out = []
    for item in data.observations:
        if item.binding.name == "Sarah Room":
            out.append(obs("Sarah Room", ROLE_MESH, False, response=None))
        else:
            out.append(item)
    data.observations = out
    result = classify(data)
    assert result.diagnosis == "Sarah Room unreachable"
    assert result.confidence == "high"


def test_single_ipv4_control_failure_is_medium_confidence():
    data = healthy_set()
    data.observations = [item for item in data.observations if item.binding.name != "IPv4 B"]
    replace_state(data, "IPv4 A", False)
    result = classify(data)
    assert result.diagnosis == "General IPv4 failure"
    assert result.confidence == "medium"


def test_single_neutral_dns_control_general_failure_is_medium_confidence():
    data = healthy_set()
    # A general DNS failure with only one independent neutral DNS control cannot
    # justify high evidence strength. Local DNS is a separate downstream path.
    replace_state(data, "Cloudflare DNS", False)
    replace_state(data, "Orbi DNS", False)
    result = classify(data)
    assert result.diagnosis == "General DNS failure"
    assert result.confidence == "medium"


def test_one_fixed_mesh_child_down_is_ambiguous_path_or_client():
    data = healthy_set()
    data.observations.append(
        obs("Sarah wired control", ROLE_MESH_CHILD, False, group="Sarah Room")
    )
    result = classify(data)
    assert result.diagnosis == "Sarah Room downstream path/client failure"
    assert result.confidence == "medium"


def test_two_fixed_mesh_children_down_support_backhaul_path_failure():
    data = healthy_set()
    data.observations.extend(
        [
            obs("Sarah wired control A", ROLE_MESH_CHILD, False, group="Sarah Room"),
            obs("Sarah wired control B", ROLE_MESH_CHILD, False, group="Sarah Room"),
        ]
    )
    result = classify(data)
    assert result.diagnosis == "Sarah Room downstream/backhaul path failure"
    assert result.confidence == "high"
