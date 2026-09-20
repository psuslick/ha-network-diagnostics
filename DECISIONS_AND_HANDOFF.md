# Network Diagnostics v0.2.0 — Decisions and handoff

## Status

**PROPOSED / PACKAGE-VALIDATED**

The source package is intended for a new Git repository and HACS custom-repository installation. It has not yet been installed on the live Home Assistant instance, so it is not APPLIED or VERIFIED.

## Objective

The system must answer **what is going on with the network**, not merely reproduce a Kuma red/green dashboard.

Acceptance standard:

> Given a real or simulated incident, identify the smallest supportable failing domain, show supporting and contradicting evidence, distinguish downstream consequences from independent failures, retain the incident for later investigation, and explicitly report insufficient evidence rather than manufacturing certainty.

## Major architecture decisions

### Kuma remains the probe engine

Network Diagnostics performs no ping/DNS/TCP/HTTP probes. Uptime Kuma owns probe execution, retries/timeouts, response time, and raw history.

The official Home Assistant Uptime Kuma integration is the transport into HA. Network Diagnostics is the correlation/RCA layer.

### No direct Kuma API dependency

The package does not ask for Kuma credentials and does not use Kuma's private Socket.IO API. It observes the official HA integration already connected to Kuma.

### Monitor names are the configuration contract

Kuma tags were rejected as the hard contract because HA's tag entities are disabled by default and current HA/Kuma behavior around tags has had reliability issues. Generic users enroll monitors with explicit `[ND:...]` name markers. The original Orbi + NextDNS monitor names are a built-in compatibility profile.

### No manual HA entity mapping

Discovery groups Uptime Kuma entities by their stable monitor/config-entry identity and uses the official coordinator's current monitor inventory. Stale registry remnants are ignored when coordinator inventory is available.

### Integration-owned panel

v0.2 replaces the earlier plan to ship a Lovelace dashboard YAML file. The integration registers an admin-only **Network Diagnostics** sidebar panel and an admin-only local WebSocket API.

This avoids hidden `.storage` Lovelace mutation and means a clean installation does not require dashboard import/configuration.

## Root-cause model

The classifier is deterministic and topology-aware. It uses ideas common to mature monitoring/RCA systems:

- parent/dependency suppression: upstream causes explain downstream symptoms;
- independent controls: healthy controls can contradict a proposed cause;
- incident correlation: repeated transitions belong to one incident until recovery;
- qualitative evidence strength rather than uncalibrated numerical probabilities.

The package does not copy Checkmk/Zabbix/Netdata/PyRCA code.

## Monitoring completeness and fail-closed behavior

A missing or stale evidence source can never produce Healthy.

Core generic coverage for an all-clear requires:

- gateway;
- IPv4 or IPv6 external reachability;
- neutral DNS;
- HTTPS.

The Orbi + NextDNS profile declares its own richer required monitor set. Missing satellite/service controls are therefore visible blockers rather than silent reductions in capability.

## Provider freshness correction

A stable HA state does not prove that a polling provider stopped reporting; an unchanged `up` status may legitimately retain an old state timestamp.

v0.2 therefore listens to the official Uptime Kuma config entry's current `DataUpdateCoordinator`. Successful coordinator refreshes are the provider heartbeat. A stale/failed coordinator makes observations unusable and produces **Monitoring incomplete**.

This is an explicit compatibility boundary with Home Assistant's official Uptime Kuma implementation. If the runtime shape changes in a future HA release, the intended failure mode is Monitoring incomplete, not a false network verdict.

## Evidence validation

The package validates discovered roles before using them:

- DNS roles must use a DNS monitor when monitor type is known;
- literal IPv4/IPv6 targets must match their declared family;
- HTTPS role URLs must actually use HTTPS;
- duplicate non-DNS endpoints assigned to the same logical role/group are blockers because they are not independent evidence;
- mesh-child roles must reference an existing mesh-node label;
- duplicate mesh labels are blocked because parent/child relationships would be ambiguous;
- service DNS without service-path evidence (and vice versa) is surfaced as a coverage warning.

DNS-query targets are deliberately excluded from endpoint-duplicate detection because HA's exposed DNS monitor target describes the query hostname, not necessarily the configured resolver endpoint.

## Satellite/backhaul strategy

A mesh node's own management IP can remain reachable while client forwarding/backhaul is impaired.

v0.2 therefore supports optional fixed downstream controls:

`[ND:mesh-child:<mesh label>] <control label>`

- one failed fixed child while parent/gateway remain up → path/client ambiguity, medium evidence;
- two independent failed fixed children behind the same reachable parent → downstream/backhaul-path failure, high evidence;
- failed parent → children are downstream effects of the parent outage;
- sustained parent response time above the configured threshold and materially worse than gateway latency → mesh latency degradation candidate.

The integration does not claim direct knowledge of a proprietary vendor backhaul-quality LED/state that is not exposed to HA/Kuma.

## Incident model

Defaults:

- failure confirmation: 15 seconds;
- recovery confirmation: 60 seconds;
- provider stale threshold: 180 seconds;
- mesh latency threshold: 25 ms;
- mesh degradation duration: 90 seconds;
- completed incident retention: 200.

The 200-incident default reflects NVMe-backed HA storage. Storage remains bounded and transition-based; raw probe history stays in Kuma.

An active incident is not closed merely because monitoring disappears. Evidence loss becomes a transition to Monitoring incomplete, not recovery.

Each incident stores start/latest/recovery snapshots plus a bounded transition list. Fingerprints support recognition of repeated incident patterns.

## Storage migration

v0.2 includes an explicit Home Assistant `Store` migration path from v0.1 incident storage. Malformed individual historical records are skipped with a warning instead of preventing the integration from starting.

## Home Assistant API compatibility hardening

The final v0.2 source uses Home Assistant's current `ConfigFlowResult` typing and `OptionsFlowWithReload` pattern. It does not combine an options-flow auto-reload with a config-entry update listener. WebSocket runtime lookup uses a fail-closed `getattr(..., "runtime_data", None)` path so an unloaded/disabled entry returns `not_loaded` instead of raising.

Read-only checks against the live Home Assistant 2026.9.3 Uptime Kuma registry verified the unique-ID suffixes used by discovery (`status`, `response_time`, `type`, `hostname`, `url`, and `port`) on the current deployment.

## Source integrity

`SOURCE_MANIFEST.sha256` covers the clean repository source tree (excluding itself, VCS metadata, and generated caches). `tools/finalize_repo.py` regenerates this manifest after filling the real GitHub documentation/issue/codeowner values so repository finalization does not leave a stale checksum file.

## Security/privacy decisions

- panel requires admin;
- WebSocket commands require admin;
- no direct network I/O;
- no Kuma credentials stored;
- URL targets are sanitized before UI/diagnostics persistence;
- source fingerprints are one-way short hashes used only to detect accidental duplicate evidence;
- diagnostic/incident payloads are bounded.

## Current Orbi deployment

Verified node identities:

- RBR850 router — `192.168.1.1`, `C8:9E:43:DB:5E:F3`
- RBS850 Satellite 1 — `192.168.1.11`, `C8:9E:43:DD:89:08`
- RBS850 Sarah Room — `192.168.1.20`, `C8:9E:43:DD:86:88`

The Sarah Room identity was verified physically by MAC.

Required new Kuma monitors before live validation:

- `Orbi Satellite 1` → Ping `192.168.1.11`
- `Orbi Sarah Room` → Ping `192.168.1.20`

Recommended for both: interval 30 s, retries 2, retry interval 10 s, timeout 5 s.

Strongly recommended: one `LAN Control` wired router-side reference.

For deeper Sarah Room backhaul evidence, add one or preferably two fixed wired controls behind that RBS850 using the generic mesh-child naming contract. See `ORBI_NEXTDNS_SETUP.md`.

## Live cutover plan

The existing Template helper `sensor.network_fault_diagnosis` remains current until v0.2 passes live acceptance testing.

After v0.2 is VERIFIED:

1. mark the Template implementation SUPERSEDED;
2. remove the old helper;
3. retire/hide the old Network Diagnostics Lovelace dashboard if the new panel replaces it operationally;
4. update HA_CURRENT_STATE.md and HA_DECISION_LOG.md;
5. do not leave two long-term diagnosis engines active.

## Remaining concerns

1. **Direct Orbi backhaul quality is not observable.** A persistent amber RBS850 can remain software-healthy if it still answers normally and downstream controls remain healthy.
2. **Coordinator compatibility.** v0.2 intentionally reads the current official Uptime Kuma coordinator in memory without polling it. Future HA changes could require an adapter update; the package should fail closed meanwhile.
3. **Kuma DNS resolver identity.** HA does not expose enough resolver metadata to prove that two DNS checks are truly independent merely because they are separate monitors.
4. **Actual topology.** A mesh system may daisy-chain nodes. v0.2 localizes individual/multiple mesh failures but does not yet model arbitrary mesh-parent chains. Add explicit mesh-parent topology in a later release if live evidence shows it materially changes diagnosis.

## Live acceptance tests

Do not mark VERIFIED until at minimum:

1. healthy complete evidence → Healthy;
2. missing/stale Kuma feed → Monitoring incomplete;
3. Sarah satellite only down → Sarah Room unreachable;
4. other satellite only down → Satellite 1 unreachable;
5. one fixed Sarah child down → medium path/client result;
6. two independent Sarah children down → high downstream/backhaul-path result;
7. sustained Sarah latency degradation → medium latency result;
8. NextDNS path/DNS failure patterns classify correctly with neutral controls healthy;
9. IPv4/IPv6/WAN patterns classify correctly;
10. incident start/update/recovery persists through reload/restart;
11. panel loads for admin and Analyze now performs only local analysis;
12. non-admin users cannot use the panel WebSocket API;
13. satellite target IPs are confirmed reserved/stable.
