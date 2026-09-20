# Network Diagnostics for Home Assistant

Network Diagnostics is a HACS custom integration that turns **Uptime Kuma measurements into topology-aware network diagnosis** inside Home Assistant.

> **Uptime Kuma measures. Network Diagnostics explains.**

The integration does **not** ping hosts, query DNS, open TCP connections, or fetch websites. Uptime Kuma remains the probe and raw-history engine. Network Diagnostics consumes the monitors already exposed by Home Assistant's official **Uptime Kuma** integration and correlates them into root-cause hypotheses, downstream effects, monitoring gaps, and retained incidents.

## Status

**v0.2.0 — PROPOSED / package-validated.**

The package is locally tested and repository-validated. It is not **APPLIED** or **VERIFIED** until installed and exercised on a real Home Assistant system.

## What you get

After adding Network Diagnostics, Home Assistant gets:

- an admin-only **Network Diagnostics** sidebar panel;
- a current diagnosis with qualitative evidence strength;
- supporting and contradicting evidence;
- downstream-effect suppression so one upstream failure does not look like many independent failures;
- explicit monitoring/coverage gaps;
- automatic incident start/update/recovery tracking;
- retained incident snapshots for later investigation;
- an **Analyze now** action;
- Home Assistant entities for status, confidence, coverage, active/last incident, incident count, and incident events;
- downloadable integration diagnostics.

No Lovelace YAML, template helper, automation, HA Ping integration, or manual entity-ID mapping is required.

## Architecture

```text
Uptime Kuma
  ├─ ping / DNS / TCP / HTTP(S) probes
  ├─ retries and timeouts
  └─ raw latency / uptime history
        │
        ▼
Official Home Assistant Uptime Kuma integration
        │
        ▼
Network Diagnostics
  ├─ automatic monitor-role discovery
  ├─ evidence validation / freshness checking
  ├─ topology-aware causal classification
  ├─ downstream symptom suppression
  ├─ incident correlation / persistence
  └─ admin-only Network Diagnostics panel
```

Network Diagnostics performs no additional network polling. It listens to the official Uptime Kuma coordinator already present in Home Assistant and to the HA entities that coordinator owns.

## Installation

### Prerequisites

1. Home Assistant **2026.9.0 or newer**.
2. Uptime Kuma.
3. Home Assistant's official **Uptime Kuma** integration configured and loaded.
4. HACS.

For the Home Assistant OS Uptime Kuma App, the App publishes discovery information to Home Assistant. For an external Kuma instance, configure the official HA Uptime Kuma integration normally.

### Install through HACS

1. Add this repository to HACS as a **Custom repository** of type **Integration**.
2. Install **Network Diagnostics**.
3. Restart Home Assistant if HACS requests it.
4. Go to **Settings → Devices & services → Add integration → Network Diagnostics**.
5. Open **Network Diagnostics** from the sidebar.

The config flow contains no monitor mapping form. Monitor assignment comes from the Kuma monitor names described below.

## Generic Kuma naming contract

A monitor is enrolled by prefixing its Kuma name with a Network Diagnostics role marker. The text after the marker is the human-facing label.

| Kuma monitor name | Meaning |
|---|---|
| `[ND:gateway] Main Router` | local gateway/router reachability |
| `[ND:lan-control] Wired LAN Control` | independent always-on wired LAN reference |
| `[ND:mesh] Upstairs AP` | mesh satellite / access point |
| `[ND:mesh-child:Upstairs AP] Wired TV` | fixed endpoint physically downstream of that mesh node |
| `[ND:ipv4] Cloudflare IPv4` | independent IPv4 Internet control |
| `[ND:ipv6] Cloudflare IPv6` | independent IPv6 Internet control |
| `[ND:dns-neutral] Cloudflare DNS` | DNS control independent of the home's configured DNS path |
| `[ND:dns-local] Router DNS` | DNS through the local router/resolver |
| `[ND:https] Internet HTTPS` | HTTPS/application-layer control |
| `[ND:service:NextDNS:dns] Resolver 1` | service-specific DNS check |
| `[ND:service:NextDNS:path] IPv6 path 1` | service-specific network-path check |

Unknown Kuma monitors are ignored and listed as **Unassigned monitors** in the panel. Network Diagnostics never guesses an arbitrary monitor's purpose from an IP address alone.

### Minimum evidence for a Healthy verdict

Network Diagnostics will not claim **Healthy** unless it has at least:

- one `gateway` monitor;
- at least one `ipv4` or `ipv6` Internet control;
- one `dns-neutral` control; and
- one `https` control.

Additional independent controls increase what the classifier can distinguish. For example, independent IPv4 and IPv6 controls can separate family-specific failures from a broader WAN outage.

## Built-in Orbi + NextDNS profile

The integration recognizes the existing monitor names used by the original Orbi + NextDNS deployment without requiring `[ND:...]` renames. See [ORBI_NEXTDNS_SETUP.md](ORBI_NEXTDNS_SETUP.md) for the complete monitor list and the two required satellite monitors.

## Root-cause behavior

The classifier is deterministic. It does not generate numerical pseudo-probabilities.

Examples of supported findings include:

- gateway management/reachability failure;
- gateway/router failure;
- local HA/LAN path failure;
- individual mesh-node outage;
- mesh-layer impairment;
- sustained mesh latency degradation;
- fixed downstream mesh path/client failure;
- stronger downstream/backhaul-path evidence when multiple fixed children fail together;
- IPv4-only or IPv6-only failure;
- upstream Internet/WAN failure;
- partial Internet target/path failure;
- general DNS failure;
- local DNS forwarder/upstream failure;
- service-specific DNS, routing/path, or partial endpoint failure;
- HTTPS-specific failure;
- multiple concurrent fault domains;
- Monitoring incomplete;
- Mixed / insufficient evidence;
- Healthy.

The classifier favors the smallest supported upstream explanation and labels downstream failures as consequences when the evidence permits it.

## Mesh/backhaul diagnosis

A pingable mesh node is not proof that its forwarding/backhaul path is healthy.

For stronger diagnosis, add one or preferably two **fixed, always-on, non-roaming endpoints physically behind a mesh node**, for example a device Ethernet-connected to that satellite/AP:

```text
[ND:mesh] Upstairs AP
[ND:mesh-child:Upstairs AP] Wired control A
[ND:mesh-child:Upstairs AP] Wired control B
```

Interpretation:

- mesh node down, gateway up → localized mesh-node outage;
- mesh node up + one fixed child down → path **or client** failure, medium evidence;
- mesh node up + two independent fixed children down → downstream/backhaul path failure, high evidence;
- sustained mesh-node latency materially above the gateway path → latency degradation candidate.

Network Diagnostics does not pretend that these observations equal a vendor's proprietary radio-quality indicator. If the vendor reports a degraded backhaul while all available Kuma evidence is healthy, the panel explicitly retains that observability limitation.

## Monitoring freshness

Stable `up` state entities can remain unchanged for a long time even while Kuma is functioning normally. Network Diagnostics therefore does **not** use a stable status entity's `last_changed` timestamp as the provider heartbeat.

On Home Assistant 2026.9, it listens to the official Uptime Kuma integration's existing `DataUpdateCoordinator`. A successful coordinator update refreshes the provider heartbeat; a failed or stale coordinator causes **Monitoring incomplete**. This is an intentional fail-closed design.

This is a compatibility boundary: Network Diagnostics depends on the current official Uptime Kuma integration runtime exposing a standard coordinator through its config entry. If Home Assistant changes that implementation in a future release, the integration should fail to **Monitoring incomplete** rather than manufacture a network diagnosis.

## Incident history

Default behavior:

- abnormal diagnosis confirmation: **15 s**;
- recovery confirmation: **60 s**;
- Kuma provider stale threshold: **180 s**;
- mesh latency threshold: **25 ms**;
- sustained mesh-latency duration: **90 s**;
- completed incident retention: **200**.

These can be changed under **Settings → Devices & services → Network Diagnostics → Configure**.

Incident history stores semantic transitions and bounded snapshots, not every Kuma heartbeat. Uptime Kuma remains the raw time-series/history source.

The 200-incident default is appropriate for SSD/NVMe-backed HA storage. It remains bounded to avoid creating an unbounded internal database.

## Privacy and security

- The sidebar panel and its WebSocket commands require an HA **admin** user.
- Network Diagnostics makes no direct network requests.
- It does not need Kuma credentials.
- URL targets are sanitized before appearing in the panel or diagnostic export; credentials, paths, query strings, and fragments are removed.
- Incident transition history is bounded.

## Limitations

- Network Diagnostics can only reason from evidence that Kuma/HA exposes.
- It cannot directly read proprietary Wi-Fi backhaul-quality states unless another integration exposes them.
- A single downstream endpoint failure cannot prove a backhaul failure; the endpoint itself may have failed.
- DNS monitor metadata exposed by HA does not reliably identify the configured resolver endpoint, so two DNS checks querying the same hostname are not automatically considered duplicates.
- The v0.2 provider-freshness implementation intentionally relies on the current HA Uptime Kuma coordinator shape. It fails closed if that evidence disappears.

## Repository validation

Before the GitHub repository exists, the manifest intentionally contains `REPLACE_WITH_...` placeholders. After creating the repo:

```bash
python tools/finalize_repo.py \
  --repo-url https://github.com/YOUR_ACCOUNT/ha-network-diagnostics

python tools/check_repo.py
pytest
```

The repository includes GitHub Actions for unit tests, HACS validation, and Home Assistant hassfest validation.

See [REPOSITORY_SETUP.md](REPOSITORY_SETUP.md) and [DECISIONS_AND_HANDOFF.md](DECISIONS_AND_HANDOFF.md).

## License

MIT. See [LICENSE](LICENSE).
