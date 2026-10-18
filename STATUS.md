# Status

Version: **0.4.0 candidate**

Build status: **PACKAGE-VALIDATED / NOT YET LIVE VERIFIED** after automated regression, source/privacy checks, and archive validation. Live verification requires installing and observing it in Home Assistant.

Live status:
- v0.3.0: **APPLIED / LIVE VALIDATION FAILED** for Integrations-page visibility, setup-state UX, and unresolved install-manifest publication placeholders.
- v0.3.1: **APPLIED / LIVE VALIDATION FAILED** because DNS query hostnames were incorrectly treated as resolver endpoint identity, creating a false duplicate-evidence blocker during Reconfigure.
- v0.3.2: **PACKAGE-VALIDATED / NOT YET LIVE VERIFIED**. It corrects DNS endpoint-independence semantics and adds portable JSON configuration upload.
- v0.4.0: **CANDIDATE / NOT LIVE VERIFIED**. Adds intermittent reachability, fixed-client latency, stronger evidence handling, and conservative causal attribution.

No live Home Assistant configuration was modified by the build process.
