"""Pure helpers for privacy-safe monitor target semantics."""

from __future__ import annotations

import hashlib
import ipaddress
from urllib.parse import urlsplit


def select_raw_target(
    *,
    url: str | None = None,
    hostname: str | None = None,
    port: str | None = None,
) -> str | None:
    """Choose the target values exposed by Home Assistant's Kuma entities."""
    clean_url = str(url).strip() if url not in (None, "") else None
    clean_host = str(hostname).strip() if hostname not in (None, "") else None
    clean_port = str(port).strip() if port not in (None, "") else None
    if clean_url:
        return clean_url
    if clean_host:
        return f"{clean_host}:{clean_port}" if clean_port else clean_host
    if clean_port:
        return clean_port
    return None


def normalized_target_identity(value: str | None) -> str | None:
    """Normalize a target for in-memory equality checks without displaying it."""
    if value is None:
        return None
    clean = str(value).strip()
    if not clean:
        return None
    if "://" not in clean:
        return clean.casefold()
    try:
        parsed = urlsplit(clean)
    except ValueError:
        return None
    if not parsed.scheme or not parsed.hostname:
        return None
    host = parsed.hostname.casefold()
    port = f":{parsed.port}" if parsed.port is not None else ""
    return f"{parsed.scheme.lower()}://{host}{port}"


def target_fingerprint(value: str | None) -> str | None:
    """Return a non-display fingerprint for duplicate-source checks."""
    normalized = normalized_target_identity(value)
    if not normalized:
        return None
    return hashlib.sha256(normalized.encode()).hexdigest()[:20]


def target_ip_version(value: str | None) -> int | None:
    """Return 4/6 when a target is a literal IP address, otherwise None."""
    if not value:
        return None
    clean = str(value).strip()
    if "://" in clean:
        try:
            host = urlsplit(clean).hostname
        except ValueError:
            return None
        if not host:
            return None
        clean = host
    else:
        if clean.startswith("[") and "]" in clean:
            clean = clean[1 : clean.index("]")]
        elif clean.count(":") == 1:
            host, maybe_port = clean.rsplit(":", 1)
            if maybe_port.isdigit():
                clean = host
    try:
        return ipaddress.ip_address(clean).version
    except ValueError:
        return None
