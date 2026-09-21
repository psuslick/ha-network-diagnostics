"""Pure topology helpers for configured monitor dependency graphs."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from .const import (
    LOCAL_CHILD_ROLES,
    LOCAL_PARENT_ROLES,
    ROLE_DISPLAY_NAMES,
    ROLE_GATEWAY,
    TOPOLOGY_NODE_ROLES,
)
from .observations import MonitorBinding, ObservationSet


@dataclass(frozen=True, slots=True)
class TopologyImpact:
    monitor_id: str
    name: str
    ancestors: tuple[str, ...]
    descendants: tuple[str, ...]
    direct_children: tuple[str, ...]
    siblings: tuple[str, ...]


def by_id(bindings: Iterable[MonitorBinding]) -> dict[str, MonitorBinding]:
    return {item.monitor_id: item for item in bindings}


def children_map(bindings: Iterable[MonitorBinding]) -> dict[str, list[MonitorBinding]]:
    mapping: dict[str, list[MonitorBinding]] = {}
    for item in bindings:
        if item.parent_id:
            mapping.setdefault(item.parent_id, []).append(item)
    for items in mapping.values():
        items.sort(key=lambda item: item.name.casefold())
    return mapping


def ancestor_ids(monitor_id: str, bindings: Iterable[MonitorBinding]) -> list[str]:
    lookup = by_id(bindings)
    out: list[str] = []
    seen: set[str] = set()
    current = lookup.get(monitor_id)
    while current and current.parent_id:
        if current.parent_id in seen:
            break
        seen.add(current.parent_id)
        out.append(current.parent_id)
        current = lookup.get(current.parent_id)
    return out


def descendant_ids(monitor_id: str, bindings: Iterable[MonitorBinding]) -> list[str]:
    children = children_map(bindings)
    out: list[str] = []
    stack = list(reversed(children.get(monitor_id, [])))
    seen: set[str] = set()
    while stack:
        item = stack.pop()
        if item.monitor_id in seen:
            continue
        seen.add(item.monitor_id)
        out.append(item.monitor_id)
        stack.extend(reversed(children.get(item.monitor_id, [])))
    return out


def path_names(monitor_id: str, bindings: Iterable[MonitorBinding]) -> tuple[str, ...]:
    lookup = by_id(bindings)
    ids = list(reversed(ancestor_ids(monitor_id, bindings))) + [monitor_id]
    return tuple(lookup[item_id].name for item_id in ids if item_id in lookup)


def impact_for(monitor_id: str, bindings: Iterable[MonitorBinding]) -> TopologyImpact | None:
    binding_list = list(bindings)
    lookup = by_id(binding_list)
    node = lookup.get(monitor_id)
    if node is None:
        return None
    children = children_map(binding_list)
    parent = lookup.get(node.parent_id) if node.parent_id else None
    siblings = [
        item.name
        for item in (children.get(parent.monitor_id, []) if parent else [])
        if item.monitor_id != monitor_id
    ]
    return TopologyImpact(
        monitor_id=monitor_id,
        name=node.name,
        ancestors=tuple(
            lookup[item_id].name
            for item_id in reversed(ancestor_ids(monitor_id, binding_list))
            if item_id in lookup
        ),
        descendants=tuple(
            lookup[item_id].name
            for item_id in descendant_ids(monitor_id, binding_list)
            if item_id in lookup
        ),
        direct_children=tuple(item.name for item in children.get(monitor_id, [])),
        siblings=tuple(siblings),
    )


def topology_payload(bindings: Iterable[MonitorBinding]) -> list[dict[str, object]]:
    binding_list = list(bindings)
    lookup = by_id(binding_list)
    children = children_map(binding_list)
    rows: list[dict[str, object]] = []
    for item in sorted(binding_list, key=lambda value: value.name.casefold()):
        if item.role not in TOPOLOGY_NODE_ROLES:
            continue
        rows.append(
            {
                "monitor_id": item.monitor_id,
                "name": item.name,
                "role": item.role,
                "role_name": ROLE_DISPLAY_NAMES.get(item.role, item.role),
                "parent_id": item.parent_id,
                "parent_name": lookup[item.parent_id].name if item.parent_id in lookup else None,
                "children": [child.name for child in children.get(item.monitor_id, [])],
                "impact": [
                    lookup[child_id].name
                    for child_id in descendant_ids(item.monitor_id, binding_list)
                    if child_id in lookup
                ],
            }
        )
    return rows


def validate_topology(bindings: Iterable[MonitorBinding]) -> tuple[list[str], list[str]]:
    """Return ``(warnings, blockers)`` for topology semantics."""
    items = list(bindings)
    lookup = by_id(items)
    warnings: list[str] = []
    blockers: list[str] = []

    gateways = [item for item in items if item.role == ROLE_GATEWAY]
    if len(gateways) > 1:
        warnings.append(
            "More than one Gateway is configured; this is supported, but each local node should have an explicit parent when the topology is ambiguous"
        )

    for item in items:
        if item.role in LOCAL_CHILD_ROLES and not item.parent_id:
            warnings.append(
                f"{item.name} has no configured parent, so upstream impact suppression is limited"
            )
        if item.parent_id:
            parent = lookup.get(item.parent_id)
            if parent is None:
                blockers.append(f"{item.name} references a parent monitor that is not configured")
                continue
            if parent.role not in LOCAL_PARENT_ROLES:
                blockers.append(
                    f"{item.name} has parent {parent.name}, but {parent.name} is not a Gateway, Network Node, or Mesh / Wireless Node"
                )

    for item in items:
        seen: set[str] = set()
        current = item
        while current.parent_id:
            if current.parent_id == item.monitor_id or current.parent_id in seen:
                blockers.append(f"Topology contains a parent cycle involving {item.name}")
                break
            seen.add(current.parent_id)
            parent = lookup.get(current.parent_id)
            if parent is None:
                break
            current = parent

    return list(dict.fromkeys(warnings)), list(dict.fromkeys(blockers))


def failed_root_nodes(obs: ObservationSet) -> list[tuple[object, list[object]]]:
    """Return failed topology observations whose configured ancestors are not failed."""
    bindings = [item.binding for item in obs.observations]
    lookup_obs = {item.binding.monitor_id: item for item in obs.observations}
    roots: list[tuple[object, list[object]]] = []
    for item in obs.observations:
        if item.binding.role not in TOPOLOGY_NODE_ROLES or item.status is not False:
            continue
        ancestors = ancestor_ids(item.binding.monitor_id, bindings)
        if any(
            lookup_obs.get(ancestor) and lookup_obs[ancestor].status is False
            for ancestor in ancestors
        ):
            continue
        failed_descendants = [
            lookup_obs[descendant]
            for descendant in descendant_ids(item.binding.monitor_id, bindings)
            if descendant in lookup_obs and lookup_obs[descendant].status is False
        ]
        roots.append((item, failed_descendants))
    return roots
