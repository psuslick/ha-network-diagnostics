from __future__ import annotations

from custom_components.network_diagnostics.targets import sanitize_target, target_fingerprint


def test_http_target_strips_credentials_path_query_and_fragment():
    assert sanitize_target("https://user:secret@example.com:8443/private/token?api=secret#x") == "https://example.com:8443"


def test_ipv6_url_target_is_bracketed():
    assert sanitize_target("https://[2001:db8::1]:8443/private") == "https://[2001:db8::1]:8443"


def test_non_url_target_is_preserved():
    assert sanitize_target("192.168.1.20") == "192.168.1.20"


def test_target_fingerprint_is_stable_and_hides_raw_value():
    first = target_fingerprint("https://example.com/token?secret=abc")
    second = target_fingerprint("https://example.com/token?secret=abc")
    assert first == second
    assert "secret" not in first
    assert len(first) == 16
