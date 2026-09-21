# Changelog

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
