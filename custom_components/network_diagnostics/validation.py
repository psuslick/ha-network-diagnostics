"""Pure validation and coverage analysis for configured diagnostic monitors."""

from __future__ import annotations

from collections import Counter, defaultdict

from .const import (
    ROLE_DNS_LOCAL,
    ROLE_DNS_NEUTRAL,
    ROLE_FIXED_CLIENT,
    ROLE_GATEWAY,
    ROLE_HTTPS_CONTROL,
    ROLE_IPV4_CONTROL,
    ROLE_IPV6_CONTROL,
    ROLE_LAN_CONTROL,
    ROLE_MESH_NODE,
    ROLE_NETWORK_NODE,
    ROLE_SERVICE_DNS,
    ROLE_SERVICE_PATH,
    SERVICE_ROLES,
)
from .observations import MonitorBinding
from .topology import validate_topology

_DNS_ROLES = {ROLE_DNS_NEUTRAL, ROLE_DNS_LOCAL, ROLE_SERVICE_DNS}
_LOCAL_NODE_ROLES = {ROLE_GATEWAY, ROLE_NETWORK_NODE, ROLE_MESH_NODE, ROLE_FIXED_CLIENT}
_INDEPENDENT_ROLES = {
    ROLE_LAN_CONTROL,
    ROLE_IPV4_CONTROL,
    ROLE_IPV6_CONTROL,
    ROLE_DNS_NEUTRAL,
    ROLE_SERVICE_DNS,
    ROLE_SERVICE_PATH,
    ROLE_HTTPS_CONTROL,
}


def _duplicate_independence_gaps(bindings: list[MonitorBinding]) -> list[str]:
    """Find controls presented as independent that resolve to one known target."""
    grouped: dict[tuple[str, str | None], list[MonitorBinding]] = defaultdict(list)
    for item in bindings:
        if item.role not in _INDEPENDENT_ROLES or not item.target_fingerprint:
            continue
        service = item.service.casefold() if item.service else None
        grouped[(item.role, service)].append(item)

    gaps: list[str] = []
    for items in grouped.values():
        by_target: dict[str, list[MonitorBinding]] = defaultdict(list)
        for item in items:
            by_target[item.target_fingerprint or ""].append(item)
        for same in by_target.values():
            if len(same) < 2:
                continue
            names = " and ".join(sorted(item.name for item in same))
            gaps.append(
                f"{names} use the same endpoint for the same diagnostic role; independent evidence must use distinct endpoints"
            )
    return gaps


def _independent_count(items: list[MonitorBinding]) -> int:
    """Count only endpoint identities that Home Assistant lets us verify as distinct."""
    return len({item.target_fingerprint for item in items if item.target_fingerprint})


def _unknown_independence_warnings(bindings: list[MonitorBinding]) -> list[str]:
    grouped: dict[tuple[str, str | None], list[MonitorBinding]] = defaultdict(list)
    for item in bindings:
        if item.role not in _INDEPENDENT_ROLES:
            continue
        service = item.service.casefold() if item.service else None
        grouped[(item.role, service)].append(item)

    warnings: list[str] = []
    for items in grouped.values():
        if len(items) < 2 or all(item.target_fingerprint for item in items):
            continue
        names = ", ".join(sorted(item.name for item in items))
        warnings.append(
            f"Endpoint identity is unavailable for one or more controls in this evidence set ({names}); "
            "they remain usable evidence, but Network Diagnostics will not assume they are independent or increase independence-based confidence"
        )
    return warnings


def validate_bindings(bindings: list[MonitorBinding]) -> tuple[list[str], list[str]]:
    """Return ``(coverage_warnings, blockers)`` for role semantics."""
    warnings: list[str] = []
    blockers: list[str] = []

    names = Counter(item.name.casefold() for item in bindings)
    if any(count > 1 for count in names.values()):
        warnings.append(
            "Two configured Kuma monitors share the same display name; diagnosis still uses stable monitor identity, but incident text may be ambiguous"
        )

    for item in bindings:
        if item.role in _DNS_ROLES and item.monitor_type not in {None, "dns"}:
            blockers.append(
                f"{item.name} is assigned a DNS role but its Kuma monitor type is {item.monitor_type}"
            )
        if item.role == ROLE_HTTPS_CONTROL and item.monitor_type not in {
            None,
            "http",
            "keyword",
            "real_browser",
        }:
            warnings.append(
                f"{item.name} is assigned HTTPS Control but its Kuma monitor type is {item.monitor_type}"
            )
        if item.role == ROLE_IPV4_CONTROL and item.target_ip_version == 6:
            blockers.append(
                f"{item.name} is assigned IPv4 Internet Control but monitors an IPv6 literal"
            )
        if item.role == ROLE_IPV6_CONTROL and item.target_ip_version == 4:
            blockers.append(
                f"{item.name} is assigned IPv6 Internet Control but monitors an IPv4 literal"
            )
        if item.role in SERVICE_ROLES and not item.service:
            blockers.append(
                f"{item.name} is assigned a service-specific role but has no service group name"
            )

    warnings.extend(_unknown_independence_warnings(bindings))
    blockers.extend(_duplicate_independence_gaps(bindings))
    topo_warnings, topo_blockers = validate_topology(bindings)
    warnings.extend(topo_warnings)
    blockers.extend(topo_blockers)
    return list(dict.fromkeys(warnings)), list(dict.fromkeys(blockers))


def coverage_capabilities(bindings: list[MonitorBinding]) -> dict[str, bool]:
    """Describe what the configured evidence can actually distinguish."""
    by_role: dict[str, list[MonitorBinding]] = defaultdict(list)
    for item in bindings:
        by_role[item.role].append(item)

    local_nodes = [item for item in bindings if item.role in _LOCAL_NODE_ROLES]
    child_counts = Counter(
        item.parent_id
        for item in bindings
        if item.role == ROLE_FIXED_CLIENT and item.parent_id
    )
    services = {
        item.service for item in bindings if item.service and item.role in SERVICE_ROLES
    }
    service_depth = any(
        any(x.service == service for x in by_role[ROLE_SERVICE_DNS])
        and any(x.service == service for x in by_role[ROLE_SERVICE_PATH])
        for service in services
    )

    return {
        "gateway_failure": bool(by_role[ROLE_GATEWAY]),
        "local_path_discrimination": bool(
            by_role[ROLE_GATEWAY] and by_role[ROLE_LAN_CONTROL]
        ),
        "topology_node_localization": any(item.parent_id for item in local_nodes),
        "downstream_path_discrimination": any(
            count >= 2 for count in child_counts.values()
        ),
        "adaptive_latency_degradation": any(
            item.role in {ROLE_GATEWAY, ROLE_NETWORK_NODE, ROLE_MESH_NODE}
            for item in bindings
        ),
        "ipv4_specific_failure": _independent_count(by_role[ROLE_IPV4_CONTROL]) >= 2,
        "ipv6_specific_failure": _independent_count(by_role[ROLE_IPV6_CONTROL]) >= 2,
        "wan_failure": bool(
            by_role[ROLE_GATEWAY]
            and (by_role[ROLE_IPV4_CONTROL] or by_role[ROLE_IPV6_CONTROL])
        ),
        "general_dns_failure": bool(
            by_role[ROLE_DNS_NEUTRAL]
            and (by_role[ROLE_IPV4_CONTROL] or by_role[ROLE_IPV6_CONTROL])
        ),
        "local_dns_failure": bool(
            by_role[ROLE_DNS_LOCAL] and by_role[ROLE_DNS_NEUTRAL]
        ),
        "service_dns_path_separation": service_depth,
        "https_specific_failure": bool(
            by_role[ROLE_HTTPS_CONTROL]
            and by_role[ROLE_DNS_NEUTRAL]
            and (by_role[ROLE_IPV4_CONTROL] or by_role[ROLE_IPV6_CONTROL])
        ),
    }


def coverage_gaps(capabilities: dict[str, bool]) -> list[str]:
    """Return advisory gaps; they do not invalidate healthy configured evidence."""
    labels = {
        "gateway_failure": "Gateway failure is not directly covered",
        "local_path_discrimination": "No independent LAN Control is configured to separate gateway failure from the Home Assistant-to-LAN path",
        "topology_node_localization": "No parent relationships are configured for local nodes",
        "downstream_path_discrimination": "No local node has two fixed downstream controls, so forwarding/backhaul-path failures remain harder to distinguish from client failures",
        "adaptive_latency_degradation": "No Gateway, Network Node, or Mesh / Wireless Node is configured for adaptive latency degradation analysis",
        "ipv4_specific_failure": "Fewer than two independent IPv4 controls are configured",
        "ipv6_specific_failure": "Fewer than two independent IPv6 controls are configured",
        "wan_failure": "Gateway plus external IP evidence is not sufficient to distinguish a WAN failure",
        "general_dns_failure": "Independent DNS plus external IP evidence is not configured",
        "local_dns_failure": "Local DNS plus independent DNS evidence is not configured",
        "service_dns_path_separation": "No service has both DNS and path controls, so service DNS failures cannot be separated from service-path failures",
        "https_specific_failure": "HTTPS, independent DNS, and external IP evidence are not all configured",
    }
    return [labels[key] for key, available in capabilities.items() if not available]
