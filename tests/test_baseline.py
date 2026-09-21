from datetime import UTC, datetime, timedelta

from custom_components.network_diagnostics.baseline import BaselineTracker


def test_baseline_learns_then_detects_sustained_degradation():
    tracker = BaselineTracker(
        window_minutes=60,
        min_samples=4,
        ratio_threshold=2.0,
        min_delta_ms=10,
        degradation_seconds=60,
    )
    start = datetime(2026, 1, 1, tzinfo=UTC)
    for index, value in enumerate((5.0, 6.0, 5.0, 6.0)):
        assessment = tracker.update(
            "node-a", observed_at=start + timedelta(seconds=index * 30), response_ms=value
        )
    assert assessment.state == "learning"

    first = tracker.update(
        "node-a", observed_at=start + timedelta(seconds=120), response_ms=30.0
    )
    assert first.abnormal is True
    assert first.sustained is False

    second = tracker.update(
        "node-a", observed_at=start + timedelta(seconds=150), response_ms=32.0
    )
    assert second.abnormal is True
    assert second.sustained is False

    third = tracker.update(
        "node-a", observed_at=start + timedelta(seconds=180), response_ms=31.0
    )
    assert third.sustained is True
    assert third.state == "degraded"
    assert third.median_ms <= 6.0


def test_same_timestamp_is_not_recorded_twice():
    tracker = BaselineTracker(
        window_minutes=60,
        min_samples=4,
        ratio_threshold=2.0,
        min_delta_ms=10,
        degradation_seconds=60,
    )
    at = datetime(2026, 1, 1, tzinfo=UTC)
    tracker.update("node-a", observed_at=at, response_ms=5.0)
    tracker.update("node-a", observed_at=at, response_ms=5.0)
    assert len(tracker.samples["node-a"]) == 1


def test_unknown_monitors_are_removed_from_ram():
    tracker = BaselineTracker(
        window_minutes=60,
        min_samples=4,
        ratio_threshold=2.0,
        min_delta_ms=10,
        degradation_seconds=60,
    )
    tracker.update(
        "old-node", observed_at=datetime(2026, 1, 1, tzinfo=UTC), response_ms=5.0
    )
    tracker.remove_unknown({"new-node"})
    assert "old-node" not in tracker.samples
