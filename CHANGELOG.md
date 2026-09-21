# Changelog

## 0.3.2

- Changed Home Assistant `integration_type` from `helper` to `service` so Network Diagnostics is visible and manageable on the normal Integrations page.
- Changed the conservative migrated/unconfigured state from `Monitoring incomplete` to `Setup required`.
- Coverage now reports `Not configured` until the role/topology reconfigure flow is completed.
- `Monitoring problem` no longer turns on solely because one-time migration setup is pending.
- Setup Repair/panel copy now explains that Kuma discovery succeeded and points to the Network Diagnostics Reconfigure flow.
- Removed unresolved repository-owner placeholders from the installable manifest; publication metadata is omitted until explicit finalization.
- Preserved the v0.3 generic topology, privacy model, RCA engine, RAM-only baselines, and one-raw-historian architecture.

## 0.3.0

- Rebuilt configuration around generic monitor roles and explicit topology.
- Removed vendor/provider/deployment-specific discovery profiles and magic monitor-name contracts.
- Made the Uptime Kuma monitor name canonical for all human-facing monitor references.
- Added optional readable Kuma Tag hints and explicit reconfigure flow.
- Added arbitrary parent/child topology and impact analysis.
- Added dependency-aware root-cause suppression and generic service correlation.
- Added bounded RAM-only median/MAD adaptive response-time baselines with parent/sibling context.
- Added privacy-reduced downloadable diagnostics and repository privacy validation.
- Added Repairs for setup-required, missing monitor, invalid model, and stale-evidence conditions.
- Separated configured-scope health from breadth of diagnostic coverage.
- Made duplicate supposedly independent endpoints a blocking evidence-model error.
- Removed direct dependence on another integration's private runtime objects.
- Preserved compact incident lifecycle, transition, recovery, and recurrence tracking without raw time-series persistence.
