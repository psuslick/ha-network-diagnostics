# Network Diagnostics v0.3.0

v0.3.0 is the privacy-safe, topology-generic rebuild of the prototype.

## Highlights

- Generic roles and arbitrary parent/child topology instead of deployment-specific profiles.
- Explicit config/reconfigure flow with coverage preview.
- Optional, readable Uptime Kuma Tag hints; tags are not a runtime dependency.
- Kuma monitor name is the canonical display name everywhere.
- Stable monitor identity is used for relationships rather than mutable entity IDs.
- Public Home Assistant registry/state boundary only; no access to the Uptime Kuma integration's private runtime data.
- Dependency-aware RCA with downstream symptom suppression, causal paths, supporting/contradicting evidence, and qualitative evidence strength.
- RAM-only adaptive response-time baselines with parent/sibling localization and sustained-degradation detection.
- Topology impact display.
- Compact incident lifecycle/history and recurrence fingerprints.
- Privacy-reduced downloadable diagnostics.
- Home Assistant Repairs for actionable configuration/evidence defects.
- No raw-network recorder inside Network Diagnostics and no automatic Recorder changes.
- Repository privacy validator and generic synthetic tests/examples.

## Upgrade note

Pre-v0.3 role mappings were inferred using prototype-specific rules. v0.3.0 intentionally requires one explicit reconfiguration after upgrade instead of silently carrying those assumptions into the generic topology model. Old prototype incident records are reset for the same reason.
