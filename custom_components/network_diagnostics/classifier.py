"""Deterministic topology-aware root-cause classification."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable

from .baseline import BaselineAssessment
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
)
from .observations import Observation, ObservationSet
from .topology import ancestor_ids, children_map, failed_root_nodes, path_names

HEALTHY = "Healthy"
SETUP_REQUIRED = "Setup required"
MONITORING_INCOMPLETE = "Monitoring incomplete"
MIXED = "Mixed / insufficient evidence"
MULTIPLE = "Multiple concurrent faults"


@dataclass(frozen=True, slots=True)
class RootCause:
    name: str
    domain: str
    confidence: str
    supporting: tuple[str, ...] = ()
    contradicting: tuple[str, ...] = ()
    downstream: tuple[str, ...] = ()
    affected: tuple[str, ...] = ()
    causal_path: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class DiagnosisResult:
    diagnosis: str
    summary: str
    confidence: str
    evidence: tuple[str, ...] = field(default_factory=tuple)
    contradictions: tuple[str, ...] = field(default_factory=tuple)
    downstream: tuple[str, ...] = field(default_factory=tuple)
    unaffected: tuple[str, ...] = field(default_factory=tuple)
    failed_controls: tuple[str, ...] = field(default_factory=tuple)
    affected_components: tuple[str, ...] = field(default_factory=tuple)
    monitoring_gaps: tuple[str, ...] = field(default_factory=tuple)
    coverage_gaps: tuple[str, ...] = field(default_factory=tuple)
    unassigned_monitors: tuple[str, ...] = field(default_factory=tuple)
    root_causes: tuple[RootCause, ...] = field(default_factory=tuple)

    @property
    def healthy(self) -> bool:
        return self.diagnosis == HEALTHY

    @property
    def monitoring_problem(self) -> bool:
        return self.diagnosis == MONITORING_INCOMPLETE

    @property
    def setup_required(self) -> bool:
        return self.diagnosis == SETUP_REQUIRED


def _usable(items: Iterable[Observation]) -> list[Observation]:
    return [item for item in items if item.status is not None]


def _all_down(items: Iterable[Observation]) -> bool:
    values = _usable(items)
    return bool(values) and all(item.status is False for item in values)


def _any_up(items: Iterable[Observation]) -> bool:
    return any(item.status is True for item in items)


def _any_down(items: Iterable[Observation]) -> bool:
    return any(item.status is False for item in items)


def _names(items: Iterable[Observation]) -> tuple[str, ...]:
    return tuple(item.binding.name for item in items)


def _failed_names(obs: ObservationSet) -> tuple[str, ...]:
    return tuple(item.binding.name for item in obs.observations if item.status is False)


def _healthy_names(obs: ObservationSet) -> tuple[str, ...]:
    return tuple(item.binding.name for item in obs.observations if item.status is True)


def _result_from_causes(obs: ObservationSet, causes: list[RootCause]) -> DiagnosisResult:
    coverage = tuple(obs.coverage_gaps)
    failed = _failed_names(obs)
    unaffected = _healthy_names(obs)
    if not causes:
        if failed:
            return DiagnosisResult(
                diagnosis=MIXED,
                summary=(
                    "One or more configured monitors are failing, but the available "
                    "independent evidence does not support a single causal explanation."
                ),
                confidence="low",
                evidence=tuple(f"Failed: {name}" for name in failed),
                unaffected=unaffected,
                failed_controls=failed,
                affected_components=failed,
                coverage_gaps=coverage,
                unassigned_monitors=tuple(obs.unassigned_monitors),
            )
        return DiagnosisResult(
            diagnosis=HEALTHY,
            summary=(
                "All configured diagnostic monitors are healthy."
                if not coverage
                else "All configured diagnostic monitors are healthy; the coverage report lists fault classes that are not yet distinguishable."
            ),
            confidence="high" if not coverage else "medium",
            evidence=("No configured diagnostic monitor is reporting a failure.",),
            unaffected=unaffected,
            coverage_gaps=coverage,
            unassigned_monitors=tuple(obs.unassigned_monitors),
        )

    if len(causes) == 1:
        cause = causes[0]
        return DiagnosisResult(
            diagnosis=cause.name,
            summary=f"{cause.name}. "
            + (
                cause.supporting[0]
                if cause.supporting
                else "The observed failure pattern matches this fault domain."
            ),
            confidence=cause.confidence,
            evidence=cause.supporting,
            contradictions=cause.contradicting,
            downstream=cause.downstream,
            unaffected=unaffected,
            failed_controls=failed,
            affected_components=cause.affected,
            coverage_gaps=coverage,
            unassigned_monitors=tuple(obs.unassigned_monitors),
            root_causes=(cause,),
        )

    return DiagnosisResult(
        diagnosis=MULTIPLE,
        summary="Multiple independent fault domains are present: "
        + "; ".join(cause.name for cause in causes)
        + ".",
        confidence="high" if all(cause.confidence == "high" for cause in causes) else "medium",
        evidence=tuple(item for cause in causes for item in cause.supporting),
        contradictions=tuple(item for cause in causes for item in cause.contradicting),
        downstream=tuple(item for cause in causes for item in cause.downstream),
        unaffected=unaffected,
        failed_controls=failed,
        affected_components=tuple(item for cause in causes for item in cause.affected),
        coverage_gaps=coverage,
        unassigned_monitors=tuple(obs.unassigned_monitors),
        root_causes=tuple(causes),
    )


def _topology_causes(
    obs: ObservationSet,
    baseline_assessments: dict[str, BaselineAssessment],
) -> tuple[list[RootCause], bool]:
    """Return local topology causes and whether a hard gateway root suppresses externals."""
    causes: list[RootCause] = []
    gateway = obs.by_role(ROLE_GATEWAY)
    lan = obs.by_role(ROLE_LAN_CONTROL)
    external = [*obs.by_role(ROLE_IPV4_CONTROL), *obs.by_role(ROLE_IPV6_CONTROL)]
    bindings = [item.binding for item in obs.observations]
    lookup_obs = {item.binding.monitor_id: item for item in obs.observations}
    child_lookup = children_map(bindings)

    gateway_down = _all_down(gateway)
    if gateway_down:
        downstream_failed = [
            item.binding.name
            for item in obs.observations
            if item.status is False and item.binding.role != ROLE_LAN_CONTROL
        ]
        if _any_up(external):
            support = (
                "The Gateway monitor is down while external Internet reachability remains healthy."
            )
            if lan and _any_up(lan):
                support = (
                    "The Gateway monitor is down while an independent LAN Control and external Internet reachability remain healthy."
                )
            causes.append(
                RootCause(
                    "Gateway management/reachability failure",
                    "local",
                    "high" if lan and _any_up(lan) else "medium",
                    supporting=(support,),
                    contradicting=(
                        "A complete gateway forwarding failure is contradicted by healthy external Internet reachability from Home Assistant.",
                    ),
                    affected=_names(gateway),
                    causal_path=("Home Assistant", "Gateway management/reachability"),
                )
            )
        elif lan and _any_up(lan):
            causes.append(
                RootCause(
                    "Gateway/router failure",
                    "local",
                    "high",
                    supporting=(
                        "The Gateway monitor is down while an independent LAN Control remains reachable.",
                    ),
                    downstream=tuple(
                        name for name in downstream_failed if name not in _names(gateway)
                    ),
                    affected=_names(gateway),
                    causal_path=("Gateway", "downstream network services"),
                )
            )
            return causes, True
        elif lan and _all_down(lan):
            causes.append(
                RootCause(
                    "Local LAN / Home Assistant path failure",
                    "local",
                    "high",
                    supporting=(
                        "The Gateway and independent LAN Control are both unreachable from Home Assistant.",
                    ),
                    downstream=tuple(downstream_failed),
                    affected=tuple((*_names(gateway), *_names(lan))),
                    causal_path=(
                        "Home Assistant local path",
                        "Gateway",
                        "downstream services",
                    ),
                )
            )
            return causes, True
        else:
            causes.append(
                RootCause(
                    "Gateway / local path failure",
                    "local",
                    "medium",
                    supporting=(
                        "The Gateway is unreachable and no independent healthy control is available to localize the failure further.",
                    ),
                    downstream=tuple(downstream_failed),
                    affected=_names(gateway),
                    causal_path=(
                        "Gateway or Home Assistant local path",
                        "downstream services",
                    ),
                )
            )
            return causes, True

    if not gateway_down and lan and _any_down(lan):
        failed_lan = [item for item in lan if item.status is False]
        healthy_lan = [item for item in lan if item.status is True]
        causes.append(
            RootCause(
                "Partial LAN control failure" if healthy_lan else "LAN control endpoint/path failure",
                "local-control",
                "medium",
                supporting=(
                    "A LAN Control is unreachable while the Gateway remains reachable; this does not support a whole-LAN outage.",
                ),
                contradicting=(
                    "A broad local-LAN failure is contradicted by the reachable Gateway.",
                ),
                affected=_names(failed_lan),
                causal_path=("Gateway", "LAN Control endpoint/path"),
            )
        )

    fixed_failures_by_parent: dict[str | None, list[Observation]] = {}
    mesh_roots_by_parent: dict[str | None, list[tuple[Observation, list[Observation]]]] = {}
    for item, failed_descendants in failed_root_nodes(obs):
        if item.binding.role == ROLE_GATEWAY:
            continue
        if item.binding.role == ROLE_FIXED_CLIENT:
            fixed_failures_by_parent.setdefault(item.binding.parent_id, []).append(item)
            continue
        if item.binding.role == ROLE_MESH_NODE:
            mesh_roots_by_parent.setdefault(item.binding.parent_id, []).append(
                (item, failed_descendants)
            )
            continue
        path = path_names(item.binding.monitor_id, bindings)
        parent = lookup_obs.get(item.binding.parent_id or "")
        confidence = "high" if parent and parent.status is True else "medium"
        causes.append(
            RootCause(
                f"{item.binding.name} unreachable",
                "topology",
                confidence,
                supporting=(
                    f"{item.binding.name} is down"
                    + (
                        f" while its parent {parent.binding.name} remains reachable."
                        if parent and parent.status is True
                        else "."
                    ),
                ),
                downstream=_names(failed_descendants),
                affected=(item.binding.name,),
                causal_path=path or (item.binding.name,),
            )
        )

    for parent_id, pairs in mesh_roots_by_parent.items():
        items = [pair[0] for pair in pairs]
        failed_descendants = [desc for _item, descs in pairs for desc in descs]
        parent = lookup_obs.get(parent_id or "")
        if len(items) > 1:
            parent_name = parent.binding.name if parent else "upstream parent"
            causes.append(
                RootCause(
                    "Mesh / wireless layer failure",
                    "topology",
                    "high" if parent and parent.status is True else "medium",
                    supporting=(
                        f"Multiple Mesh / Wireless Nodes are down while {parent_name} remains reachable."
                        if parent and parent.status is True
                        else "Multiple Mesh / Wireless Nodes are down under the same configured parent.",
                    ),
                    downstream=_names(failed_descendants),
                    affected=_names(items),
                    causal_path=(parent_name, "Mesh / wireless layer"),
                )
            )
        else:
            item = items[0]
            path = path_names(item.binding.monitor_id, bindings)
            causes.append(
                RootCause(
                    f"{item.binding.name} unreachable",
                    "topology",
                    "high" if parent and parent.status is True else "medium",
                    supporting=(
                        f"{item.binding.name} is down"
                        + (
                            f" while its parent {parent.binding.name} remains reachable."
                            if parent and parent.status is True
                            else "."
                        ),
                    ),
                    downstream=_names(failed_descendants),
                    affected=(item.binding.name,),
                    causal_path=path or (item.binding.name,),
                )
            )

    for parent_id, failed_clients in fixed_failures_by_parent.items():
        parent = lookup_obs.get(parent_id or "")
        if parent and parent.status is False:
            continue
        if parent and parent.status is True:
            if len(failed_clients) >= 2:
                causes.append(
                    RootCause(
                        f"{parent.binding.name} downstream/forwarding path failure",
                        "topology",
                        "high",
                        supporting=(
                            f"Multiple Fixed Downstream Clients behind {parent.binding.name} are down while the parent remains reachable.",
                        ),
                        contradicting=(
                            f"A complete {parent.binding.name} node outage is contradicted by the node itself remaining reachable.",
                        ),
                        affected=_names(failed_clients),
                        causal_path=(
                            *path_names(parent.binding.monitor_id, bindings),
                            "downstream/forwarding path",
                        ),
                    )
                )
            else:
                causes.append(
                    RootCause(
                        f"{parent.binding.name} downstream path/client failure",
                        "topology",
                        "medium",
                        supporting=(
                            f"A Fixed Downstream Client behind {parent.binding.name} is down while the parent remains reachable.",
                        ),
                        contradicting=(
                            "One downstream client cannot distinguish a client failure from the forwarding path by itself.",
                        ),
                        affected=_names(failed_clients),
                        causal_path=(
                            *path_names(parent.binding.monitor_id, bindings),
                            "downstream path or client",
                        ),
                    )
                )
        else:
            for item in failed_clients:
                causes.append(
                    RootCause(
                        f"{item.binding.name} endpoint/path failure",
                        "topology",
                        "medium",
                        supporting=(
                            f"{item.binding.name} is down and no healthy configured parent is available to localize the path further.",
                        ),
                        affected=(item.binding.name,),
                        causal_path=(item.binding.name,),
                    )
                )

    sustained = {
        monitor_id: assessment
        for monitor_id, assessment in baseline_assessments.items()
        if assessment.sustained
        and (item := lookup_obs.get(monitor_id)) is not None
        and item.status is True
    }
    root_degraded: dict[str, BaselineAssessment] = {}
    for monitor_id, assessment in sustained.items():
        if any(ancestor in sustained for ancestor in ancestor_ids(monitor_id, bindings)):
            continue
        root_degraded[monitor_id] = assessment

    consumed: set[str] = set()
    degraded_mesh_by_parent: dict[str | None, list[str]] = {}
    for monitor_id in root_degraded:
        item = lookup_obs[monitor_id]
        if item.binding.role == ROLE_MESH_NODE:
            degraded_mesh_by_parent.setdefault(item.binding.parent_id, []).append(monitor_id)

    for parent_id, monitor_ids in degraded_mesh_by_parent.items():
        if len(monitor_ids) < 2:
            continue
        parent = lookup_obs.get(parent_id or "")
        if parent and parent.status is not True:
            continue
        parent_assessment = baseline_assessments.get(parent_id or "")
        if parent_assessment and parent_assessment.sustained:
            continue
        items = [lookup_obs[item_id] for item_id in monitor_ids]
        causes.append(
            RootCause(
                "Mesh / wireless layer latency degradation",
                "topology",
                "high" if parent and parent.status is True else "medium",
                supporting=(
                    "Multiple sibling Mesh / Wireless Nodes show sustained response-time degradation while their configured parent remains reachable."
                    if parent
                    else "Multiple sibling Mesh / Wireless Nodes show sustained response-time degradation.",
                ),
                affected=_names(items),
                causal_path=(
                    *((parent.binding.name,) if parent else ()),
                    "Mesh / wireless layer latency",
                ),
            )
        )
        consumed.update(monitor_ids)

    for monitor_id, assessment in root_degraded.items():
        if monitor_id in consumed:
            continue
        item = lookup_obs[monitor_id]
        parent = lookup_obs.get(item.binding.parent_id or "")
        ratio = f"{assessment.ratio:.1f}×" if assessment.ratio is not None else "materially above"
        baseline = (
            f"{assessment.median_ms:.1f} ms"
            if assessment.median_ms is not None
            else "its recent baseline"
        )
        supporting = [
            f"{item.binding.name} response time is {ratio} its recent median ({baseline}) for a sustained period."
        ]
        contradictions: list[str] = []
        confidence = "medium"
        if parent and parent.status is True:
            contradictions.append(
                f"A broad upstream outage is contradicted by parent {parent.binding.name} remaining reachable."
            )
            parent_assessment = baseline_assessments.get(parent.binding.monitor_id)
            if parent_assessment and parent_assessment.state == "normal":
                supporting.append(
                    f"Parent {parent.binding.name} remains within its own recent response-time baseline."
                )

        siblings = [
            sibling
            for sibling in child_lookup.get(item.binding.parent_id or "", [])
            if sibling.monitor_id != monitor_id
            and sibling.role in {ROLE_NETWORK_NODE, ROLE_MESH_NODE}
        ]
        normal_siblings = [
            sibling.name
            for sibling in siblings
            if (sibling_obs := lookup_obs.get(sibling.monitor_id)) is not None
            and sibling_obs.status is True
            and (sibling_assessment := baseline_assessments.get(sibling.monitor_id)) is not None
            and sibling_assessment.state == "normal"
        ]
        if normal_siblings:
            supporting.append(
                "Sibling control(s) remain within baseline: " + ", ".join(normal_siblings) + "."
            )
            if parent and parent.status is True:
                confidence = "high"

        causes.append(
            RootCause(
                f"{item.binding.name} latency degradation",
                "topology",
                confidence,
                supporting=tuple(supporting),
                contradicting=tuple(contradictions),
                affected=(item.binding.name,),
                causal_path=(
                    *path_names(item.binding.monitor_id, bindings),
                    "latency degradation",
                ),
            )
        )

    return causes, False


def classify(
    obs: ObservationSet,
    *,
    degraded_nodes: dict[str, BaselineAssessment] | None = None,
) -> DiagnosisResult:
    """Classify observations with deterministic causal reasoning."""
    degraded_nodes = degraded_nodes or {}
    if not obs.configured:
        return DiagnosisResult(
            diagnosis=SETUP_REQUIRED,
            summary=(
                "Network Diagnostics found Uptime Kuma monitors, but the one-time "
                "diagnostic role/topology setup has not been completed. Open the "
                "Network Diagnostics integration and choose Reconfigure to finish setup."
            ),
            confidence="insufficient",
            coverage_gaps=tuple(obs.coverage_gaps),
            unassigned_monitors=tuple(obs.unassigned_monitors),
        )
    if obs.monitoring_gaps or obs.required_gaps or not obs.provider_fresh:
        gaps = [*obs.required_gaps, *obs.monitoring_gaps]
        if not obs.provider_fresh:
            age = (
                f" ({obs.provider_age_seconds:.0f}s since the stalest configured monitor heartbeat)"
                if obs.provider_age_seconds is not None
                else ""
            )
            gaps.append(f"Uptime Kuma evidence is stale or unavailable{age}")
        return DiagnosisResult(
            diagnosis=MONITORING_INCOMPLETE,
            summary=(
                "Required configured evidence is missing, stale, or invalid, so Network Diagnostics "
                "will not claim the network is healthy or assign a root cause."
            ),
            confidence="insufficient",
            monitoring_gaps=tuple(dict.fromkeys(gaps)),
            coverage_gaps=tuple(obs.coverage_gaps),
            unassigned_monitors=tuple(obs.unassigned_monitors),
            failed_controls=_failed_names(obs),
            unaffected=_healthy_names(obs),
        )

    gateway = obs.by_role(ROLE_GATEWAY)
    ipv4 = obs.by_role(ROLE_IPV4_CONTROL)
    ipv6 = obs.by_role(ROLE_IPV6_CONTROL)
    dns_neutral = obs.by_role(ROLE_DNS_NEUTRAL)
    dns_local = obs.by_role(ROLE_DNS_LOCAL)
    https = obs.by_role(ROLE_HTTPS_CONTROL)

    causes, gateway_suppresses_external = _topology_causes(obs, degraded_nodes)
    if gateway_suppresses_external:
        return _result_from_causes(obs, causes)

    v4_down = _all_down(ipv4)
    v6_down = _all_down(ipv6)
    v4_up = _any_up(ipv4)
    v6_up = _any_up(ipv6)
    if v4_down and ipv4 and v6_up:
        causes.append(
            RootCause(
                "General IPv4 failure",
                "internet",
                "high" if len(_usable(ipv4)) >= 2 else "medium",
                supporting=(
                    "All configured IPv4 controls are down while at least one IPv6 control remains healthy.",
                ),
                contradicting=(
                    "A full WAN outage is contradicted by healthy IPv6 reachability.",
                ),
                downstream=_names(
                    [item for item in (*dns_neutral, *dns_local, *https) if item.status is False]
                ),
                affected=_names(ipv4),
                causal_path=("upstream network", "IPv4"),
            )
        )
    elif v6_down and ipv6 and v4_up:
        causes.append(
            RootCause(
                "General IPv6 failure",
                "internet",
                "high" if len(_usable(ipv6)) >= 2 else "medium",
                supporting=(
                    "All configured IPv6 controls are down while at least one IPv4 control remains healthy.",
                ),
                contradicting=(
                    "A full WAN outage is contradicted by healthy IPv4 reachability.",
                ),
                downstream=_names(
                    [item for item in (*dns_neutral, *dns_local, *https) if item.status is False]
                ),
                affected=_names(ipv6),
                causal_path=("upstream network", "IPv6"),
            )
        )
    elif (ipv4 or ipv6) and ((v4_down or not ipv4) and (v6_down or not ipv6)):
        failed_external = [item for item in (*ipv4, *ipv6) if item.status is False]
        causes.append(
            RootCause(
                "Upstream Internet / WAN failure",
                "internet",
                "high" if gateway and _any_up(gateway) else "medium",
                supporting=(
                    "Configured external IP controls are unreachable while the local Gateway remains reachable.",
                ),
                downstream=_names(
                    [item for item in (*dns_neutral, *dns_local, *https) if item.status is False]
                ),
                affected=_names(failed_external),
                causal_path=("Gateway", "WAN/upstream Internet", "external services"),
            )
        )
    else:
        partial_ip = [item for item in (*ipv4, *ipv6) if item.status is False]
        if partial_ip and (v4_up or v6_up):
            causes.append(
                RootCause(
                    "Partial Internet target/path failure",
                    "internet",
                    "medium",
                    supporting=(
                        "Some external reachability controls fail while others remain healthy.",
                    ),
                    affected=_names(partial_ip),
                    causal_path=("Internet", "specific target/path"),
                )
            )

    has_upstream = any(cause.name == "Upstream Internet / WAN failure" for cause in causes)
    internet_any_up = v4_up or v6_up
    if not has_upstream and internet_any_up:
        neutral_down = _all_down(dns_neutral)
        neutral_up = _any_up(dns_neutral)
        local_down = _all_down(dns_local)
        if dns_neutral and neutral_down and (not dns_local or local_down):
            causes.append(
                RootCause(
                    "General DNS failure",
                    "dns",
                    "high" if len(_usable(dns_neutral)) >= 2 else "medium",
                    supporting=(
                        "Independent DNS controls are failing while general IP reachability remains available.",
                    ),
                    contradicting=(
                        "A general Internet outage is contradicted by healthy IP controls.",
                    ),
                    downstream=_names([item for item in https if item.status is False]),
                    affected=_names(
                        [item for item in (*dns_neutral, *dns_local) if item.status is False]
                    ),
                    causal_path=("Internet IP", "DNS"),
                )
            )
        elif dns_local and local_down and neutral_up:
            causes.append(
                RootCause(
                    "Local DNS forwarder/upstream failure",
                    "dns",
                    "high",
                    supporting=(
                        "Local DNS is down while Independent DNS remains healthy.",
                    ),
                    contradicting=(
                        "General DNS failure is contradicted by healthy Independent DNS.",
                    ),
                    affected=_names(dns_local),
                    causal_path=("Internet", "local DNS forwarder"),
                )
            )

        for service in obs.service_groups:
            service_dns = obs.by_service(ROLE_SERVICE_DNS, service)
            service_path = obs.by_service(ROLE_SERVICE_PATH, service)
            dns_all_down = _all_down(service_dns)
            path_all_down = _all_down(service_path)
            dns_any_up = _any_up(service_dns)
            path_any_up = _any_up(service_path)
            if dns_all_down and service_dns and path_all_down and service_path and neutral_up:
                causes.append(
                    RootCause(
                        f"{service} routing/path failure",
                        f"service:{service}",
                        "high",
                        supporting=(
                            f"{service} DNS and path controls fail while Independent DNS and general Internet remain healthy.",
                        ),
                        contradicting=(
                            "General DNS failure is contradicted by healthy Independent DNS.",
                        ),
                        downstream=_names([item for item in dns_local if item.status is False]),
                        affected=_names([*service_dns, *service_path]),
                        causal_path=("Internet", f"{service} network path", f"{service} DNS service"),
                    )
                )
            elif dns_all_down and service_dns and (path_any_up or not service_path) and neutral_up:
                causes.append(
                    RootCause(
                        f"{service} DNS-service failure",
                        f"service:{service}",
                        "high" if len(_usable(service_dns)) >= 2 and service_path else "medium",
                        supporting=(
                            f"{service} DNS checks fail while its path and Independent DNS remain healthy.",
                        ),
                        affected=_names(service_dns),
                        causal_path=("Internet", f"{service} path", f"{service} DNS service"),
                    )
                )
            else:
                partial = [item for item in (*service_dns, *service_path) if item.status is False]
                if partial and (dns_any_up or path_any_up):
                    causes.append(
                        RootCause(
                            f"Partial {service} endpoint/path failure",
                            f"service:{service}",
                            "medium",
                            supporting=(f"Only part of the {service} evidence set is failing.",),
                            affected=_names(partial),
                            causal_path=("Internet", service, "specific endpoint/path"),
                        )
                    )

        if https and _all_down(https) and neutral_up:
            causes.append(
                RootCause(
                    "HTTPS-specific failure",
                    "https",
                    "medium",
                    supporting=(
                        "HTTPS controls fail while IP reachability and Independent DNS remain healthy.",
                    ),
                    affected=_names(https),
                    causal_path=("Internet", "DNS", "HTTPS/application layer"),
                )
            )

    if any(cause.domain.startswith("service:") for cause in causes):
        causes = [cause for cause in causes if cause.name != "Local DNS forwarder/upstream failure"]

    topology_causes = [cause for cause in causes if cause.domain == "topology"]
    non_topology = [cause for cause in causes if cause.domain != "topology"]
    if len(topology_causes) > 1 and not non_topology:
        combined = RootCause(
            "Local topology impairment",
            "topology",
            "high" if all(c.confidence == "high" for c in topology_causes) else "medium",
            supporting=tuple(item for c in topology_causes for item in c.supporting),
            contradicting=tuple(item for c in topology_causes for item in c.contradicting),
            downstream=tuple(item for c in topology_causes for item in c.downstream),
            affected=tuple(item for c in topology_causes for item in c.affected),
            causal_path=("configured local topology", "multiple affected nodes/paths"),
        )
        causes = [combined]

    return _result_from_causes(obs, causes)
