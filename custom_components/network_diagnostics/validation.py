"""Pure validation of discovered diagnostic monitor semantics."""

from __future__ import annotations

from collections import Counter
import ipaddress

from .const import (
    ROLE_DNS_LOCAL,
    ROLE_DNS_NEUTRAL,
    ROLE_HTTPS,
    ROLE_IPV4,
    ROLE_IPV6,
    ROLE_MESH,
    ROLE_MESH_CHILD,
    ROLE_SERVICE_DNS,
    ROLE_SERVICE_PATH,
)
from .observations import MonitorBinding

_DNS_ROLES = {ROLE_DNS_NEUTRAL, ROLE_DNS_LOCAL, ROLE_SERVICE_DNS}


def validate_bindings(bindings: list[MonitorBinding]) -> tuple[list[str], list[str]]:
    """Return ``(coverage_warnings, required_blockers)`` for monitor mappings."""
    warnings: list[str] = []
    blockers: list[str] = []

    # Distinct Kuma monitor IDs are distinct observations, but two non-DNS
    # monitors assigned to the same diagnostic role/group and the exact same
    # endpoint are not independent evidence. DNS monitors are excluded because
    # Kuma's exposed target is the query hostname; the configured resolver is
    # not part of the HA/Prometheus target metadata, so two independent DNS
    # resolvers can legitimately show the same target.
    seen_sources: dict[tuple[str, str, str, str], str] = {}
    for item in bindings:
        if item.role in _DNS_ROLES or not item.target_fingerprint:
            continue
        key = (
            item.role,
            (item.group or "").casefold(),
            (item.monitor_type or "").casefold(),
            item.target_fingerprint,
        )
        previous = seen_sources.get(key)
        if previous:
            blockers.append(
                f"{previous} and {item.name} use the same endpoint for the same diagnostic role; they are not independent controls"
            )
        else:
            seen_sources[key] = item.name

    mesh_labels = [(item.label or item.name).strip() for item in bindings if item.role == ROLE_MESH]
    mesh_counts = Counter(label.casefold() for label in mesh_labels)
    duplicated_mesh_labels = {label for label, count in mesh_counts.items() if count > 1}
    if duplicated_mesh_labels:
        for duplicate in sorted(duplicated_mesh_labels):
            blockers.append(
                f"Multiple mesh monitors use the same diagnostic label {duplicate!r}; mesh-child parent relationships would be ambiguous"
            )

    mesh_lookup = {label.casefold() for label in mesh_labels}
    for item in bindings:
        monitor_type = (item.monitor_type or "").casefold()
        if item.role in _DNS_ROLES and monitor_type and monitor_type != "dns":
            blockers.append(
                f"{item.name} is assigned a DNS role but Kuma monitor type is {item.monitor_type!r}, not 'dns'"
            )

        if item.role == ROLE_HTTPS and item.target and "://" in item.target:
            if not item.target.casefold().startswith("https://"):
                blockers.append(
                    f"{item.name} is assigned the HTTPS role but its monitored URL is not HTTPS"
                )

        if item.role in {ROLE_IPV4, ROLE_IPV6} and item.target:
            try:
                addr = ipaddress.ip_address(item.target.strip("[]"))
            except ValueError:
                addr = None
            if addr is not None:
                expected = 4 if item.role == ROLE_IPV4 else 6
                if addr.version != expected:
                    blockers.append(
                        f"{item.name} is assigned {item.role.upper()} but targets an IPv{addr.version} address"
                    )

        if item.role == ROLE_MESH_CHILD:
            parent = (item.group or "").strip()
            if not parent:
                blockers.append(f"{item.name} is a mesh-child monitor without a parent mesh label")
            elif parent.casefold() not in mesh_lookup:
                blockers.append(
                    f"{item.name} references mesh parent {parent!r}, but no [ND:mesh] monitor uses that label"
                )

    service_dns = {
        (item.group or "").casefold()
        for item in bindings
        if item.role == ROLE_SERVICE_DNS and item.group
    }
    service_path = {
        (item.group or "").casefold()
        for item in bindings
        if item.role == ROLE_SERVICE_PATH and item.group
    }
    display_group = {
        (item.group or "").casefold(): item.group
        for item in bindings
        if item.group
    }
    for group in sorted(service_dns - service_path):
        warnings.append(
            f"Service {display_group.get(group, group)} has DNS checks but no service-path control; DNS-service versus routing failures will be harder to separate"
        )
    for group in sorted(service_path - service_dns):
        warnings.append(
            f"Service {display_group.get(group, group)} has path controls but no service-DNS check; service-specific DNS diagnosis is unavailable"
        )

    return list(dict.fromkeys(warnings)), list(dict.fromkeys(blockers))
