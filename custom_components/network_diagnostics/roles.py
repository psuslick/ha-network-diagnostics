"""Pure monitor-role parsing and profile helpers."""

from __future__ import annotations

from dataclasses import dataclass
import re

from .const import (
    LEGACY_NAME_ROLES,
    ROLE_DNS_LOCAL,
    ROLE_DNS_NEUTRAL,
    ROLE_GATEWAY,
    ROLE_HTTPS,
    ROLE_IPV4,
    ROLE_IPV6,
    ROLE_LAN_CONTROL,
    ROLE_MESH,
    ROLE_MESH_CHILD,
    ROLE_SERVICE_DNS,
    ROLE_SERVICE_PATH,
)

_MARKER = re.compile(r"^\[ND:(?P<spec>[^\]]+)\]\s*(?P<label>.*)$", re.IGNORECASE)

_SIMPLE = {
    "gateway": ROLE_GATEWAY,
    "lan": ROLE_LAN_CONTROL,
    "lan-control": ROLE_LAN_CONTROL,
    "mesh": ROLE_MESH,
    "wifi": ROLE_MESH,
    "ipv4": ROLE_IPV4,
    "ipv6": ROLE_IPV6,
    "dns-neutral": ROLE_DNS_NEUTRAL,
    "dns-local": ROLE_DNS_LOCAL,
    "https": ROLE_HTTPS,
}


@dataclass(frozen=True, slots=True)
class ParsedRole:
    role: str
    group: str | None = None
    label: str | None = None
    source: str = "marker"


def parse_monitor_name(name: str) -> ParsedRole | None:
    """Parse a Uptime Kuma monitor name into a diagnostic role.

    Explicit ``[ND:...]`` markers win. Known legacy names are accepted so an
    existing installation does not need to rename monitors merely to use the
    integration.
    """
    clean = name.strip()
    match = _MARKER.match(clean)
    if match:
        spec = match.group("spec").strip()
        label = match.group("label").strip() or None
        lower = spec.lower()
        if lower in _SIMPLE:
            return ParsedRole(_SIMPLE[lower], label=label, source="marker")

        parts = [part.strip() for part in spec.split(":")]
        if len(parts) == 2 and parts[0].lower() == "mesh-child" and parts[1]:
            return ParsedRole(
                ROLE_MESH_CHILD, group=parts[1], label=label, source="marker"
            )
        if len(parts) == 3 and parts[0].lower() == "service" and parts[1]:
            kind = parts[2].lower()
            if kind == "dns":
                return ParsedRole(ROLE_SERVICE_DNS, group=parts[1], label=label, source="marker")
            if kind == "path":
                return ParsedRole(ROLE_SERVICE_PATH, group=parts[1], label=label, source="marker")
        return None

    legacy = LEGACY_NAME_ROLES.get(clean)
    if legacy:
        role, group = legacy
        label = clean
        if role == ROLE_MESH:
            label = group or clean
            group = None
        return ParsedRole(role, group=group, label=label, source="legacy")
    return None
