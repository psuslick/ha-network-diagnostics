#!/usr/bin/env python3
"""Fail when repository text appears to contain deployment-specific network data."""
from __future__ import annotations

import ipaddress
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
TEXT_SUFFIXES = {
    ".py", ".md", ".json", ".yml", ".yaml", ".toml", ".txt", ".js", ".css", ".html"
}
SKIP_PARTS = {".git", ".pytest_cache", "__pycache__"}

IPV4_RE = re.compile(r"(?<![\w.])(?:\d{1,3}\.){3}\d{1,3}(?![\w.])")
MAC_RE = re.compile(r"(?i)(?<![0-9a-f])(?:[0-9a-f]{2}[:-]){5}[0-9a-f]{2}(?![0-9a-f])")
EMAIL_RE = re.compile(r"(?i)\b[A-Z0-9._%+-]+@([A-Z0-9.-]+\.[A-Z]{2,})\b")
IPV6_CANDIDATE_RE = re.compile(r"(?<![0-9A-Fa-f:])(?:[0-9A-Fa-f]{0,4}:){2,7}[0-9A-Fa-f]{0,4}(?![0-9A-Fa-f:])")
NETWORK_CLIENT_IMPORT_RE = re.compile(
    r"(?m)^\s*(?:from\s+(?:aiohttp|httpx|requests|socket)\b|import\s+(?:aiohttp|httpx|requests|socket)\b)"
)

DOC_IPV4_NETS = tuple(
    ipaddress.ip_network(net)
    for net in ("192.0.2.0/24", "198.51.100.0/24", "203.0.113.0/24")
)
DOC_IPV6 = ipaddress.ip_network("2001:db8::/32")


def _allowed_ip(value: str) -> bool:
    try:
        address = ipaddress.ip_address(value)
    except ValueError:
        return True
    if address.is_loopback or address.is_unspecified:
        return True
    if address.version == 4:
        return any(address in network for network in DOC_IPV4_NETS)
    return address in DOC_IPV6


def _iter_text_files():
    for path in ROOT.rglob("*"):
        if not path.is_file() or any(part in SKIP_PARTS for part in path.relative_to(ROOT).parts):
            continue
        if path.suffix.lower() in TEXT_SUFFIXES or path.name in {"LICENSE", ".gitignore"}:
            yield path


def main() -> int:
    failures: list[str] = []
    for path in _iter_text_files():
        text = path.read_text(encoding="utf-8", errors="replace")
        rel = path.relative_to(ROOT)
        for match in MAC_RE.finditer(text):
            failures.append(f"{rel}: MAC-like address {match.group(0)!r}")
        for match in IPV4_RE.finditer(text):
            value = match.group(0)
            if not _allowed_ip(value):
                failures.append(f"{rel}: non-documentation IPv4 literal {value!r}")
        for match in IPV6_CANDIDATE_RE.finditer(text):
            value = match.group(0)
            if value and not _allowed_ip(value):
                try:
                    ipaddress.ip_address(value)
                except ValueError:
                    continue
                failures.append(f"{rel}: non-documentation IPv6 literal {value!r}")
        for match in EMAIL_RE.finditer(text):
            candidate = match.group(0).casefold()
            domain = match.group(1).casefold()
            if candidate.endswith(("@2x.png", "@3x.png")):
                continue
            if domain not in {"example.com", "example.org", "example.net"}:
                failures.append(f"{rel}: email address outside documentation domains")

    component = ROOT / "custom_components" / "network_diagnostics"
    for path in component.rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        if NETWORK_CLIENT_IMPORT_RE.search(text):
            failures.append(
                f"{path.relative_to(ROOT)}: direct network client import; raw probing belongs to Uptime Kuma"
            )

    if failures:
        for failure in failures:
            print(f"ERROR: {failure}")
        return 1
    print("Privacy checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
