from __future__ import annotations

from custom_components.network_diagnostics.const import (
    ROLE_DNS_NEUTRAL,
    ROLE_GATEWAY,
    ROLE_MESH,
    ROLE_MESH_CHILD,
    ROLE_SERVICE_DNS,
    ROLE_SERVICE_PATH,
)
from custom_components.network_diagnostics.roles import parse_monitor_name


def test_explicit_gateway_marker():
    parsed = parse_monitor_name("[ND:gateway] Main router")
    assert parsed is not None
    assert parsed.role == ROLE_GATEWAY
    assert parsed.label == "Main router"
    assert parsed.source == "marker"


def test_explicit_mesh_marker():
    parsed = parse_monitor_name("[ND:mesh] Upstairs AP")
    assert parsed is not None
    assert parsed.role == ROLE_MESH
    assert parsed.label == "Upstairs AP"


def test_explicit_service_dns_marker():
    parsed = parse_monitor_name("[ND:service:NextDNS:dns] Resolver 1")
    assert parsed is not None
    assert parsed.role == ROLE_SERVICE_DNS
    assert parsed.group == "NextDNS"


def test_explicit_service_path_marker():
    parsed = parse_monitor_name("[ND:service:NextDNS:path] IPv6 1")
    assert parsed is not None
    assert parsed.role == ROLE_SERVICE_PATH
    assert parsed.group == "NextDNS"


def test_legacy_current_install_names_are_supported():
    assert parse_monitor_name("Orbi LAN").role == ROLE_GATEWAY
    assert parse_monitor_name("Orbi Sarah Room").role == ROLE_MESH
    assert parse_monitor_name("DNS via Cloudflare").role == ROLE_DNS_NEUTRAL


def test_unknown_monitor_is_unassigned():
    assert parse_monitor_name("NAS homepage") is None


def test_invalid_marker_is_not_guessed():
    assert parse_monitor_name("[ND:totally-made-up] Something") is None


def test_mesh_child_marker():
    parsed = parse_monitor_name("[ND:mesh-child:Sarah Room] Wired control")
    assert parsed is not None
    assert parsed.role == ROLE_MESH_CHILD
    assert parsed.group == "Sarah Room"
    assert parsed.label == "Wired control"


def test_full_orbi_nextdns_profile_monitor_names_are_recognized():
    names = (
        "Orbi LAN",
        "Orbi Satellite 1",
        "Orbi Sarah Room",
        "Internet IPv4",
        "Google IPv4",
        "Internet IPv6",
        "Google IPv6",
        "DNS via Cloudflare",
        "DNS via Orbi",
        "Internet HTTPS",
        "DNS via NextDNS 1",
        "DNS via NextDNS 2",
        "NextDNS IPv4 1",
        "NextDNS IPv4 2",
        "NextDNS IPv6 1",
        "NextDNS IPv6 2",
        "NextDNS TCP 443 1",
        "NextDNS TCP 443 2",
    )
    assert all(parse_monitor_name(name) is not None for name in names)
