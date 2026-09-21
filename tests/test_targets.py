from custom_components.network_diagnostics.targets import (
    normalized_target_identity,
    select_raw_target,
    target_fingerprint,
    target_ip_version,
)


def test_hostname_and_port_identity_is_preserved():
    raw = select_raw_target(hostname="198.51.100.20", port="443")
    assert raw == "198.51.100.20:443"
    assert normalized_target_identity(raw) == "198.51.100.20:443"
    assert target_ip_version(raw) == 4


def test_url_identity_discards_credentials_path_query_and_fragment():
    raw = "https://user:secret@example.com:8443/private?q=token#fragment"
    assert normalized_target_identity(raw) == "https://example.com:8443"
    assert "secret" not in target_fingerprint(raw)


def test_documentation_ipv6_literal_is_detected():
    assert target_ip_version("2001:db8::10") == 6
    assert target_ip_version("[2001:db8::10]:443") == 6


def test_invalid_or_empty_targets_do_not_create_identity():
    assert select_raw_target() is None
    assert normalized_target_identity("") is None
    assert target_fingerprint(None) is None


def test_dns_query_hostname_is_never_treated_as_resolver_endpoint():
    from custom_components.network_diagnostics.targets import monitor_target_semantics

    fingerprint, ip_version = monitor_target_semantics("dns", "example.com:53")
    assert fingerprint is None
    assert ip_version is None


def test_non_dns_monitor_keeps_endpoint_semantics():
    from custom_components.network_diagnostics.targets import monitor_target_semantics

    fingerprint, ip_version = monitor_target_semantics("ping", "198.51.100.20")
    assert fingerprint is not None
    assert ip_version == 4
