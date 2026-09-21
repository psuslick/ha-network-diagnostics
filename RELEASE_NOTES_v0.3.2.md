# Network Diagnostics v0.3.2

v0.3.2 is a live-validation fix release for the generic v0.3 architecture.

## DNS independence fix

v0.3.1 incorrectly treated Home Assistant's Uptime Kuma **monitored hostname** for a DNS monitor as though it identified the resolver endpoint. That value is the DNS query name. Two independent DNS resolvers can deliberately query the same hostname, so the old logic could create a false duplicate-evidence blocker.

v0.3.2 changes the rule:

- DNS query hostname is never used as resolver endpoint identity.
- If the supported public HA surface does not expose resolver identity, endpoint identity is `unknown`.
- Unknown identity does not block configuration as a duplicate.
- Unknown identity also does not grant extra independence-based coverage or confidence.

## Portable configuration upload

Initial setup and Reconfigure now offer **Upload configuration file** in addition to the guided manual flow.

The v1 JSON format stores only portable semantic configuration:

- canonical Uptime Kuma monitor `name`;
- diagnostic `role`;
- optional parent monitor name;
- optional service-group name.

At import time Network Diagnostics resolves canonical Kuma names to the current installation's stable monitor identities, validates the topology/evidence model against the live discovered inventory, and still requires the normal review/confirmation step before saving.

The import deliberately does not accept target addresses, credentials, Home Assistant entity IDs, or config-entry IDs. Missing/ambiguous monitor names fail closed. A synthetic example is included under `examples/`.

## Preserved architecture

This release does not restore vendor/provider-specific profiles, does not call Kuma directly, does not access Uptime Kuma private runtime data, does not duplicate raw probes/history, and does not alter Home Assistant Recorder.
