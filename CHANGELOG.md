# Changelog

## 0.2.0 - 2026-09-20

- Rebuilt monitor enrollment around automatic Uptime Kuma discovery instead of manual HA entity mapping.
- Added generic `[ND:...]` monitor-name roles and built-in Orbi + NextDNS profile compatibility.
- Made the official HA Uptime Kuma integration the sole data transport; Network Diagnostics performs no duplicate probes and stores no Kuma credentials.
- Added an integration-owned admin-only Network Diagnostics sidebar panel and local admin-only WebSocket API.
- Removed the packaged Lovelace dashboard dependency and legacy HA Ping dependency.
- Added topology-aware root-cause evidence, causal paths, contradictions, downstream symptom suppression, and concurrent-fault handling.
- Added fixed `mesh-child` controls for stronger downstream/backhaul diagnosis while a mesh node remains reachable.
- Added sustained mesh latency degradation detection relative to the gateway path.
- Added fail-closed coordinator freshness checking.
- Added semantic role validation and duplicate non-DNS endpoint protection.
- Added gateway-management versus complete gateway-failure differentiation.
- Added localized wired LAN-control failure handling.
- Added explicit v0.1 incident-store migration and malformed stored-record tolerance.
- Increased bounded completed-incident retention to 200 for NVMe/SSD-backed HA storage.
- Updated config-flow typing to the current Home Assistant `ConfigFlowResult` API and retained `OptionsFlowWithReload` behavior.
- Made sidebar WebSocket runtime lookup fail closed when the integration entry exists but is not loaded.
- Added deterministic source-manifest generation and automatic checksum regeneration after repository finalization.

## 0.1.0 - 2026-09-19

- Initial prototype HACS package around manually mapped HA entities and a Lovelace dashboard replacement.
- Established Kuma-as-probe / HA-as-diagnosis architecture and semantic incident history.
