from datetime import UTC, datetime, timedelta

from custom_components.network_diagnostics.quality import QualityTracker


def _at(seconds):
    return datetime(2026, 1, 1, tzinfo=UTC) + timedelta(seconds=seconds)


def test_two_short_outages_become_intermitttent_even_after_recovery():
    tracker = QualityTracker()
    assert not tracker.update("a", observed_at=_at(0), status=True).flapping
    tracker.update("a", observed_at=_at(10), status=False)
    assert tracker.update("a", observed_at=_at(12), status=True).recent_outages == 1
    tracker.update("a", observed_at=_at(22), status=False)
    recovered = tracker.update("a", observed_at=_at(24), status=True)
    assert recovered.flapping
    assert recovered.recent_outages == 2
    assert recovered.last_recovery == _at(24).isoformat()


def test_repeated_same_state_does_not_count_as_a_drop():
    tracker = QualityTracker()
    for second in range(40):
        result = tracker.update("a", observed_at=_at(second), status=True)
    assert result.recent_outages == 0
    assert not result.flapping


def test_stale_or_unknown_breaks_continuity_not_a_false_outage():
    tracker = QualityTracker()
    tracker.update("a", observed_at=_at(0), status=True)
    tracker.update("a", observed_at=_at(1), status=False)
    tracker.update("a", observed_at=_at(2), status=None)
    assert tracker.update("a", observed_at=_at(3), status=True).recent_outages == 0


def test_flap_expires_when_window_elapses():
    tracker = QualityTracker(window_minutes=1)
    for second, status in [(0, True), (1, False), (2, True), (3, False), (4, True)]:
        last = tracker.update("a", observed_at=_at(second), status=status)
    assert last.flapping
    assert not tracker.update("a", observed_at=_at(65), status=True).flapping


def test_monitors_are_isolated_and_removed_without_history_leak():
    tracker = QualityTracker()
    tracker.update("first", observed_at=_at(0), status=True)
    tracker.update("first", observed_at=_at(1), status=False)
    tracker.update("first", observed_at=_at(2), status=True)
    assert tracker.update("second", observed_at=_at(2), status=True).recent_outages == 0
    tracker.remove_unknown({"second"})
    assert "first" not in tracker.previous
    assert "first" not in tracker.recoveries

