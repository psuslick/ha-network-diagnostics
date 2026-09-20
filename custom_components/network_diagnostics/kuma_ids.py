"""Pure helpers for parsing Home Assistant Uptime Kuma entity unique IDs."""

from __future__ import annotations

# Longest first. Home Assistant's Uptime Kuma sensor keys include multi-word
# suffixes such as response_time; splitting on the final underscore is wrong.
KNOWN_SUFFIXES: tuple[str, ...] = (
    "cert_days_remaining",
    "response_time",
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
