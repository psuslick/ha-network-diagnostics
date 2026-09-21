"""Bounded in-memory response-time baselines for degradation detection."""

from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from statistics import median


@dataclass(frozen=True, slots=True)
class BaselineAssessment:
    state: str
    sample_count: int
    median_ms: float | None
    mad_ms: float | None
    ratio: float | None
    delta_ms: float | None
    abnormal: bool
    sustained: bool
    abnormal_seconds: float | None


class BaselineTracker:
    """Maintain small RAM-only rolling windows keyed by stable monitor identity."""

    def __init__(
        self,
        *,
        window_minutes: int,
        min_samples: int,
        ratio_threshold: float,
        min_delta_ms: float,
        degradation_seconds: int,
        max_samples_per_monitor: int = 512,
    ) -> None:
        self.window = timedelta(minutes=max(5, window_minutes))
        self.min_samples = max(4, min_samples)
        self.ratio_threshold = max(1.1, ratio_threshold)
        self.min_delta_ms = max(1.0, min_delta_ms)
        self.degradation_seconds = max(0, degradation_seconds)
        self.max_samples = max(32, max_samples_per_monitor)
        self.samples: dict[str, deque[tuple[datetime, float]]] = defaultdict(
            lambda: deque(maxlen=self.max_samples)
        )
        self.last_sample_at: dict[str, datetime] = {}
        self.abnormal_since: dict[str, datetime] = {}

    def _prune(self, monitor_id: str, now: datetime) -> None:
        cutoff = now - self.window
        bucket = self.samples[monitor_id]
        while bucket and bucket[0][0] < cutoff:
            bucket.popleft()

    @staticmethod
    def _stats(values: list[float]) -> tuple[float, float]:
        center = float(median(values))
        deviations = [abs(value - center) for value in values]
        mad = float(median(deviations)) if deviations else 0.0
        return center, mad

    def update(
        self,
        monitor_id: str,
        *,
        observed_at: datetime,
        response_ms: float | None,
    ) -> BaselineAssessment:
        """Evaluate the current value against prior samples, then add it once."""
        if observed_at.tzinfo is None:
            observed_at = observed_at.replace(tzinfo=UTC)
        now = observed_at
        self._prune(monitor_id, now)
        bucket = self.samples[monitor_id]
        prior = [value for _at, value in bucket]

        if len(prior) < self.min_samples or response_ms is None:
            assessment = BaselineAssessment(
                state="learning" if response_ms is not None else "unavailable",
                sample_count=len(prior),
                median_ms=float(median(prior)) if prior else None,
                mad_ms=None,
                ratio=None,
                delta_ms=None,
                abnormal=False,
                sustained=False,
                abnormal_seconds=None,
            )
        else:
            center, mad = self._stats(prior)
            ratio = response_ms / center if center > 0 else None
            delta = response_ms - center
            robust_limit = max(self.min_delta_ms, mad * 6.0)
            abnormal = (
                delta >= robust_limit
                and ratio is not None
                and ratio >= self.ratio_threshold
            )
            if abnormal:
                since = self.abnormal_since.setdefault(monitor_id, now)
                seconds = max(0.0, (now - since).total_seconds())
            else:
                self.abnormal_since.pop(monitor_id, None)
                seconds = None
            sustained = bool(
                abnormal and seconds is not None and seconds >= self.degradation_seconds
            )
            assessment = BaselineAssessment(
                state="degraded" if sustained else "abnormal" if abnormal else "normal",
                sample_count=len(prior),
                median_ms=center,
                mad_ms=mad,
                ratio=ratio,
                delta_ms=delta,
                abnormal=abnormal,
                sustained=sustained,
                abnormal_seconds=seconds,
            )

        last = self.last_sample_at.get(monitor_id)
        if response_ms is not None and (last is None or observed_at > last):
            bucket.append((observed_at, float(response_ms)))
            self.last_sample_at[monitor_id] = observed_at
            self._prune(monitor_id, observed_at)
        return assessment

    def remove_unknown(self, valid_ids: set[str]) -> None:
        for store in (self.samples, self.last_sample_at, self.abnormal_since):
            for monitor_id in list(store):
                if monitor_id not in valid_ids:
                    store.pop(monitor_id, None)
