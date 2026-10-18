"""Plain-language next checks derived only from available network evidence."""

from __future__ import annotations

from .models import RuntimeSnapshot


def triage_recommendations(snapshot: RuntimeSnapshot) -> list[str]:
    """Make diagnostic suggestions, not automated device/network changes."""
    diagnosis = snapshot.diagnosis
    if diagnosis.setup_required:
        return [
            "Open Network Diagnostics under Settings > Devices & services > Integrations and choose Reconfigure to assign Kuma monitor roles and parents."
        ]
    if diagnosis.monitoring_problem:
        return [
            "Restore fresh Uptime Kuma monitor evidence first; stale or missing readings are not proof of an outage.",
            "Verify the official Kuma integration has current status and response entities before interpreting the network.",
        ]

    checks: list[str] = []
    if any(item.get("flapping") for item in snapshot.observations):
        checks.append(
            "Compare recent brief Kuma status drops against the exact times of device/app symptoms. Two recoveries within 15 minutes indicate repeated reachability loss, not its cause."
        )
    if any(item.get("baseline_state") == "degraded" for item in snapshot.observations):
        checks.append(
            "Compare the slow endpoint with its healthy parent and siblings at the same time; check the physical link, local congestion and radio placement if applicable."
        )
    if any(item.get("status") is False for item in snapshot.observations):
        checks.append(
            "Compare failed endpoints with reachable siblings and upstream nodes in the topology; a healthy router alone cannot distinguish a device failure from its downstream path."
        )
        checks.append(
            "Use Uptime Kuma history to determine whether the failure is continuous or intermittent; this integration does not independently probe devices."
        )
    else:
        checks.append(
            "Reachability checks alone cannot rule out a device, cloud, application command-transport, or motion-detection delay. Compare exact action timestamps with device-integration logs."
        )
    if diagnosis.coverage_gaps:
        checks.append(
            "Review Coverage and add an independent LAN/control monitor in Kuma where needed to distinguish local endpoint problems from upstream network issues."
        )
    return checks[:4]
