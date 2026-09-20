# Orbi + NextDNS setup profile

This profile is the deployment used to design Network Diagnostics v0.2.0. The exact Kuma monitor names below are recognized automatically, so the existing monitors do not need `[ND:...]` prefixes.

## Verified network identities for this deployment

| Node | Address | MAC |
|---|---|---|
| RBR850 router | `192.168.1.1` | `C8:9E:43:DB:5E:F3` |
| RBS850 Satellite 1 | `192.168.1.11` | `C8:9E:43:DD:89:08` |
| RBS850 Sarah Room | `192.168.1.20` | `C8:9E:43:DD:86:88` |

The Sarah Room mapping was physically verified by MAC address.

Before long-term monitoring, make sure `.11` and `.20` are stable DHCP reservations/static assignments. Monitoring a lease that later moves would create misleading history.

## Required Kuma monitors

The profile expects all of these names:

### Local / mesh

- `Orbi LAN`
- `Orbi Satellite 1`
- `Orbi Sarah Room`

### Internet controls

- `Internet IPv4`
- `Google IPv4`
- `Internet IPv6`
- `Google IPv6`
- `Internet HTTPS`

### DNS controls

- `DNS via Cloudflare`
- `DNS via Orbi`
- `DNS via NextDNS 1`
- `DNS via NextDNS 2`

### NextDNS path controls

- `NextDNS IPv4 1`
- `NextDNS IPv4 2`
- `NextDNS IPv6 1`
- `NextDNS IPv6 2`
- `NextDNS TCP 443 1`
- `NextDNS TCP 443 2`

Until the required set is complete, the panel reports **Monitoring incomplete** rather than claiming Healthy.

## Add the two satellite monitors

### Orbi Satellite 1

- Kuma type: **Ping**
- Name: `Orbi Satellite 1`
- Host: `192.168.1.11`
- Heartbeat interval: **30 seconds**
- Retries: **2**
- Retry interval: **10 seconds**
- Timeout: **5 seconds**

### Orbi Sarah Room

- Kuma type: **Ping**
- Name: `Orbi Sarah Room`
- Host: `192.168.1.20`
- Heartbeat interval: **30 seconds**
- Retries: **2**
- Retry interval: **10 seconds**
- Timeout: **5 seconds**

Once the official Home Assistant Uptime Kuma integration exposes these monitors, Network Diagnostics should discover them automatically. No HA entity IDs need to be entered.

## Strongly recommended: LAN Control

Create one additional Kuma Ping monitor named exactly:

`LAN Control`

Target a stable, always-on **wired device on the router-side LAN** that does not depend on either RBS850 backhaul.

Good candidates are infrastructure devices that stay powered and are directly wired to the RBR850/router-side Ethernet path.

Do not use:

- a phone;
- a laptop;
- a sleeping desktop;
- a roaming Wi-Fi client;
- a device Ethernet-connected to a satellite.

Why it matters:

- router down + LAN Control up helps localize the gateway itself;
- router down + LAN Control down supports a broader HA/LAN-path failure;
- router monitor down + LAN Control up + Internet still healthy points toward gateway management/reachability rather than a complete forwarding failure.

## Optional: prove more about Sarah Room backhaul

The RBS850 can remain pingable while its main ring reports a degraded/fair backhaul. To observe forwarding through that satellite rather than only its management IP, add fixed downstream controls.

Best evidence is an always-on device **Ethernet-connected to the Sarah Room RBS850**. A Wi-Fi phone or laptop can roam and is not a reliable physical dependency.

Use generic role names for these optional controls, for example:

```text
[ND:mesh-child:Sarah Room] Sarah wired control A
[ND:mesh-child:Sarah Room] Sarah wired control B
```

Recommended probe type: Ping, with the same 30-second cadence unless the endpoint requires a different check.

Interpretation:

- Sarah RBS850 down → `Sarah Room unreachable`;
- Sarah RBS850 up + one fixed child down → `Sarah Room downstream path/client failure` (medium evidence);
- Sarah RBS850 up + two independent fixed children down → `Sarah Room downstream/backhaul path failure` (high evidence);
- Sarah RBS850 remains reachable but has sustained high latency compared with the router → `Sarah Room latency degradation` (medium evidence).

The package does **not** call an amber ring a software-verified backhaul failure unless available evidence supports that conclusion.

## Live acceptance tests after installation

Do not mark the deployment VERIFIED until these are exercised or observed:

1. Complete healthy evidence → **Healthy**.
2. Remove/stall required Kuma evidence → **Monitoring incomplete**, never false Healthy.
3. Make only `Orbi Sarah Room` fail → localized Sarah Room diagnosis.
4. Make only `Orbi Satellite 1` fail → localized Satellite 1 diagnosis.
5. One fixed Sarah child fails while `.20` stays up → medium path/client ambiguity.
6. Two independent fixed Sarah children fail while `.20` stays up → high downstream/backhaul-path finding.
7. Sustained Sarah satellite latency crosses threshold while gateway remains materially healthier → latency degradation.
8. NextDNS DNS/path controls fail while neutral DNS and general Internet remain healthy → NextDNS-specific diagnosis.
9. General external IPv4/IPv6 controls fail together → upstream Internet/WAN diagnosis.
10. Incident start/update/recovery survives integration reload/HA restart.
11. Network Diagnostics sidebar panel loads and **Analyze now** recomputes without network I/O.

After successful side-by-side validation, retire the old `sensor.network_fault_diagnosis` Template helper so two diagnosis engines are not left active indefinitely.
