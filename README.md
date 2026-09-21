# Network Diagnostics

Network Diagnostics is a HACS custom integration that turns existing Uptime Kuma monitor states into topology-aware network diagnosis inside Home Assistant.

Uptime Kuma answers **which checks are healthy or failing**. Network Diagnostics adds the next layer: **which upstream explanation best accounts for the pattern, which failures are downstream effects, what evidence contradicts broader alternatives, and whether the same incident pattern has happened before**.

It performs no network probes itself.

## Architecture

```text
Uptime Kuma
  raw probes + raw history
        │
        ▼
Home Assistant official Uptime Kuma integration
  current monitor entities
        │
        ▼
Network Diagnostics
  roles + topology + causal reasoning
  RAM-only adaptive latency baselines
  compact derived incident history
        │
        ├── standard HA entities
        └── admin-only Network Diagnostics sidebar panel
```

Network Diagnostics uses Home Assistant's public entity/device/config-entry/state interfaces. It does not read the Uptime Kuma integration's private runtime objects and does not directly contact monitored targets.

## Why it is useful with different network topologies

The engine contains no vendor-specific topology. During setup, the user assigns generic roles to Kuma monitors and describes parent relationships. A simple installation can model a Gateway plus Internet and DNS controls. A larger installation can describe chains such as Gateway → Network Node → Mesh Node → Fixed Downstream Clients.

That graph lets the classifier apply dependency-aware reasoning. If an upstream node fails, failed descendants can be presented as effects rather than unrelated root causes. If a child fails while its parent and sibling controls remain healthy, localization becomes stronger.

Diagnostic capability scales with the evidence configured. The Coverage view explicitly lists what can and cannot currently be distinguished.

## Setup

Prerequisites:

- Home Assistant 2026.9.0 or newer
- HACS
- the official Home Assistant **Uptime Kuma** integration configured and exposing at least one monitor

Install Network Diagnostics as a HACS custom integration, restart Home Assistant when HACS requests it, then add **Network Diagnostics** under **Settings → Devices & services**.

The setup flow:

1. discovers Kuma monitors already exposed by Home Assistant;
2. asks which monitors should participate and what diagnostic role each has;
3. asks for parent relationships for local topology nodes;
4. groups service-specific DNS/path controls when used;
5. validates the evidence model and shows coverage gaps before saving.

Reconfigure the integration later to change topology; removal/re-add is not required.

See [KUMA_TAG_CONVENTION.md](KUMA_TAG_CONVENTION.md) for the optional Kuma Tags convention that can prefill setup when Home Assistant exposes an enabled Tags entity.

## Canonical naming

The **Uptime Kuma monitor name is the canonical display name**. Network Diagnostics does not create alternate room/device aliases.

Internally, topology uses stable Kuma monitor identity so a display-name change does not become the relationship key. Re-discovery uses the updated Kuma name for presentation.

## Diagnostic roles

Roles represent semantics, not brands:

- Gateway
- Network Node
- Mesh / Wireless Node
- Fixed Downstream Client
- LAN Control
- IPv4 Internet Control
- IPv6 Internet Control
- Independent DNS Control
- Local DNS Control
- Service DNS Control
- Service Path Control
- HTTPS Control

Two independent Fixed Downstream Clients behind one reachable local node provide stronger evidence of a shared forwarding/downstream-path failure than one client alone.

## Adaptive latency degradation

Gateway, Network Node, and Mesh / Wireless Node response times use a bounded in-memory rolling baseline. The detector uses a recent median, median absolute deviation, a minimum absolute increase, a ratio threshold, and a sustained-duration requirement.

The baseline is deliberately **RAM-only**. After a Home Assistant restart, the panel reports a learning state until enough fresh samples have accumulated. Network Diagnostics does not persist every Kuma latency sample and does not query Recorder continuously to rebuild the window.

Sibling and parent baselines are used as independent context when available. A single degraded mesh node with a healthy parent and normal sibling is stronger evidence of a localized path/node problem than degradation shared by all siblings.

## Incidents

Network Diagnostics persists compact derived incidents, not raw telemetry. An incident can retain:

- start/recovery time and duration;
- initial/current diagnosis and transitions;
- evidence strength;
- supporting/contradicting evidence;
- causal path/downstream effects;
- a compact evidence snapshot;
- a fingerprint for recurring-pattern counts.

Raw network measurement history remains Uptime Kuma's responsibility.

## Home Assistant entities

The integration exposes native HA entities for Status, Confidence, Coverage, Last incident, Incidents 24h, Monitoring problem, Active incident, Analyze now, and incident events. These make the result usable from ordinary HA dashboards and automations without requiring the custom panel.

The sidebar panel adds topology/impact, detailed evidence, adaptive-baseline state, coverage, and incident history.

## Repairs and configuration health

Actionable configuration defects are surfaced through Home Assistant Repairs, including setup-required state, configured Kuma monitors that disappeared, invalid evidence/topology configuration, and stale Kuma evidence.

A Coverage gap is different from a broken configuration. A network can be **Healthy within its configured scope** while Coverage remains **Partial**. The integration will not claim it can distinguish a fault class for which the necessary evidence was never configured.

## Privacy

The source tree contains no deployment topology or monitored targets. Runtime topology stays inside the installing Home Assistant instance. Downloaded integration diagnostics pseudonymize local monitor/service names and stable monitor identifiers and do not export monitored targets.

See [PRIVACY_AND_PUBLISHING.md](PRIVACY_AND_PUBLISHING.md).

## Data ownership / Recorder

Uptime Kuma is the authoritative raw network historian. Network Diagnostics does not create a second raw recorder. Its adaptive sample window is bounded RAM; only compact derived incidents are persisted.

The integration does **not** change Home Assistant Recorder exclusions. Whether to retain HA-side history for high-frequency Kuma entities is an independent user decision that should be made only after checking dashboards/automations that might rely on it.

## Known limitations

- Network Diagnostics can only reason from configured evidence. A vendor-specific radio/backhaul-quality indicator is not inferred from successful ping/latency alone.
- Optional Kuma Tags depend on what the official HA Uptime Kuma integration exposes and whether the Tags entity is enabled. Explicit setup remains the authority.
- Dynamic diagnosis narratives and the custom panel are currently English-only.
- The release ZIP can be package-validated locally; real Home Assistant behavior is not **VERIFIED** until a live installation completes acceptance testing.

## Development and validation

Run:

```bash
python tools/check_privacy.py
python tools/generate_source_manifest.py
python tools/check_repo.py --allow-placeholders
pytest
python -m compileall -q custom_components tests tools
node --check custom_components/network_diagnostics/frontend/network-diagnostics-panel.js
```

The repository also includes HACS and hassfest GitHub Actions.

The complete acceptance contract is [SUCCESS_CRITERIA.md](SUCCESS_CRITERIA.md).
