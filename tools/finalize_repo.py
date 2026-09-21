#!/usr/bin/env python3
"""Add publisher-selected repository metadata to a privacy-neutral install tree."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "custom_components" / "network_diagnostics" / "manifest.json"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-url", required=True)
    parser.add_argument("--codeowner")
    args = parser.parse_args()

    parsed = urlparse(args.repo_url)
    if parsed.scheme != "https" or parsed.netloc != "github.com":
        raise SystemExit("--repo-url must be an https://github.com/<owner>/<repo> URL")
    parts = [part for part in parsed.path.split("/") if part]
    if len(parts) != 2:
        raise SystemExit("--repo-url must identify exactly one GitHub repository")
    owner, repo = parts
    codeowner = args.codeowner or f"@{owner}"
    if not codeowner.startswith("@"):
        raise SystemExit("--codeowner must start with @")

    data = json.loads(MANIFEST.read_text(encoding="utf-8"))
    base = f"https://github.com/{owner}/{repo}"
    data["documentation"] = base
    data["issue_tracker"] = f"{base}/issues"
    data["codeowners"] = [codeowner]
    MANIFEST.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")

    from generate_source_manifest import main as generate_manifest
    generate_manifest()
    print(f"Finalized repository metadata for {base}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
