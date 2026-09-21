#!/usr/bin/env python3
"""Generate SOURCE_MANIFEST.sha256 for distributable repository files."""
from __future__ import annotations

import hashlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "SOURCE_MANIFEST.sha256"
SKIP_NAMES = {"SOURCE_MANIFEST.sha256"}
SKIP_DIRS = {".git", ".pytest_cache", "__pycache__"}
SKIP_SUFFIXES = {".pyc", ".pyo"}


def iter_files():
    for path in sorted(ROOT.rglob("*")):
        if not path.is_file():
            continue
        rel = path.relative_to(ROOT)
        if any(part in SKIP_DIRS for part in rel.parts):
            continue
        if path.name in SKIP_NAMES or path.suffix in SKIP_SUFFIXES:
            continue
        yield path


def build_manifest_lines() -> list[str]:
    lines: list[str] = []
    for path in iter_files():
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        lines.append(f"{digest}  {path.relative_to(ROOT).as_posix()}")
    return lines


def main() -> int:
    OUTPUT.write_text("\n".join(build_manifest_lines()) + "\n", encoding="utf-8")
    print(f"Wrote {OUTPUT.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
