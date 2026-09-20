"""Pure helpers for safe monitor target handling."""

from __future__ import annotations

import hashlib
from urllib.parse import urlsplit


def sanitize_target(value: str | None) -> str | None:
    """Return a display-safe target without URL credentials/query/fragment.

    Kuma monitor URLs can contain credentials or secret query strings. Network
    Diagnostics never needs those secrets for diagnosis, so the UI/diagnostics
    surface only the origin (scheme, host and optional port) for URL targets.
    Non-URL targets such as IP addresses and DNS hostnames are returned as-is.
    """
    if value is None:
        return None
    clean = str(value).strip()
    if not clean:
        return None
    if "://" not in clean:
        return clean
    try:
        parsed = urlsplit(clean)
    except ValueError:
        return "<url>"
    if not parsed.scheme or not parsed.hostname:
        return "<url>"
    host = parsed.hostname
    if ":" in host and not host.startswith("["):
        host = f"[{host}]"
    port = f":{parsed.port}" if parsed.port is not None else ""
    return f"{parsed.scheme.lower()}://{host}{port}"


def target_fingerprint(value: str | None) -> str | None:
    """Return a non-reversible short fingerprint for duplicate-source checks."""
    if value is None:
        return None
    clean = str(value).strip()
    if not clean:
        return None
    return hashlib.sha256(clean.encode()).hexdigest()[:16]
