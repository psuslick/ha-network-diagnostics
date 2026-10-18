"""Bounded RAM-only detection of intermittent monitor reachability.

This tracks *reported* Kuma status changes, not individual missed packets.
Missing/stale evidence breaks continuity, so it cannot manufacture an outage.
"""

from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta


@dataclass(frozen=True, slots=True)
class QualityAssessment:
    recent_outages: int = 0
    flapping: bool = False
    last_recovery: str | None = None


class QualityTracker:
    """Retain only recent recovery events, never a second raw historian."""

    def __init__(self, *, window_minutes: int = 15, minimum_outages: int = 2) -> None:
        self.window = timedelta(minutes=max(1, window_minutes))
        self.minimum_outages = max(2, minimum_outages)
        self.previous: dict[str, bool] = {}
        self.down_since: dict[str, datetime] = {}
        self.recoveries: dict[str, deque[datetime]] = defaultdict(lambda: deque(maxlen=32))

    def update(
        self, monitor_id: str, *, observed_at: datetime, status: bool | None
    ) -> QualityAssessment:
        if observed_at.tzinfo is None:
            observed_at = observed_at.replace(tzinfo=UTC)
        recoveries = self.recoveries[monitor_id]
        cutoff = observed_at - self.window
        while recoveries and recoveries[0] < cutoff:
            recoveries.popleft()

        if status is None:
            # An unknown interval cannot prove that a subsequent status change
            # occurred, and must never be counted as a network outage.
            self.previous.pop(monitor_id, None)
            self.down_since.pop(monitor_id, None)
        else:
            previous = self.previous.get(monitor_id)
            if previous is True and status is False:
                self.down_since[monitor_id] = observed_at
            elif previous is False and status is True:
                if monitor_id in self.down_since:
                    recoveries.append(observed_at)
                self.down_since.pop(monitor_id, None)
            self.previous[monitor_id] = status

        return QualityAssessment(
            recent_outages=len(recoveries),
            flapping=len(recoveries) >= self.minimum_outages,
            last_recovery=recoveries[-1].isoformat() if recoveries else None,
        )

    def remove_unknown(self, valid_ids: set[str]) -> None:
        for mapping in (self.previous, self.down_since, self.recoveries):
            for monitor_id in list(mapping):
                if monitor_id not in valid_ids:
                    mapping.pop(monitor_id, None)
