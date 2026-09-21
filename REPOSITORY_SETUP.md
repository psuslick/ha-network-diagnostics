# Repository setup

The installable ZIP intentionally omits publication-only repository metadata so the distributable source is not tied to a publisher identity and never contains unresolved placeholder values.

## Recommended privacy-first publication

If an earlier prototype repository ever contained deployment-specific information and strict history privacy matters, create a **new clean repository** for v0.3.1 rather than layering this release on top of that history.

Extract the ZIP into the new repository root. Then finalize only the repository metadata:

```bash
python tools/finalize_repo.py --repo-url https://github.com/PROJECT_OWNER/ha-network-diagnostics
```

Optionally provide a team/user codeowner explicitly:

```bash
python tools/finalize_repo.py \
  --repo-url https://github.com/PROJECT_OWNER/ha-network-diagnostics \
  --codeowner @PROJECT_OWNER
```

If public association with a personal GitHub identity is itself undesirable, use a project-specific account or organization.

Before pushing:

```bash
python tools/check_privacy.py
python tools/check_repo.py
pytest
python -m compileall -q custom_components tests tools
node --check custom_components/network_diagnostics/frontend/network-diagnostics-panel.js
```

`finalize_repo.py` regenerates `SOURCE_MANIFEST.sha256` after changing the manifest.
