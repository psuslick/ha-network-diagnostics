# Network Diagnostics v0.4.0 — Intermittent Reachability & Local Device Evidence

**Status:** Candidate / not yet live-verified in Home Assistant.

## What's new

1. **Brief-outage memory:** two Kuma-observed DOWN/UP recoveries in 15 minutes can now trigger an intermittent-reachability incident while the monitor is UP. State and counters live only in RAM; evidence gaps never create synthetic failures.
2. **Local endpoint latency:** Fixed Downstream Clients now have adaptive response-time assessments, with relevant parent/sibling comparisons. This allows local device and hub reachability to be compared without vendor-specific code.
3. **More conservative root causes:** a router that answers pings while multiple descendants fail is not automatically blamed for forwarding failure. Shared-path versus separate device problems remain explicitly unresolved without independent evidence.
4. **Stronger measurement hygiene:** stale/negative/nonfinite response readings cannot corrupt latency baselines; lost samples break the sustained-anomaly timer.
5. **More useful dashboard:** incident count, flapping endpoints, evidence age, recent recoveries, and prioritized next diagnostic checks.
   A new native **Flapping monitors** sensor also exposes the number and names of currently intermittent endpoints for optional Home Assistant automations.
6. **Better incident fingerprints:** affected stable monitor identity distinguishes recurrent latency/flapping patterns even when no monitor is currently DOWN.

## Preserved from v0.3.2

- Existing config entry, role assignments, parents, service groups, and options are unchanged; no required migration or reconfiguration on upgrade.
- Historical compact incidents and storage version 3 remain readable. No raw Kuma history is duplicated.
- No direct network probes, telemetry, cloud services, passwords, or private Uptime Kuma runtime access.
- Existing Home Assistant entity IDs and integrations are not intentionally changed.

## Deployment in HACS

1. Extract this ZIP locally. Place its root contents (including `custom_components`, `hacs.json`, and `README.md`) at the root of your HACS GitHub repository.
2. For a fresh repository, finalize its manifest's publisher-only metadata using `python tools/finalize_repo.py --repo-url https://github.com/PROJECT_OWNER/ha-network-diagnostics` with your actual GitHub repository URL. An existing repository should retain its valid `codeowners` and documentation/issue links. Then commit the files and publish the tag/release `v0.4.0` using the regular HACS GitHub repository release model. The source ZIP is not a HACS release-only asset format.
3. In HACS, update Network Diagnostics to v0.4.0 and restart Home Assistant if prompted.
4. In Network Diagnostics, confirm previous monitor assignments remain; inspect the new metrics and **Recommended next checks**.

### Optional Kuma evidence to add

Add low-impact ICMP reachability monitors for relevant local hubs/controllers. In Network Diagnostics, assign each **Fixed Downstream Client** with the correct parent and provide one truly independent LAN Control where available. Do not use TCP connect probes against sensitive application/MQTT listeners merely to monitor reachability.

### Live acceptance

- Before any test, verify v0.4.0 loads with existing v0.3.2 topology and previous incidents intact.
- Confirm healthy monitors remain Healthy and that a missing/stale Kuma source remains a monitoring problem, not a network outage.
- Use a safe controlled Kuma test monitor to produce two short reported DOWN/UP cycles within 15 minutes. After the configured failure confirmation, expect an intermittent diagnosis despite UP status. Do not intentionally disrupt production hubs.
- Verify a single short outage alone does not yield a flapping incident; a sustained outage is still diagnosed through the normal topology path.
- Compare actual network evidence with application logs during a real command delay. Successful Kuma reachability must not be interpreted as proof that the local/cloud command path is healthy.

**No Home Assistant changes were made by building this package.**
