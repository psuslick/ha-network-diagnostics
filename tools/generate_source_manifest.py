#!/usr/bin/env python3
"""Generate a deterministic SHA-256 manifest for repository source files."""
from __future__ import annotations

import hashlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "SOURCE_MANIFEST.sha256"


def _included(path: Path) -> bool:
    """Return whether a path belongs in the source integrity manifest."""
    relative = path.relative_to(ROOT)
    if relative == Path("SOURCE_MANIFEST.sha256"):
        return False
    if any(part in {".git", ".pytest_cache", "__pycache__"} for part in relative.parts):
        return False
    if path.name == ".DS_Store" or path.suffix in {".pyc", ".pyo"}:
        return False
    return path.is_file()


def build_manifest_lines() -> list[str]:
    """Return deterministic checksum lines for the current source tree."""
    lines: list[str] = []
    for path in sorted((path for path in ROOT.rglob("*") if _included(path)), key=lambda p: p.as_posix()):
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        relative = path.relative_to(ROOT).as_posix()
        lines.append(f"{digest}  ./{relative}")
    return lines


def write_manifest() -> None:
    """Write SOURCE_MANIFEST.sha256."""
    OUTPUT.write_text("\n".join(build_manifest_lines()) + "\n", encoding="utf-8")


def main() -> int:
    write_manifest()
    print(f"Wrote {OUTPUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
