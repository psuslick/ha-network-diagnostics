from __future__ import annotations

from custom_components.network_diagnostics.kuma_ids import split_kuma_unique_id


def test_response_time_suffix_is_not_split_at_final_underscore():
    assert split_kuma_unique_id("entry_1_response_time", "entry") == ("1", "response_time")


def test_status_suffix():
    assert split_kuma_unique_id("entry_42_status", "entry") == ("42", "status")


def test_v1_style_monitor_name_with_underscores():
    assert split_kuma_unique_id("entry_my_router_name_response_time", "entry") == (
        "my_router_name",
        "response_time",
    )


def test_unknown_suffix_is_rejected():
    assert split_kuma_unique_id("entry_1_uptime_1_day", "entry") is None


def test_wrong_entry_is_rejected():
    assert split_kuma_unique_id("other_1_status", "entry") is None
