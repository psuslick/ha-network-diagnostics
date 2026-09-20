from __future__ import annotations

from custom_components.network_diagnostics.const import *
from custom_components.network_diagnostics.observations import MonitorBinding
from custom_components.network_diagnostics.validation import validate_bindings


def binding(name, role, *, label=None, group=None, monitor_type="ping", target="1.1.1.1"):
    return MonitorBinding(
        monitor_id=name,
        name=name,
        role=role,
        group=group,
        label=label or name,
        status_entity=f"sensor.{name}_status",
        monitor_type=monitor_type,
        target=target,
        target_fingerprint="f",
    )


def test_dns_role_requires_dns_monitor_type_when_known():
    warnings, blockers = validate_bindings([
        binding("Neutral", ROLE_DNS_NEUTRAL, monitor_type="ping", target="1.1.1.1")
    ])
    assert not warnings
    assert blockers


def test_literal_ip_family_mismatch_is_blocker():
    _, blockers = validate_bindings([
        binding("IPv4", ROLE_IPV4, target="2606:4700:4700::1111")
    ])
    assert any("IPv6" in item for item in blockers)


def test_mesh_child_must_reference_known_parent_label():
    _, blockers = validate_bindings([
        binding("Sarah", ROLE_MESH, label="Sarah Room", target="192.168.1.20"),
        binding("Child", ROLE_MESH_CHILD, group="Library", target="192.168.1.30"),
    ])
    assert any("Library" in item for item in blockers)


def test_service_dns_without_path_is_warning_not_blocker():
    warnings, blockers = validate_bindings([
        binding("Resolver", ROLE_SERVICE_DNS, group="ExampleDNS", monitor_type="dns", target="example.com")
    ])
    assert warnings
    assert not blockers


def test_https_role_requires_https_url_when_url_known():
    _, blockers = validate_bindings([
        binding("Web", ROLE_HTTPS, monitor_type="http", target="http://example.com")
    ])
    assert blockers


def test_duplicate_non_dns_sources_are_blockers():
    first = binding("IPv4 A", ROLE_IPV4, monitor_type="ping", target="1.1.1.1")
    second = MonitorBinding(
        monitor_id="IPv4 B",
        name="IPv4 B",
        role=ROLE_IPV4,
        group=None,
        label="IPv4 B",
        status_entity="sensor.ipv4_b_status",
        monitor_type="ping",
        target="1.1.1.1",
        target_fingerprint=first.target_fingerprint,
    )
    _, blockers = validate_bindings([first, second])
    assert any("not independent" in item for item in blockers)


def test_same_dns_query_target_is_not_assumed_duplicate_resolver():
    first = binding("DNS 1", ROLE_SERVICE_DNS, group="ExampleDNS", monitor_type="dns", target="example.com")
    second = MonitorBinding(
        monitor_id="DNS 2", name="DNS 2", role=ROLE_SERVICE_DNS, group="ExampleDNS",
        label="DNS 2", status_entity="sensor.dns_2_status", monitor_type="dns",
        target="example.com", target_fingerprint=first.target_fingerprint,
    )
    warnings, blockers = validate_bindings([first, second])
    assert not any("not independent" in item for item in blockers)
