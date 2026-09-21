"""Parse optional Uptime Kuma tag hints from Home Assistant state attributes."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable

from .const import (
    KUMA_TAG_ENABLED,
    KUMA_TAG_ENABLED_VALUE,
    KUMA_TAG_PARENT,
    KUMA_TAG_ROLE,
    KUMA_TAG_SERVICE,
    ROLE_DISPLAY_NAMES,
)


@dataclass(frozen=True, slots=True)
class TagHint:
    """Optional setup hints derived from Kuma tags."""

    enrolled: bool = False
    role: str | None = None
    parent_name: str | None = None
    service: str | None = None


_ROLE_BY_DISPLAY = {value.casefold(): key for key, value in ROLE_DISPLAY_NAMES.items()}
_ROLE_BY_KEY = {key.casefold(): key for key in ROLE_DISPLAY_NAMES}


def _tag_pairs(attributes: dict[str, Any] | None) -> Iterable[tuple[str, str]]:
    if not attributes:
        return []
    raw = attributes.get("tags")
    if raw is None:
        raw = attributes.get("tag_list")
    if raw is None:
        return []

    pairs: list[tuple[str, str]] = []
    if isinstance(raw, dict):
        for key, value in raw.items():
            pairs.append((str(key), "" if value is None else str(value)))
        return pairs
    if not isinstance(raw, (list, tuple, set)):
        return []
    for item in raw:
        if isinstance(item, str):
            if "=" in item:
                name, value = item.split("=", 1)
                pairs.append((name.strip(), value.strip()))
            elif ":" in item:
                name, value = item.split(":", 1)
                pairs.append((name.strip(), value.strip()))
            else:
                pairs.append((item.strip(), ""))
        elif isinstance(item, dict):
            name = item.get("name") or item.get("tag") or item.get("key")
            if name is None:
                continue
            value = item.get("value")
            pairs.append((str(name), "" if value is None else str(value)))
    return pairs


def parse_tag_hint(attributes: dict[str, Any] | None) -> TagHint:
    """Return optional role/parent/service suggestions from Kuma tags."""
    values = {name.strip().casefold(): value.strip() for name, value in _tag_pairs(attributes)}
    enabled_value = values.get(KUMA_TAG_ENABLED.casefold())
    enrolled = enabled_value is not None and (
        not enabled_value or enabled_value.casefold() == KUMA_TAG_ENABLED_VALUE.casefold()
    )

    role_value = values.get(KUMA_TAG_ROLE.casefold())
    role = None
    if role_value:
        role = _ROLE_BY_DISPLAY.get(role_value.casefold()) or _ROLE_BY_KEY.get(
            role_value.casefold()
        )

    parent = values.get(KUMA_TAG_PARENT.casefold()) or None
    service = values.get(KUMA_TAG_SERVICE.casefold()) or None
    return TagHint(
        enrolled=enrolled or role is not None,
        role=role,
        parent_name=parent,
        service=service,
    )
