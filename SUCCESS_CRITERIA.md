# Network Diagnostics v0.3.2 success criteria

This file is the acceptance contract for the v0.3.2 package. It consolidates the decisions made through the prototype, privacy, architecture, and housekeeping reviews.

## Product value

1. **Benefit first.** The integration must improve diagnosis of the installing user's network rather than genericize away useful capability.
2. **Reusable causal model.** The same engine must support unrelated network topologies by modeling generic roles and explicit parent/child relationships instead of vendor, room, provider, or household-specific constants.
3. **Kuma remains the probe engine.** Network Diagnostics must make no ping, DNS, TCP, HTTP, or other target probes. It consumes state already exposed by Home Assistant's official Uptime Kuma integration.
4. **Explain, do not merely alarm.** Results must distinguish root-cause candidates, supporting evidence, contradicting evidence, downstream effects, causal paths, unaffected controls, and evidence strength.
5. **Dependency-aware RCA.** Failed descendants of a failed upstream node must be treated as downstream effects when the topology supports that explanation.
6. **Incident correlation.** Compact incidents must preserve start, transitions, recovery, evidence, causal fingerprint, and recurrence count without becoming a second raw time-series recorder.
7. **Adaptive degradation.** Eligible local infrastructure nodes must learn a bounded RAM-only response-time baseline and detect sustained degradation before outright failure. Parent/sibling evidence should strengthen or weaken localization.
8. **Topology impact.** The panel must show what a configured node depends on and what downstream monitors a failure at that node could explain.
9. **No pseudo-probabilities.** Confidence is qualitative (`high`, `medium`, `low`, `insufficient`) unless a future release introduces genuinely calibrated probabilities.

## Configuration and naming

10. **One canonical human name.** The Uptime Kuma monitor name is the display name everywhere Network Diagnostics shows that monitor. The integration does not invent room aliases or alternate device names.
11. **Stable machine identity.** Stored topology uses the Uptime Kuma monitor identity exposed through Home Assistant, not mutable Home Assistant entity IDs or friendly names.
12. **Explicit setup.** A Home Assistant config/reconfigure flow discovers Kuma monitors, assigns diagnostic roles, defines parent relationships, groups service controls, validates the resulting model, and previews diagnostic coverage.
13. **Kuma Tags are optional hints.** Clear Kuma Tags may prefill setup, but tag availability is never required at runtime and never silently rewrites confirmed topology.
14. **No HA Label abuse.** The integration does not create Home Assistant Labels to encode topology or duplicate monitor identity.
15. **Coverage is inspectable.** Setup and the panel state which fault classes the configured evidence can and cannot distinguish.

## Privacy and security

16. **No deployment data in distributable source.** Source, tests, fixtures, docs, examples, comments, manifests, and screenshots contain no real household/person names, device addresses, public/private deployment IPs, MACs, hostnames, service names learned from a deployment, credentials, or account identifiers.
17. **No telemetry/exfiltration.** The integration has no direct network client for probes, analytics, or telemetry. The custom panel communicates only through Home Assistant's authenticated WebSocket API and is admin-only.
18. **Privacy-reduced diagnostics.** Downloaded diagnostics omit targets and pseudonymize locally supplied monitor names, service names, and stable monitor identifiers.
19. **Repository privacy gate.** Local/CI validation rejects MAC-like values, non-documentation IP literals, non-example email addresses, and direct network-client imports in the integration.

## Home Assistant architecture

20. **UI-first and inspectable.** No YAML setup and no direct `.storage` editing. Topology lives in the config entry; behavior tuning lives in options.
21. **Reconfiguration without remove/re-add.** Topology and roles can be changed through a reconfigure flow.
22. **Public integration boundary.** Network Diagnostics uses Home Assistant public entity/device/config-entry/state interfaces and does not read another integration's private `runtime_data`.
23. **Event-driven.** Source-state changes trigger local analysis; a low-frequency watchdog only handles freshness/re-discovery. Network Diagnostics does not duplicate Kuma polling.
24. **Native HA surfaces plus deep panel.** Important status/coverage/incident state is exposed as standard HA entities while the integration-owned sidebar panel provides topology, evidence, impact, and incident detail.
25. **Actionable configuration defects use Repairs.** Missing configured monitors, stale evidence, setup-required state, and blocking evidence/topology errors create Home Assistant Repair issues when user action can resolve them.
26. **Bounded persistence.** Raw response samples remain in RAM and relearn after restart. Persistent storage contains only compact derived incident records and manual-analysis metadata.
27. **Migration is conservative.** Pre-v0.3 inferred mappings are not silently converted to the generic model; the user explicitly reconfigures once so obsolete assumptions cannot survive unnoticed.

## Data ownership and Home Assistant housekeeping

28. **One raw historian.** Uptime Kuma is authoritative for raw network measurements/history. Network Diagnostics never creates a second raw recorder.
29. **Recorder independence.** The integration does not silently modify Home Assistant Recorder. Recorder exclusions may be considered separately only after the replacement is live-verified and consumers of HA-side Kuma history are checked.
30. **Old logic remains until verification.** Installing/testing this package does not itself remove any existing diagnostic automation/helper. Replacement logic is superseded only after a live acceptance test proves the new integration.

## Refined criteria added during implementation

31. **Health and coverage are separate.** `Healthy` means all configured evidence is fresh and healthy; `Coverage: Partial` means additional fault classes cannot yet be distinguished. Optional evidence gaps alone must not force `Monitoring incomplete`.
32. **Duplicate independent evidence is blocking.** If controls intended to be independent are known to resolve to the same endpoint, the model must not grant independence-based confidence.
33. **Monitoring problems are not outage incidents.** Missing/stale/invalid monitoring raises monitoring/repair state but does not open a new network incident. If evidence disappears during an already-open network incident, the incident remains open because loss of evidence is not recovery.
34. **Adaptive localization is comparative.** A degraded child with a healthy parent and normal sibling is stronger localized evidence; a degraded ancestor suppresses redundant descendant degradation; multiple degraded mesh siblings can become shared mesh/wireless-layer evidence.
35. **Downloaded diagnostics are stricter than the live UI.** The live admin panel uses canonical Kuma names for usability, while shareable diagnostics pseudonymize local identifiers and names.
36. **Privacy applies to repository ownership metadata too.** The installable ZIP contains no personal publisher identity and no unresolved placeholder metadata. Publication-only GitHub documentation/issue/codeowner fields may be added later by `finalize_repo.py` using a neutral organization or project identity.

## Validation

37. Pure RCA, topology, target, baseline, tag, validation, incident-model, and package/privacy behavior must have automated tests.
38. Python compilation, JavaScript syntax, repository validation, privacy validation, source-manifest validation, publication-finalization simulation, ZIP extraction validation, and checksum verification must pass before release.
39. HACS/hassfest workflows must be included for repository-side validation. A package may be marked **PACKAGE-VALIDATED** before live installation, but not **VERIFIED** until a real Home Assistant installation completes the acceptance test.
40. **Validation must survive publication finalization.** The same automated test suite must pass both in the privacy-preserving installable state (publication metadata omitted) and after `finalize_repo.py` injects a valid publisher/repository identity. Repository metadata finalization must not change product behavior or invalidate tests.


## Refined criteria added after the v0.3.0 live acceptance failure

41. **Normal Integrations visibility.** Network Diagnostics must be classified so a loaded config entry appears on Home Assistant's normal **Settings → Devices & services → Integrations** surface. It must not use the `helper` integration type, which hides the entry from that surface.
42. **Reconfigure must be reachable from the integration card.** A migrated/unconfigured entry must remain loaded and expose the official reconfigure flow from the visible Network Diagnostics integration entry; the user must not need to remove/re-add it.
43. **Setup state is not a fault state.** After the conservative pre-v0.3 migration clears inferred mappings, status must read `Setup required`, Coverage must read `Not configured`, and `Monitoring problem` must remain off until configured evidence actually becomes missing/stale/invalid.
44. **Setup UX must explain what happened.** The panel and Repair issue must state that Kuma monitor discovery succeeded, report the number of discovered monitors, and direct the user to Network Diagnostics → Reconfigure. They must not present zero bindings as an outage.
45. **Install artifact metadata must be immediately usable.** The package installed into Home Assistant must contain no `REPLACE_WITH_*` or equivalent unresolved publisher placeholders. Privacy is preserved by omitting publication-only ownership/URL fields until publication finalization, not by shipping fake values.
46. **Patch upgrade must preserve the generic model.** v0.3.2 fixes integration visibility/setup UX/metadata without restoring vendor-specific sentinels, provider-specific profiles, magic friendly-name configuration, or private Uptime Kuma runtime access.

## Refined criteria added after the v0.3.1 live configuration failure

47. **DNS query name is not resolver identity.** For Kuma DNS monitors, Home Assistant's monitored-hostname value is the DNS query name. Network Diagnostics must never use that value to prove resolver equality or independence. If the resolver endpoint is not exposed through the supported public HA surface, endpoint identity is `unknown`.
48. **Unknown independence is usable but not promoted.** Controls whose endpoint identity cannot be verified may participate in diagnosis and must not be blocked as duplicates merely because their target identity is unknown. They also must not increase independence-based coverage or confidence as though independence had been proven.
49. **Portable configuration import.** Initial setup and reconfigure must offer a JSON file-upload path in addition to guided manual setup. The portable file identifies monitors by canonical Uptime Kuma names and may specify role, parent name, and service group. Import resolves those names to local stable monitor identities, validates against the currently discovered inventory, fails closed on missing/ambiguous/malformed references, and still requires the normal review/confirmation step before saving.
50. **Import privacy boundary.** Portable configuration files must not require or accept monitored targets, credentials, Home Assistant entity IDs, config-entry IDs, or other deployment internals. The distributable repository may contain only a synthetic example. A user-specific import file may exist separately from the public package as local configuration data.
