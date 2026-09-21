# v0.3.0 decisions and handoff

## Status

**PROPOSED / PACKAGE-VALIDATED target.** Building this repository does not change a live Home Assistant installation. Existing diagnostic logic remains current until v0.3.0 is installed and live-verified.

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
