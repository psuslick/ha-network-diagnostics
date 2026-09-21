from custom_components.network_diagnostics.kuma_ids import split_kuma_unique_id


def test_status_unique_id():
    assert split_kuma_unique_id("entry_42_status", "entry") == ("42", "status")


def test_longest_suffix_wins():
    assert split_kuma_unique_id("entry_42_avg_response_time_1d", "entry") == (
        "42",
        "avg_response_time_1d",
    )


def test_unknown_suffix_is_ignored():
    assert split_kuma_unique_id("entry_42_something_else", "entry") is None
