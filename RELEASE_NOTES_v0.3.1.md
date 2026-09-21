# Network Diagnostics v0.3.1

v0.3.1 is a corrective patch for defects found during the first live v0.3.0 acceptance test.

## What the live test proved

v0.3.0 loaded successfully, created its native entities, and discovered the available Uptime Kuma monitors. The first live failure was instead in the Home Assistant integration/upgrade UX layer:

- `integration_type: helper` kept the loaded entry off the normal Integrations page;
- the intentionally cleared migration mapping was rendered as `Monitoring incomplete`, making setup look like a network/monitoring outage; and
- the installed manifest still contained publication placeholders.

## Fixes

- Classify Network Diagnostics as an HA `service`, making its config entry visible under Settings → Devices & services → Integrations.
- Keep the conservative one-time v0.3 migration, but surface it as **Setup required** rather than a monitoring failure.
- Report Coverage as **Not configured** until roles/topology are confirmed.
- Keep the Monitoring Problem binary sensor off while only setup is pending.
- Make the panel/Repair issue explicitly say that Kuma discovery succeeded and direct the user to **Network Diagnostics → Reconfigure**.
- Ship no unresolved repository-owner placeholders in the installable manifest. Publication-only owner/docs/issue metadata can be added later with `tools/finalize_repo.py`.

## Preserved architecture

The patch does not weaken the v0.3 architecture: Kuma remains the sole raw probe/history engine; Network Diagnostics performs no duplicate probes; topology is explicit and generic; Kuma Tags are optional hints; canonical names come from Kuma; adaptive samples are RAM-only; only compact derived incidents persist; and downloaded diagnostics remain privacy-reduced.
