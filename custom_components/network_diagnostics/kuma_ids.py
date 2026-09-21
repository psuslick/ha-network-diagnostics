"""Pure helpers for parsing Home Assistant Uptime Kuma entity unique IDs."""

from __future__ import annotations

KNOWN_SUFFIXES: tuple[str, ...] = (
    "avg_response_time_365d",
    "avg_response_time_30d",
    "avg_response_time_1d",
    "cert_days_remaining",
    "response_time",
    "uptime_365d",
    "uptime_30d",
    "uptime_1d",
    "hostname",
    "status",
    "type",
    "url",
    "port",
    "tags",
)


def split_kuma_unique_id(unique_id: str, entry_id: str) -> tuple[str, str] | None:
    """Return ``(monitor_id, sensor_key)`` for a Kuma entity unique ID."""
    prefix = f"{entry_id}_"
    if not unique_id.startswith(prefix):
        return None
    rest = unique_id[len(prefix) :]
    for suffix in KNOWN_SUFFIXES:
        marker = f"_{suffix}"
        if rest.endswith(marker) and len(rest) > len(marker):
            return rest[: -len(marker)], suffix
    return None
