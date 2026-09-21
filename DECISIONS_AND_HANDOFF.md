# v0.3.2 decisions and handoff

## Status

**PROPOSED / PACKAGE-VALIDATED target.** Building this repository does not change a live Home Assistant installation. v0.3.0 was installed and failed the first live UX acceptance check; v0.3.2 is the corrective patch and remains unverified until installed and exercised live.

## Major architecture decisions

### Generic topology, user-specific configuration

The source understands generic roles and parent/child relationships. It contains no special profile for a particular router, mesh system, DNS provider, room, household, or deployment. The installing Home Assistant config entry holds the selected Kuma monitor identities, roles, parent relationships, and service-group display names.

### Canonical name

The Uptime Kuma monitor name is the only human-facing monitor name Network Diagnostics uses. Stable Kuma monitor identity is used for relationships and incident fingerprints so presentation does not become the primary key.

### Kuma Tags

Tags are optional setup hints with the convention documented in `KUMA_TAG_CONVENTION.md`. Confirmed setup is authoritative. This avoids making runtime health depend on optional/disabled tag entities.

### Public Home Assistant boundary

Network Diagnostics discovers monitor devices/entities from Home Assistant registries and consumes states. It does not inspect the Uptime Kuma integration's private runtime coordinator/data structures and does not call Kuma directly.

### Raw history ownership

Uptime Kuma owns raw probe history. Home Assistant owns current state and whatever Recorder history the user independently chooses to retain. Network Diagnostics owns only topology/configuration, bounded RAM-only adaptive baselines, and compact derived incidents.

### RCA influences retained from external systems

The implementation intentionally incorporates general ideas found useful during prior research without copying their source implementations:

- dependency/parent semantics and downstream suppression;
- incident correlation and transition/recovery lifecycle;
- explicit causal paths plus supporting/contradicting evidence;
- adaptive degradation context;
- qualitative evidence strength and recurring-pattern counts.

No external RCA/ML runtime library is required.

## Refinements made during implementation

- Healthy scope is separated from breadth of coverage.
- Duplicate supposedly independent controls are blocking when the shared target is known.
- Missing/stale/invalid monitoring does not create a new network-outage incident.
- Adaptive degradation compares node, parent, and sibling context and suppresses redundant descendant conclusions.
- Downloaded diagnostics pseudonymize deployment-specific names and stable monitor IDs; the live admin panel keeps canonical Kuma names.
- Pre-v0.3 inferred mappings and incident history are not silently migrated into the generic model.

## Live acceptance test after installation

After repository-side validation and installation:

- reconfigure monitor roles/topology explicitly;
- confirm canonical names match Kuma everywhere;
- confirm Coverage matches expected evidence;
- confirm current healthy evidence does not produce false `Monitoring incomplete`;
- observe a real or controlled monitor failure and verify upstream/downstream reasoning;
- verify adaptive baselines learn after enough fresh samples;
- verify no duplicate raw polling is introduced;
- only then consider the package **VERIFIED** and retire legacy diagnostic logic.

## Rollback

Uninstall/disable Network Diagnostics or restore the previous HACS version. The integration does not modify Kuma monitors, Recorder configuration, existing automations/helpers, or network devices, so package rollback does not require reversing those systems.


## v0.3.0 live acceptance failure and v0.3.2 corrective decisions

Live Home Assistant inspection established that v0.3.0 itself loaded, created its entities, and discovered all available Kuma monitors, but its manifest classified Network Diagnostics as an HA `helper`. That kept the loaded config entry off the normal Integrations page, making the intended Reconfigure workflow effectively inaccessible. The migrated entry also presented `Monitoring incomplete`/`Monitoring problem` even though the actual condition was simply that one-time generic topology setup had not been completed. Finally, the install artifact still contained publisher placeholders.

v0.3.2 therefore:

- changes `integration_type` to `service`;
- keeps conservative explicit migration, but reports the unconfigured migration state as `Setup required`, not a monitoring/network failure;
- reports Coverage as `Not configured` until role/topology setup is complete;
- keeps `Monitoring problem` off while merely unconfigured;
- makes the Repair/panel instructions explicitly direct the user to the visible integration's Reconfigure flow;
- removes unresolved publisher placeholders from the installable manifest; and
- preserves the generic/private-data-free RCA model introduced in v0.3.0.

## v0.3.2 live-validation refinements

### DNS query names are not resolver endpoints

The v0.3.1 live reconfigure flow exposed a false blocker: two DNS monitors intentionally querying the same hostname were classified as duplicate endpoints. In Uptime Kuma's HA entities, the monitored hostname is the DNS query name, not the resolver target. v0.3.2 therefore treats DNS resolver identity as unknown unless the supported public HA surface exposes a true resolver endpoint. Unknown identity is accepted but does not increase independence-based confidence.

### Portable configuration upload

The config/reconfigure flow now offers either guided manual setup or a native Home Assistant JSON file upload. The portable file contains only canonical Kuma names and semantic role/topology/service metadata. It is resolved against the current live Kuma inventory and goes through the same blockers/warnings/coverage review before saving. This is intended to make complex installations repeatable without embedding deployment data in the public codebase.
