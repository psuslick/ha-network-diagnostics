# Repository finalization and HACS installation

The package intentionally ships with repository placeholders because the future GitHub owner/repository URL is not known at build time.

## 1. Create a GitHub repository

Recommended repository name:

`ha-network-diagnostics`

Recommended settings:

- public;
- Issues enabled;
- description: `Topology-aware network diagnosis for Home Assistant using Uptime Kuma`;
- topics: `home-assistant`, `hacs`, `uptime-kuma`, `network-monitoring`, `root-cause-analysis`.

## 2. Extract the package into the repository root

The root should contain at least:

```text
.github/
custom_components/network_diagnostics/
tests/
tools/
README.md
ORBI_NEXTDNS_SETUP.md
DECISIONS_AND_HANDOFF.md
RELEASE_NOTES_v0.2.0.md
REPOSITORY_SETUP.md
CHANGELOG.md
LICENSE
hacs.json
pyproject.toml
```

There should be exactly one integration directory under `custom_components/`.

## 3. Fill repository-specific manifest metadata

From the repository root:

```bash
python tools/finalize_repo.py \
  --repo-url https://github.com/YOUR_ACCOUNT/ha-network-diagnostics
```

For an organization/team codeowner:

```bash
python tools/finalize_repo.py \
  --repo-url https://github.com/ORG/ha-network-diagnostics \
  --codeowner @ORG/TEAM
```

This updates only these manifest values:

- `documentation`
- `issue_tracker`
- `codeowners`

It also regenerates `SOURCE_MANIFEST.sha256` so the source-integrity manifest remains valid after `manifest.json` changes.

## 4. Validate locally

```bash
python tools/check_repo.py
pytest
python -m compileall -q custom_components tests tools
```

Before the repository URL has been filled, use:

```bash
python tools/check_repo.py --allow-placeholders
```

To regenerate the source-integrity manifest manually after any source edit:

```bash
python tools/generate_source_manifest.py
```

If Node.js is available, also run:

```bash
node --check custom_components/network_diagnostics/frontend/network-diagnostics-panel.js
```

## 5. Commit and push

The included GitHub workflow runs:

- repository checks;
- unit tests;
- Python compilation;
- JavaScript syntax validation;
- HACS validation;
- Home Assistant hassfest validation.

Do not create the first release until those workflows pass on the actual GitHub repository.

## 6. Install through HACS

1. HACS → Custom repositories.
2. Add the GitHub repository.
3. Category: **Integration**.
4. Install **Network Diagnostics**.
5. Restart Home Assistant if requested.
6. Settings → Devices & services → Add integration → **Network Diagnostics**.

The integration should then register its own admin-only **Network Diagnostics** sidebar panel.

## 7. Configure Kuma, not HA entity mappings

For generic installations, name the Kuma monitors with the `[ND:...]` role contract documented in `README.md`.

For the original Orbi + NextDNS deployment, follow `ORBI_NEXTDNS_SETUP.md`; the existing names are recognized automatically.

No dashboard YAML import or entity-ID mapping should be necessary.
