"""Deterministic topology-aware root-cause classification."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable

from .const import (
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
from .observations import Observation, ObservationSet

HEALTHY = "Healthy"
MONITORING_INCOMPLETE = "Monitoring incomplete"
MIXED = "Mixed / insufficient evidence"
MULTIPLE = "Multiple concurrent faults"


@dataclass(frozen=True, slots=True)
class RootCause:
    """One supportable root-cause hypothesis."""

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
    """Result of one analysis pass."""

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


def _usable(items: Iterable[Observation]) -> list[Observation]:
    return [item for item in items if item.status is not None]


def _all_down(items: Iterable[Observation]) -> bool:
    values = _usable(items)
    return bool(values) and all(item.status is False for item in values)


def _all_up(items: Iterable[Observation]) -> bool:
    values = _usable(items)
    return bool(values) and all(item.status is True for item in values)


def _any_up(items: Iterable[Observation]) -> bool:
    return any(item.status is True for item in items)


def _any_down(items: Iterable[Observation]) -> bool:
    return any(item.status is False for item in items)


def _names(items: Iterable[Observation]) -> tuple[str, ...]:
    return tuple(item.binding.label or item.binding.name for item in items)


def _failed_names(obs: ObservationSet) -> tuple[str, ...]:
    return tuple(
        item.binding.label or item.binding.name
        for item in obs.observations
        if item.status is False
    )


def _healthy_names(obs: ObservationSet) -> tuple[str, ...]:
    return tuple(
        item.binding.label or item.binding.name
        for item in obs.observations
        if item.status is True
    )


def _core_health_gaps(obs: ObservationSet) -> list[str]:
    """Return evidence gaps that prevent an all-clear Healthy verdict."""
    gaps = list(obs.required_gaps)
    if not obs.by_role(ROLE_GATEWAY):
        gaps.append("No gateway monitor is assigned")
    if not (obs.by_role(ROLE_IPV4) or obs.by_role(ROLE_IPV6)):
        gaps.append("No external IPv4 or IPv6 reachability control is assigned")
    if not obs.by_role(ROLE_DNS_NEUTRAL):
        gaps.append("No neutral DNS control is assigned")
    if not obs.by_role(ROLE_HTTPS):
        gaps.append("No HTTPS control is assigned")
    return list(dict.fromkeys(gaps))


def _coverage(obs: ObservationSet) -> list[str]:
    gaps = list(obs.coverage_gaps)
    gaps.extend(_core_health_gaps(obs))
    return list(dict.fromkeys(gaps))


def _result_from_causes(obs: ObservationSet, causes: list[RootCause]) -> DiagnosisResult:
    coverage_gaps = tuple(_coverage(obs))
    failed = _failed_names(obs)
    unaffected = _healthy_names(obs)
    if not causes:
        if failed:
            return DiagnosisResult(
                diagnosis=MIXED,
                summary="One or more monitors are failing, but the available independent controls do not support a single causal explanation.",
                confidence="low",
                evidence=tuple(f"Failed: {name}" for name in failed),
                unaffected=unaffected,
                failed_controls=failed,
                affected_components=failed,
                coverage_gaps=coverage_gaps,
                unassigned_monitors=tuple(obs.unassigned_monitors),
            )
        required_gaps = tuple(_core_health_gaps(obs))
        if required_gaps:
            return DiagnosisResult(
                diagnosis=MONITORING_INCOMPLETE,
                summary=(
                    "No active failure is detected in the available evidence, but required "
                    "diagnostic coverage is missing, so Network Diagnostics will not claim "
                    "the network is healthy."
                ),
                confidence="insufficient",
                evidence=("Available assigned monitors are not reporting a failure.",),
                unaffected=unaffected,
                monitoring_gaps=required_gaps,
                coverage_gaps=coverage_gaps,
                unassigned_monitors=tuple(obs.unassigned_monitors),
            )
        return DiagnosisResult(
            diagnosis=HEALTHY,
            summary="All required assigned diagnostic monitors are healthy.",
            confidence="high" if not coverage_gaps else "medium",
            evidence=("No assigned diagnostic monitor is reporting a failure.",),
            unaffected=unaffected,
            coverage_gaps=coverage_gaps,
            unassigned_monitors=tuple(obs.unassigned_monitors),
        )

    if len(causes) == 1:
        cause = causes[0]
        return DiagnosisResult(
            diagnosis=cause.name,
            summary=(
                f"{cause.name}. "
                + (cause.supporting[0] if cause.supporting else "The observed failure pattern matches this fault domain.")
            ),
            confidence=cause.confidence,
            evidence=cause.supporting,
            contradictions=cause.contradicting,
            downstream=cause.downstream,
            unaffected=unaffected,
            failed_controls=failed,
            affected_components=cause.affected,
            coverage_gaps=coverage_gaps,
            unassigned_monitors=tuple(obs.unassigned_monitors),
            root_causes=(cause,),
        )

    names = "; ".join(cause.name for cause in causes)
    return DiagnosisResult(
        diagnosis=MULTIPLE,
        summary=f"Multiple independent fault domains are present: {names}.",
        confidence="high" if all(cause.confidence == "high" for cause in causes) else "medium",
        evidence=tuple(item for cause in causes for item in cause.supporting),
        contradictions=tuple(item for cause in causes for item in cause.contradicting),
        downstream=tuple(item for cause in causes for item in cause.downstream),
        unaffected=unaffected,
        failed_controls=failed,
        affected_components=tuple(item for cause in causes for item in cause.affected),
        coverage_gaps=coverage_gaps,
        unassigned_monitors=tuple(obs.unassigned_monitors),
        root_causes=tuple(causes),
    )


def classify(obs: ObservationSet, *, degraded_mesh: set[str] | None = None) -> DiagnosisResult:
    """Classify current observations using explicit causal dependencies.

    The algorithm intentionally favors the smallest upstream explanation that
    accounts for downstream failures while independent controls remain healthy.
    It does not emit numerical pseudo-probabilities.
    """
    degraded_mesh = degraded_mesh or set()
    coverage_gaps = tuple(_coverage(obs))

    if obs.monitoring_gaps or not obs.provider_fresh:
        gaps = list(obs.monitoring_gaps)
        if not obs.provider_fresh:
            age = (
                f" ({obs.provider_age_seconds:.0f}s since the oldest required Kuma source heartbeat)"
                if obs.provider_age_seconds is not None
                else ""
            )
            gaps.append(f"Uptime Kuma data feed is stale or unavailable{age}")
        return DiagnosisResult(
            diagnosis=MONITORING_INCOMPLETE,
            summary="Required evidence is missing or stale, so Network Diagnostics will not claim the network is healthy or assign a root cause.",
            confidence="insufficient",
            monitoring_gaps=tuple(dict.fromkeys(gaps)),
            coverage_gaps=coverage_gaps,
            unassigned_monitors=tuple(obs.unassigned_monitors),
            failed_controls=_failed_names(obs),
            unaffected=_healthy_names(obs),
        )

    gateway = obs.by_role(ROLE_GATEWAY)
    lan = obs.by_role(ROLE_LAN_CONTROL)
    mesh = obs.by_role(ROLE_MESH)
    mesh_children = obs.by_role(ROLE_MESH_CHILD)
    ipv4 = obs.by_role(ROLE_IPV4)
    ipv6 = obs.by_role(ROLE_IPV6)
    dns_neutral = obs.by_role(ROLE_DNS_NEUTRAL)
    dns_local = obs.by_role(ROLE_DNS_LOCAL)
    https = obs.by_role(ROLE_HTTPS)

    causes: list[RootCause] = []

    # Local gateway/LAN root cause suppresses external symptoms as downstream.
    gateway_down = _all_down(gateway)
    gateway_management_only = False
    if gateway_down:
        downstream_failed = [
            item.binding.label or item.binding.name
            for item in obs.observations
            if item.status is False and item.binding.role != ROLE_LAN_CONTROL
        ]
        if lan and _any_up(lan):
            external_healthy = _any_up((*obs.by_role(ROLE_IPV4), *obs.by_role(ROLE_IPV6)))
            if external_healthy:
                causes.append(
                    RootCause(
                        "Gateway management/reachability failure",
                        "local",
                        "medium",
                        supporting=(
                            "The gateway monitor is down while an independent wired LAN control and external Internet reachability remain healthy.",
                        ),
                        contradicting=(
                            "A complete router/forwarding failure is contradicted by healthy external Internet reachability from Home Assistant.",
                        ),
                        affected=_names(gateway),
                        causal_path=("Home Assistant", "gateway management/reachability"),
                    )
                )
                # Forwarding to the Internet and an independent LAN control still
                # work, so the failed gateway management probe does not explain an
                # unrelated mesh/DNS/service failure. Continue looking for truly
                # concurrent faults rather than returning early.
                gateway_management_only = True
            else:
                causes.append(
                    RootCause(
                        "Gateway/router failure",
                        "local",
                        "high",
                        supporting=(
                            "The gateway monitor is down while an independent wired LAN control remains reachable.",
                        ),
                        downstream=tuple(name for name in downstream_failed if name not in _names(gateway)),
                        affected=_names(gateway),
                        causal_path=("gateway", "downstream network services"),
                    )
                )
                return _result_from_causes(obs, causes)
        elif lan and _all_down(lan):
            causes.append(
                RootCause(
                    "Local LAN / Home Assistant path failure",
                    "local",
                    "high",
                    supporting=(
                        "The gateway and independent wired LAN control are both unreachable from Home Assistant.",
                    ),
                    downstream=tuple(downstream_failed),
                    affected=tuple((*_names(gateway), *_names(lan))),
                    causal_path=("Home Assistant local path", "gateway", "downstream services"),
                )
            )
            return _result_from_causes(obs, causes)
        else:
            causes.append(
                RootCause(
                    "Gateway / local path failure",
                    "local",
                    "medium",
                    supporting=("The gateway is unreachable, but no independent wired LAN control is available to separate router failure from the HA-to-LAN path.",),
                    downstream=tuple(downstream_failed),
                    affected=_names(gateway),
                    causal_path=("gateway or HA local path", "downstream services"),
                )
            )
            return _result_from_causes(obs, causes)

    # A dedicated wired LAN control is intentionally an independent endpoint.
    # If it alone fails while the gateway remains reachable, localize that
    # observation rather than calling the whole LAN unhealthy or falling back to
    # an unexplained mixed state.
    if not gateway_down and lan and _any_down(lan):
        failed_lan = [item for item in lan if item.status is False]
        healthy_lan = [item for item in lan if item.status is True]
        causes.append(
            RootCause(
                "Partial LAN control failure" if healthy_lan else "LAN control endpoint/path failure",
                "local-control",
                "medium",
                supporting=(
                    "A wired LAN control is unreachable while the gateway remains reachable; this does not support a whole-LAN outage.",
                ),
                contradicting=(
                    "A broad local-LAN failure is contradicted by the reachable gateway.",
                ),
                affected=_names(failed_lan),
                causal_path=("gateway", "wired LAN control endpoint/path"),
            )
        )

    # Mesh failures are localized when the gateway itself is reachable. If only
    # gateway management/reachability is broken, healthy external + wired-LAN
    # evidence still shows that the forwarding path is viable enough to treat a
    # mesh-node failure as a separate finding.
    down_mesh = [item for item in mesh if item.status is False]
    if down_mesh:
        if len(down_mesh) == len(_usable(mesh)) and len(down_mesh) > 1:
            causes.append(
                RootCause(
                    "Mesh satellite/AP layer failure",
                    "mesh",
                    "high",
                    supporting=(
                        "Multiple mesh-node monitors are down while the gateway remains reachable.",
                    ),
                    affected=_names(down_mesh),
                    causal_path=("gateway", "mesh layer"),
                )
            )
        else:
            for item in down_mesh:
                label = item.binding.label or item.binding.name
                causes.append(
                    RootCause(
                        f"{label} unreachable",
                        "mesh",
                        "high",
                        supporting=(
                            (
                                f"{label} is down while gateway forwarding remains viable despite the separate gateway management/reachability failure."
                                if gateway_management_only
                                else f"{label} is down while the gateway remains reachable."
                            ),
                        ),
                        affected=(label,),
                        causal_path=("gateway", label),
                    )
                )

    # Optional fixed downstream controls can prove that traffic through a mesh
    # node is impaired even while the node's own management IP still answers.
    # A single child failure remains ambiguous between the child and its path;
    # two independent children behind the same node support a stronger path fault.
    mesh_by_label = {
        (item.binding.label or item.binding.name).casefold(): item for item in mesh
    }
    for group in sorted(
        {item.binding.group for item in mesh_children if item.binding.group},
        key=str.casefold,
    ):
        children = [
            item
            for item in mesh_children
            if (item.binding.group or "").casefold() == group.casefold()
        ]
        failed_children = [item for item in children if item.status is False]
        if not failed_children:
            continue
        parent = mesh_by_label.get(group.casefold())
        if parent is not None and parent.status is False:
            # The parent mesh-node root cause already explains these descendants.
            for idx, cause in enumerate(causes):
                if cause.domain != "mesh":
                    continue
                if (parent.binding.label or parent.binding.name) not in cause.affected:
                    continue
                causes[idx] = RootCause(
                    cause.name,
                    cause.domain,
                    cause.confidence,
                    supporting=cause.supporting,
                    contradicting=cause.contradicting,
                    downstream=tuple((*cause.downstream, *_names(failed_children))),
                    affected=cause.affected,
                    causal_path=cause.causal_path,
                )
            continue
        if parent is not None and parent.status is True:
            if len(failed_children) >= 2:
                causes.append(
                    RootCause(
                        f"{group} downstream/backhaul path failure",
                        "mesh",
                        "high",
                        supporting=(
                            f"Multiple fixed downstream controls behind {group} are down while the mesh node and gateway remain reachable.",
                        ),
                        contradicting=(
                            f"A complete {group} node outage is contradicted by the node itself remaining reachable.",
                        ),
                        affected=_names(failed_children),
                        causal_path=("gateway", group, "downstream/backhaul path"),
                    )
                )
            else:
                causes.append(
                    RootCause(
                        f"{group} downstream path/client failure",
                        "mesh",
                        "medium",
                        supporting=(
                            f"A fixed downstream control behind {group} is down while the mesh node and gateway remain reachable.",
                        ),
                        contradicting=(
                            "One downstream control cannot distinguish a client failure from the forwarding/backhaul path by itself.",
                        ),
                        affected=_names(failed_children),
                        causal_path=("gateway", group, "downstream path or client"),
                    )
                )

    for label in sorted(degraded_mesh):
        causes.append(
            RootCause(
                f"{label} latency degradation",
                "mesh",
                "medium",
                supporting=(f"{label} has sustained high response time while the gateway path remains materially healthier.",),
                affected=(label,),
                causal_path=("gateway", label, "degraded forwarding/backhaul candidate"),
            )
        )

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
                supporting=("All IPv4 controls are down while at least one IPv6 control remains healthy.",),
                contradicting=("A full WAN outage is contradicted by healthy IPv6 reachability.",),
                downstream=_names([item for item in (*dns_neutral, *dns_local, *https) if item.status is False]),
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
                supporting=("All IPv6 controls are down while at least one IPv4 control remains healthy.",),
                contradicting=("A full WAN outage is contradicted by healthy IPv4 reachability.",),
                downstream=_names([item for item in (*dns_neutral, *dns_local, *https) if item.status is False]),
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
                supporting=("External IP controls are unreachable while the local gateway remains reachable.",),
                downstream=_names([item for item in (*dns_neutral, *dns_local, *https) if item.status is False]),
                affected=_names(failed_external),
                causal_path=("gateway", "WAN/upstream Internet", "external services"),
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
                    supporting=("Some external reachability controls fail while others remain healthy.",),
                    affected=_names(partial_ip),
                    causal_path=("Internet", "specific target/path"),
                )
            )

    # If we already have a full upstream Internet root cause, DNS/HTTPS failures are downstream symptoms.
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
                    supporting=("Neutral DNS is failing while general IP reachability remains available.",),
                    contradicting=("A general Internet outage is contradicted by healthy IP controls.",),
                    downstream=_names([item for item in https if item.status is False]),
                    affected=_names([item for item in (*dns_neutral, *dns_local) if item.status is False]),
                    causal_path=("Internet IP", "DNS"),
                )
            )
        elif dns_local and local_down and neutral_up:
            causes.append(
                RootCause(
                    "Local DNS forwarder/upstream failure",
                    "dns",
                    "high",
                    supporting=("Local/router DNS is down while neutral DNS remains healthy.",),
                    contradicting=("General DNS failure is contradicted by healthy neutral DNS.",),
                    affected=_names(dns_local),
                    causal_path=("Internet", "local DNS forwarder"),
                )
            )

        # Service-specific groups (for example NextDNS).
        for group in obs.service_groups:
            service_dns = obs.by_service(ROLE_SERVICE_DNS, group)
            service_path = obs.by_service(ROLE_SERVICE_PATH, group)
            dns_all_down = _all_down(service_dns)
            path_all_down = _all_down(service_path)
            dns_any_up = _any_up(service_dns)
            path_any_up = _any_up(service_path)
            if dns_all_down and service_dns and path_all_down and service_path and neutral_up:
                causes.append(
                    RootCause(
                        f"{group} routing/path failure",
                        f"service:{group}",
                        "high",
                        supporting=(f"{group} DNS and path controls fail while neutral DNS and general Internet remain healthy.",),
                        contradicting=("General DNS failure is contradicted by healthy neutral DNS.",),
                        downstream=_names([item for item in dns_local if item.status is False]),
                        affected=_names([*service_dns, *service_path]),
                        causal_path=("Internet", f"{group} network path", f"{group} DNS service"),
                    )
                )
            elif dns_all_down and service_dns and (path_any_up or not service_path) and neutral_up:
                causes.append(
                    RootCause(
                        f"{group} DNS-service failure",
                        f"service:{group}",
                        "high" if len(_usable(service_dns)) >= 2 and service_path else "medium",
                        supporting=(f"{group} DNS checks fail while its network path and neutral DNS remain healthy.",),
                        affected=_names(service_dns),
                        causal_path=("Internet", f"{group} path", f"{group} DNS service"),
                    )
                )
            else:
                partial = [item for item in (*service_dns, *service_path) if item.status is False]
                if partial and (dns_any_up or path_any_up):
                    causes.append(
                        RootCause(
                            f"Partial {group} endpoint/path failure",
                            f"service:{group}",
                            "medium",
                            supporting=(f"Only part of the {group} evidence set is failing.",),
                            affected=_names(partial),
                            causal_path=("Internet", group, "specific endpoint/path"),
                        )
                    )

        if https and _all_down(https) and neutral_up:
            causes.append(
                RootCause(
                    "HTTPS-specific failure",
                    "https",
                    "medium",
                    supporting=("HTTPS controls fail while IP reachability and neutral DNS remain healthy.",),
                    affected=_names(https),
                    causal_path=("Internet", "DNS", "HTTPS/application layer"),
                )
            )

    # Avoid double counting a DNS-local symptom when a service-specific provider explains it.
    if any(cause.domain.startswith("service:") for cause in causes):
        causes = [
            cause
            for cause in causes
            if not (
                cause.name == "Local DNS forwarder/upstream failure"
                and any(item.status is False for item in dns_local)
            )
        ]

    # Collapse multiple mesh-node causes into one independent domain for the MULTIPLE decision.
    domains = []
    unique_causes: list[RootCause] = []
    for cause in causes:
        if cause.domain == "mesh":
            if "mesh" in domains:
                # Keep individual mesh causes so the UI names each affected node, but they are one domain.
                unique_causes.append(cause)
                continue
            domains.append("mesh")
            unique_causes.append(cause)
        else:
            domains.append(cause.domain)
            unique_causes.append(cause)

    # If all findings are within the mesh domain, summarize them as one root-domain result.
    if unique_causes and all(cause.domain == "mesh" for cause in unique_causes):
        if len(unique_causes) == 1:
            return _result_from_causes(obs, unique_causes)
        combined = RootCause(
            "Mesh layer impairment",
            "mesh",
            "high" if all(c.confidence == "high" for c in unique_causes) else "medium",
            supporting=tuple(item for c in unique_causes for item in c.supporting),
            affected=tuple(item for c in unique_causes for item in c.affected),
            causal_path=("gateway", "mesh layer", "multiple nodes"),
        )
        return _result_from_causes(obs, [combined])

    # Multiple distinct domains are truly concurrent faults.
    distinct_domains = {cause.domain for cause in unique_causes}
    if len(distinct_domains) > 1:
        return _result_from_causes(obs, unique_causes)

    return _result_from_causes(obs, unique_causes)
