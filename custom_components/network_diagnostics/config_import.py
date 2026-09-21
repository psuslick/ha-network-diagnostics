"""Portable JSON configuration import for Network Diagnostics."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable

from .const import (
    ALL_ASSIGNABLE_ROLES,
    CONF_PARENT,
    CONF_ROLE,
    CONF_SERVICE,
    ROLE_DISPLAY_NAMES,
    ROLE_IGNORE,
)

CONFIG_FILE_FORMAT = "network_diagnostics"
CONFIG_FILE_VERSION = 1
MAX_CONFIG_FILE_BYTES = 256 * 1024


class ConfigImportError(ValueError):
    """Raised when an uploaded Network Diagnostics configuration is invalid."""


@dataclass(frozen=True, slots=True)
class ImportInventoryItem:
    """Minimal inventory shape needed by the pure importer."""

    monitor_key: str
    name: str


_ALLOWED_TOP_LEVEL = {"format", "version", "monitors"}
_ALLOWED_MONITOR_FIELDS = {"name", "role", "parent", "service"}
_ROLE_BY_DISPLAY = {value.casefold(): key for key, value in ROLE_DISPLAY_NAMES.items()}
_ROLE_BY_KEY = {key.casefold(): key for key in ROLE_DISPLAY_NAMES}


def _normalize_role(value: Any) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ConfigImportError("Every monitor entry must have a non-empty role")
    clean = value.strip().casefold()
    role = _ROLE_BY_KEY.get(clean) or _ROLE_BY_DISPLAY.get(clean)
    if role is None or role not in ALL_ASSIGNABLE_ROLES or role == ROLE_IGNORE:
        allowed = ", ".join(
            ROLE_DISPLAY_NAMES[item]
            for item in ALL_ASSIGNABLE_ROLES
            if item != ROLE_IGNORE
        )
        raise ConfigImportError(
            f"Unknown diagnostic role {value!r}. Supported roles are: {allowed}"
        )
    return role


def _resolve_name(name: Any, by_name: dict[str, list[ImportInventoryItem]]) -> ImportInventoryItem:
    if not isinstance(name, str) or not name.strip():
        raise ConfigImportError("Every monitor entry must have a non-empty name")
    clean = name.strip()
    matches = by_name.get(clean)
    if not matches:
        raise ConfigImportError(
            f"Kuma monitor {clean!r} was not found. Configuration files match canonical Kuma monitor names exactly."
        )
    if len(matches) != 1:
        raise ConfigImportError(
            f"Kuma monitor name {clean!r} is ambiguous because more than one discovered monitor has that name"
        )
    return matches[0]


def import_monitor_config(
    payload: Any,
    inventory: Iterable[ImportInventoryItem],
) -> dict[str, dict[str, Any]]:
    """Validate a portable payload and resolve canonical names to local monitor IDs.

    The file intentionally stores human-readable Kuma monitor names instead of
    Home Assistant entity IDs or integration-specific stable IDs. Stable local
    identities are resolved at import time and become the keys persisted in the
    ConfigEntry.
    """
    if not isinstance(payload, dict):
        raise ConfigImportError("The configuration file must contain one JSON object")

    unknown_top = set(payload) - _ALLOWED_TOP_LEVEL
    if unknown_top:
        raise ConfigImportError(
            "Unknown top-level field(s): " + ", ".join(sorted(unknown_top))
        )
    if payload.get("format") != CONFIG_FILE_FORMAT:
        raise ConfigImportError(
            f"The configuration file format must be {CONFIG_FILE_FORMAT!r}"
        )
    if payload.get("version") != CONFIG_FILE_VERSION:
        raise ConfigImportError(
            f"Unsupported configuration file version {payload.get('version')!r}; expected {CONFIG_FILE_VERSION}"
        )

    raw_monitors = payload.get("monitors")
    if not isinstance(raw_monitors, list) or not raw_monitors:
        raise ConfigImportError("The configuration file must contain a non-empty monitors list")
    if len(raw_monitors) > 500:
        raise ConfigImportError("The configuration file contains too many monitor entries")

    inventory_list = list(inventory)
    by_name: dict[str, list[ImportInventoryItem]] = {}
    for item in inventory_list:
        by_name.setdefault(item.name, []).append(item)

    selected_by_name: dict[str, tuple[ImportInventoryItem, dict[str, Any]]] = {}
    for index, raw in enumerate(raw_monitors, start=1):
        if not isinstance(raw, dict):
            raise ConfigImportError(f"Monitor entry {index} must be a JSON object")
        unknown = set(raw) - _ALLOWED_MONITOR_FIELDS
        if unknown:
            raise ConfigImportError(
                f"Monitor entry {index} contains unknown field(s): "
                + ", ".join(sorted(unknown))
            )
        item = _resolve_name(raw.get("name"), by_name)
        if item.name in selected_by_name:
            raise ConfigImportError(f"Kuma monitor {item.name!r} is listed more than once")
        role = _normalize_role(raw.get("role"))
        service = raw.get("service")
        if service is not None:
            if not isinstance(service, str) or not service.strip():
                raise ConfigImportError(
                    f"Kuma monitor {item.name!r} has an invalid service name"
                )
            service = service.strip()
        parent = raw.get("parent")
        if parent is not None and (not isinstance(parent, str) or not parent.strip()):
            raise ConfigImportError(
                f"Kuma monitor {item.name!r} has an invalid parent name"
            )
        selected_by_name[item.name] = (
            item,
            {
                CONF_ROLE: role,
                "name": item.name,
                CONF_PARENT: parent.strip() if isinstance(parent, str) else None,
                CONF_SERVICE: service,
            },
        )

    selected_names = set(selected_by_name)
    working: dict[str, dict[str, Any]] = {}
    for name, (item, config) in selected_by_name.items():
        parent_name = config[CONF_PARENT]
        if parent_name:
            if parent_name not in selected_names:
                # Resolve against inventory as well so the error distinguishes a
                # typo from a parent that was simply omitted from the file.
                _resolve_name(parent_name, by_name)
                raise ConfigImportError(
                    f"Parent monitor {parent_name!r} for {name!r} exists in Kuma but is not included in the imported configuration"
                )
            config[CONF_PARENT] = selected_by_name[parent_name][0].monitor_key
        working[item.monitor_key] = config

    return working
