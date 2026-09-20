#!/usr/bin/env python3
"""Fill repository-specific manifest metadata after the GitHub repo exists."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from urllib.parse import urlparse

sys.dont_write_bytecode = True
from generate_source_manifest import write_manifest

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "custom_components" / "network_diagnostics" / "manifest.json"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-url", required=True, help="https://github.com/OWNER/REPO")
    parser.add_argument("--codeowner", help="GitHub user/team, e.g. @owner or @org/team")
    args = parser.parse_args()

    url = args.repo_url.rstrip("/")
    parsed = urlparse(url)
    parts = [p for p in parsed.path.split("/") if p]
    if parsed.scheme != "https" or parsed.netloc.lower() != "github.com" or len(parts) != 2:
        raise SystemExit("--repo-url must be exactly https://github.com/OWNER/REPO")
    owner, _repo = parts
    codeowner = args.codeowner or f"@{owner}"
    if not codeowner.startswith("@"):
        raise SystemExit("--codeowner must start with @")

    data = json.loads(MANIFEST.read_text())
    data["documentation"] = url
    data["issue_tracker"] = f"{url}/issues"
    data["codeowners"] = [codeowner]
    MANIFEST.write_text(json.dumps(data, indent=2) + "\n")
    write_manifest()
    print(f"Updated {MANIFEST.relative_to(ROOT)}")
    print(f"documentation: {url}")
    print(f"issue_tracker: {url}/issues")
    print(f"codeowners: {codeowner}")
    print("Regenerated SOURCE_MANIFEST.sha256")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
