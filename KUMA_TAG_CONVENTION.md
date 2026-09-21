# Uptime Kuma Tag convention

Network Diagnostics treats the Uptime Kuma monitor name as the single canonical human-readable name. A monitor named **Mesh Node 2** remains **Mesh Node 2** in Home Assistant entities, Network Diagnostics topology, evidence, and incidents.

Uptime Kuma Tags can make first-run setup faster. They are optional setup hints, not a runtime dependency. Home Assistant's Uptime Kuma Tags sensor is disabled by default upstream, so explicit setup must always remain sufficient.

| Uptime Kuma Tag name | Value | Purpose |
| --- | --- | --- |
| `Network Diagnostics` | `Enabled` | Marks the monitor as intentionally participating in Network Diagnostics. |
| `Network Diagnostics Role` | One role name below | Prefills the role in setup when the Tags entity is available. |
| `Network Diagnostics Parent` | Exact Kuma monitor name | Prefills the parent relationship when the name resolves uniquely. |
| `Network Diagnostics Service` | User-chosen service/group name | Groups related Service DNS and Service Path controls. |

Supported `Network Diagnostics Role` values:

- `Gateway`
- `Network Node`
- `Mesh / Wireless Node`
- `Fixed Downstream Client`
- `LAN Control`
- `IPv4 Internet Control`
- `IPv6 Internet Control`
- `Independent DNS Control`
- `Local DNS Control`
- `Service DNS Control`
- `Service Path Control`
- `HTTPS Control`

Example, using deliberately generic names:

```text
Monitor: Gateway A
  Network Diagnostics = Enabled
  Network Diagnostics Role = Gateway

Monitor: Mesh Node 2
  Network Diagnostics = Enabled
  Network Diagnostics Role = Mesh / Wireless Node
  Network Diagnostics Parent = Gateway A

Monitor: Fixed Client B
  Network Diagnostics = Enabled
  Network Diagnostics Role = Fixed Downstream Client
  Network Diagnostics Parent = Mesh Node 2
```

If Home Assistant does not expose an enabled Kuma Tags entity, setup still works: assign the same roles and relationships explicitly in the Network Diagnostics reconfigure flow. Confirmed assignments are stored locally in the Network Diagnostics config entry, so later tag availability cannot silently alter the diagnostic topology.

Home Assistant Labels are a different feature. Network Diagnostics does not create or require HA Labels for monitor identity or topology.
