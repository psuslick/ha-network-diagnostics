# Privacy and publishing

The distributable repository is intentionally deployment-neutral.

Network-specific data belongs in the installing Home Assistant instance, where the config flow stores monitor roles, parent relationships, and service-group names. Uptime Kuma owns monitored targets. Network Diagnostics source code does not need those values.

Downloaded Network Diagnostics diagnostics are additionally privacy-reduced: monitored targets are not exported, and local monitor names, service names, and internal stable monitor identifiers are pseudonymized.

## Repository ownership

A GitHub repository necessarily has an owner. The installable ZIP therefore omits publication-only GitHub documentation, issue-tracker, and codeowner identity rather than embedding either a personal account name or unresolved placeholders. `tools/finalize_repo.py` can add those fields later after the publisher chooses the desired neutral repository identity.

If the requirement is that the project not be publicly associated with a personal GitHub account, publish it from an organization or project-specific account rather than a personal account.

## Existing public history

Replacing files in an existing Git repository does **not** remove sensitive data from earlier commits. If an earlier prototype containing deployment-specific information was pushed publicly, meeting a strict "never present in repository history" requirement requires either:

- publishing v0.3.1 from a new clean repository, or
- rewriting the old repository history and force-pushing the rewritten history after independently verifying it.

Creating a new clean repository is the simpler and lower-risk option.

## Automated guard

`python tools/check_privacy.py` rejects common accidental disclosures in repository text, including MAC-like addresses, non-documentation IP literals, and non-example email addresses. It also rejects direct network-client imports inside the integration because raw probing belongs to Uptime Kuma.

This automated check is a guardrail, not a proof that arbitrary free-form text contains no personal information. Human review remains required before publication.
