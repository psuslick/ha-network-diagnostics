# Network Diagnostics v0.2.0

v0.2.0 is a major architecture revision focused on portability, zero manual HA entity mapping, and stronger causal diagnosis.

## Highlights

- Uptime Kuma remains the only network probe engine.
- Requires Home Assistant's official Uptime Kuma integration as the data source.
- Automatically discovers monitor roles from Kuma monitor names.
- Adds generic `[ND:...]` role markers so the integration is usable outside the original Orbi deployment.
- Preserves automatic compatibility with the existing Orbi + NextDNS monitor names.
- Replaces the Lovelace YAML deployment model with an integration-owned, admin-only Network Diagnostics sidebar panel.
- Adds deterministic root-cause evidence with supporting evidence, contradictions, downstream effects, and causal paths.
- Adds optional fixed `mesh-child` controls to distinguish a reachable mesh management IP from downstream forwarding/backhaul impairment.
- Adds qualitative high/medium/low/insufficient evidence strength; no uncalibrated numeric probabilities.
- Uses the official Uptime Kuma coordinator heartbeat for fail-closed provider-freshness detection.
- Adds semantic monitor validation and duplicate-evidence protection.
- Keeps incident history bounded at 200 completed incidents by default for NVMe/SSD-backed installations.
- Adds explicit v0.1 incident-store migration and malformed-record tolerance.
- Uses the current Home Assistant `ConfigFlowResult` / `OptionsFlowWithReload` config-flow pattern.
- Fails closed if the config entry exists but its runtime is not loaded when the sidebar requests data.
- Ships deterministic source checksums and regenerates them automatically when repository metadata is finalized.

## Breaking/configuration changes from v0.1

- Manual HA entity mappings are removed.
- Legacy HA Ping integrations are no longer required by Network Diagnostics.
- The packaged Lovelace dashboard YAML has been removed.
- Monitor purpose is now determined from either supported profile names or generic `[ND:...]` monitor-name markers.
- Netgear is no longer a required integration; vendor-specific entities may be useful supplemental evidence in future versions but the RCA core is Kuma-based.

## Orbi deployment additions

Add:

- `Orbi Satellite 1` → `192.168.1.11`
- `Orbi Sarah Room` → `192.168.1.20`

Recommended Kuma settings: 30 s interval, 2 retries, 10 s retry interval, 5 s timeout.

See `ORBI_NEXTDNS_SETUP.md` for the full profile and optional fixed downstream controls.

## Known limitation

Network Diagnostics cannot directly read proprietary Orbi backhaul-quality state. A satellite can remain reachable while its Orbi ring indicates a fair/degraded link. v0.2 reports what its evidence supports and surfaces this limitation instead of treating reachability as proof of good backhaul quality.
