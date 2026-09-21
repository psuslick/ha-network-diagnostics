"""UI configuration and reconfiguration for Network Diagnostics."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
    OptionsFlowWithReload,
)
from homeassistant.core import callback
from homeassistant.helpers import selector

from .const import (
    ALL_ASSIGNABLE_ROLES,
    CONF_BASELINE_MIN_DELTA_MS,
    CONF_BASELINE_MIN_SAMPLES,
    CONF_BASELINE_RATIO,
    CONF_BASELINE_WINDOW_MINUTES,
    CONF_CONFIGURED,
    CONF_DEGRADATION_SECONDS,
    CONF_FAILURE_CONFIRM_SECONDS,
    CONF_INCIDENT_RETENTION,
    CONF_MONITORS,
    CONF_PARENT,
    CONF_RECOVERY_CONFIRM_SECONDS,
    CONF_ROLE,
    CONF_SERVICE,
    CONF_STALE_SECONDS,
    CONFIG_VERSION,
    DEFAULT_BASELINE_MIN_DELTA_MS,
    DEFAULT_BASELINE_MIN_SAMPLES,
    DEFAULT_BASELINE_RATIO,
    DEFAULT_BASELINE_WINDOW_MINUTES,
    DEFAULT_DEGRADATION_SECONDS,
    DEFAULT_FAILURE_CONFIRM_SECONDS,
    DEFAULT_INCIDENT_RETENTION,
    DEFAULT_RECOVERY_CONFIRM_SECONDS,
    DEFAULT_STALE_SECONDS,
    DOMAIN,
    LOCAL_CHILD_ROLES,
    LOCAL_PARENT_ROLES,
    NAME,
    ROLE_DISPLAY_NAMES,
    ROLE_IGNORE,
    SERVICE_ROLES,
)
from .discovery import KumaMonitor, configured_bindings, discover_kuma_inventory
from .validation import coverage_capabilities, coverage_gaps, validate_bindings

ROLE_FIELDS = tuple(role for role in ALL_ASSIGNABLE_ROLES if role != ROLE_IGNORE)


def _monitor_options(monitors: list[KumaMonitor]) -> list[dict[str, str]]:
    return [
        {"value": item.monitor_key, "label": item.name}
        for item in sorted(
            monitors,
            key=lambda value: (not value.tag_hint.enrolled, value.name.casefold()),
        )
    ]


def _select_monitors(monitors: list[KumaMonitor], *, multiple: bool = True):
    return selector.SelectSelector(
        selector.SelectSelectorConfig(
            options=_monitor_options(monitors),
            multiple=multiple,
            custom_value=False,
            mode=selector.SelectSelectorMode.DROPDOWN,
        )
    )


def _normalize_multi(value: Any) -> list[str]:
    if value in (None, ""):
        return []
    if isinstance(value, list):
        return [str(item) for item in value if item]
    return [str(value)]


class NetworkDiagnosticsConfigFlow(ConfigFlow, domain=DOMAIN):
    """Create or reconfigure one Network Diagnostics config entry."""

    VERSION = CONFIG_VERSION

    def __init__(self) -> None:
        self._inventory: list[KumaMonitor] = []
        self._working: dict[str, dict[str, Any]] = {}
        self._parent_items: list[str] = []
        self._parent_index = 0
        self._service_items: list[str] = []
        self._service_index = 0
        self._reconfigure = False

    def _load_inventory(self) -> bool:
        self._inventory = discover_kuma_inventory(self.hass)
        return bool(self._inventory)

    def _existing_monitor_config(self) -> dict[str, dict[str, Any]]:
        if not self._reconfigure:
            return {}
        entry = self._get_reconfigure_entry()
        raw = entry.data.get(CONF_MONITORS, {})
        return {
            str(key): dict(value)
            for key, value in raw.items()
            if isinstance(value, dict)
        }

    def _role_defaults(self) -> dict[str, list[str]]:
        defaults = {role: [] for role in ROLE_FIELDS}
        existing = self._existing_monitor_config()
        for item in self._inventory:
            role = existing.get(item.monitor_key, {}).get(CONF_ROLE)
            if role in defaults:
                defaults[role].append(item.monitor_key)
                continue
            hint = item.tag_hint.role
            if hint in defaults:
                defaults[hint].append(item.monitor_key)
        return defaults

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")
        if not self.hass.config_entries.async_entries("uptime_kuma"):
            return self.async_abort(reason="uptime_kuma_required")
        if not self._load_inventory():
            return self.async_abort(reason="no_kuma_monitors")
        return await self.async_step_roles()

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        self._reconfigure = True
        if not self.hass.config_entries.async_entries("uptime_kuma"):
            return self.async_abort(reason="uptime_kuma_required")
        if not self._load_inventory():
            return self.async_abort(reason="no_kuma_monitors")
        return await self.async_step_roles()

    async def async_step_roles(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        defaults = (
            self._role_defaults()
            if not self._working
            else {
                role: [
                    key
                    for key, cfg in self._working.items()
                    if cfg.get(CONF_ROLE) == role
                ]
                for role in ROLE_FIELDS
            }
        )
        errors: dict[str, str] = {}
        if user_input is not None:
            selected: dict[str, str] = {}
            duplicate = False
            for role in ROLE_FIELDS:
                for monitor_key in _normalize_multi(user_input.get(role)):
                    if monitor_key in selected:
                        duplicate = True
                    selected[monitor_key] = role
            if duplicate:
                errors["base"] = "duplicate_monitor_assignment"
            elif not selected:
                errors["base"] = "no_monitors_selected"
            else:
                existing = self._existing_monitor_config()
                names = {item.monitor_key: item.name for item in self._inventory}
                self._working = {
                    key: {
                        CONF_ROLE: role,
                        "name": names.get(
                            key, existing.get(key, {}).get("name", "Kuma monitor")
                        ),
                        CONF_PARENT: existing.get(key, {}).get(CONF_PARENT),
                        CONF_SERVICE: existing.get(key, {}).get(CONF_SERVICE),
                    }
                    for key, role in selected.items()
                }
                self._parent_items = [
                    key
                    for key, cfg in self._working.items()
                    if cfg[CONF_ROLE] in LOCAL_CHILD_ROLES
                ]
                self._parent_index = 0
                self._service_items = [
                    key
                    for key, cfg in self._working.items()
                    if cfg[CONF_ROLE] in SERVICE_ROLES
                ]
                self._service_index = 0
                return await self.async_step_parent()

        schema: dict[Any, Any] = {}
        for role in ROLE_FIELDS:
            schema[vol.Optional(role, default=defaults.get(role, []))] = _select_monitors(
                self._inventory, multiple=True
            )
        return self.async_show_form(
            step_id="roles", data_schema=vol.Schema(schema), errors=errors
        )

    def _monitor(self, monitor_key: str) -> KumaMonitor | None:
        return next(
            (item for item in self._inventory if item.monitor_key == monitor_key), None
        )

    async def async_step_parent(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        if self._parent_index >= len(self._parent_items):
            return await self.async_step_service()

        child_key = self._parent_items[self._parent_index]
        child = self._monitor(child_key)
        if child is None:
            self._parent_index += 1
            return await self.async_step_parent()

        if user_input is not None:
            self._working[child_key][CONF_PARENT] = user_input.get(CONF_PARENT) or None
            self._parent_index += 1
            return await self.async_step_parent()

        parents = [
            item
            for item in self._inventory
            if item.monitor_key in self._working
            and self._working[item.monitor_key][CONF_ROLE] in LOCAL_PARENT_ROLES
            and item.monitor_key != child_key
        ]
        options = [{"value": "", "label": "No parent / unknown"}, *_monitor_options(parents)]
        existing = self._working[child_key].get(CONF_PARENT) or ""
        if not existing and child.tag_hint.parent_name:
            matches = [
                item.monitor_key
                for item in parents
                if item.name.casefold() == child.tag_hint.parent_name.casefold()
            ]
            if len(matches) == 1:
                existing = matches[0]
        return self.async_show_form(
            step_id="parent",
            description_placeholders={
                "monitor": child.name,
                "role": ROLE_DISPLAY_NAMES[self._working[child_key][CONF_ROLE]],
                "position": str(self._parent_index + 1),
                "total": str(len(self._parent_items)),
            },
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_PARENT, default=existing): selector.SelectSelector(
                        selector.SelectSelectorConfig(
                            options=options,
                            multiple=False,
                            custom_value=False,
                            mode=selector.SelectSelectorMode.DROPDOWN,
                        )
                    )
                }
            ),
        )

    async def async_step_service(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        if self._service_index >= len(self._service_items):
            return await self.async_step_confirm()

        monitor_key = self._service_items[self._service_index]
        monitor = self._monitor(monitor_key)
        if monitor is None:
            self._service_index += 1
            return await self.async_step_service()

        errors: dict[str, str] = {}
        if user_input is not None:
            service = str(user_input.get(CONF_SERVICE, "")).strip()
            if not service:
                errors[CONF_SERVICE] = "service_required"
            else:
                self._working[monitor_key][CONF_SERVICE] = service
                self._service_index += 1
                return await self.async_step_service()

        default = (
            self._working[monitor_key].get(CONF_SERVICE)
            or monitor.tag_hint.service
            or ""
        )
        return self.async_show_form(
            step_id="service",
            description_placeholders={
                "monitor": monitor.name,
                "role": ROLE_DISPLAY_NAMES[self._working[monitor_key][CONF_ROLE]],
                "position": str(self._service_index + 1),
                "total": str(len(self._service_items)),
            },
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_SERVICE, default=default): selector.TextSelector(
                        selector.TextSelectorConfig(type=selector.TextSelectorType.TEXT)
                    )
                }
            ),
            errors=errors,
        )

    async def async_step_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        proposed_data = {CONF_CONFIGURED: True, CONF_MONITORS: self._working}
        discovery = configured_bindings(self.hass, proposed_data)
        warnings, blockers = validate_bindings(discovery.bindings)
        capabilities = coverage_capabilities(discovery.bindings)
        advisories = coverage_gaps(capabilities)

        if user_input is not None and not blockers:
            if self._reconfigure:
                return self.async_update_reload_and_abort(
                    self._get_reconfigure_entry(),
                    data_updates=proposed_data,
                    reload_even_if_entry_is_unchanged=False,
                )
            return self.async_create_entry(title=NAME, data=proposed_data)

        return self.async_show_form(
            step_id="confirm",
            description_placeholders={
                "configured_count": str(len(discovery.bindings)),
                "blockers": "\n".join(f"• {item}" for item in blockers) or "None",
                "warnings": "\n".join(f"• {item}" for item in warnings) or "None",
                "coverage": "\n".join(f"• {item}" for item in advisories)
                or "Complete for the modeled fault classes",
            },
            data_schema=vol.Schema({}),
            errors={"base": "configuration_blocked"} if blockers else {},
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        return NetworkDiagnosticsOptionsFlow()


class NetworkDiagnosticsOptionsFlow(OptionsFlowWithReload):
    """Edit diagnostic behavior without rewriting topology."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        current = dict(self.config_entry.options)
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        def value(key: str, default: int | float) -> int | float:
            return current.get(key, default)

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_STALE_SECONDS,
                        default=int(value(CONF_STALE_SECONDS, DEFAULT_STALE_SECONDS)),
                    ): selector.NumberSelector(
                        selector.NumberSelectorConfig(
                            min=60,
                            max=900,
                            step=10,
                            mode=selector.NumberSelectorMode.BOX,
                            unit_of_measurement="s",
                        )
                    ),
                    vol.Required(
                        CONF_FAILURE_CONFIRM_SECONDS,
                        default=int(
                            value(
                                CONF_FAILURE_CONFIRM_SECONDS,
                                DEFAULT_FAILURE_CONFIRM_SECONDS,
                            )
                        ),
                    ): selector.NumberSelector(
                        selector.NumberSelectorConfig(
                            min=0,
                            max=300,
                            step=1,
                            mode=selector.NumberSelectorMode.BOX,
                            unit_of_measurement="s",
                        )
                    ),
                    vol.Required(
                        CONF_RECOVERY_CONFIRM_SECONDS,
                        default=int(
                            value(
                                CONF_RECOVERY_CONFIRM_SECONDS,
                                DEFAULT_RECOVERY_CONFIRM_SECONDS,
                            )
                        ),
                    ): selector.NumberSelector(
                        selector.NumberSelectorConfig(
                            min=0,
                            max=600,
                            step=1,
                            mode=selector.NumberSelectorMode.BOX,
                            unit_of_measurement="s",
                        )
                    ),
                    vol.Required(
                        CONF_BASELINE_WINDOW_MINUTES,
                        default=int(
                            value(
                                CONF_BASELINE_WINDOW_MINUTES,
                                DEFAULT_BASELINE_WINDOW_MINUTES,
                            )
                        ),
                    ): selector.NumberSelector(
                        selector.NumberSelectorConfig(
                            min=10,
                            max=360,
                            step=5,
                            mode=selector.NumberSelectorMode.BOX,
                            unit_of_measurement="min",
                        )
                    ),
                    vol.Required(
                        CONF_BASELINE_MIN_SAMPLES,
                        default=int(
                            value(
                                CONF_BASELINE_MIN_SAMPLES,
                                DEFAULT_BASELINE_MIN_SAMPLES,
                            )
                        ),
                    ): selector.NumberSelector(
                        selector.NumberSelectorConfig(
                            min=4,
                            max=120,
                            step=1,
                            mode=selector.NumberSelectorMode.BOX,
                        )
                    ),
                    vol.Required(
                        CONF_BASELINE_RATIO,
                        default=float(value(CONF_BASELINE_RATIO, DEFAULT_BASELINE_RATIO)),
                    ): selector.NumberSelector(
                        selector.NumberSelectorConfig(
                            min=1.2,
                            max=10,
                            step=0.1,
                            mode=selector.NumberSelectorMode.BOX,
                        )
                    ),
                    vol.Required(
                        CONF_BASELINE_MIN_DELTA_MS,
                        default=float(
                            value(
                                CONF_BASELINE_MIN_DELTA_MS,
                                DEFAULT_BASELINE_MIN_DELTA_MS,
                            )
                        ),
                    ): selector.NumberSelector(
                        selector.NumberSelectorConfig(
                            min=1,
                            max=500,
                            step=1,
                            mode=selector.NumberSelectorMode.BOX,
                            unit_of_measurement="ms",
                        )
                    ),
                    vol.Required(
                        CONF_DEGRADATION_SECONDS,
                        default=int(
                            value(CONF_DEGRADATION_SECONDS, DEFAULT_DEGRADATION_SECONDS)
                        ),
                    ): selector.NumberSelector(
                        selector.NumberSelectorConfig(
                            min=0,
                            max=1800,
                            step=5,
                            mode=selector.NumberSelectorMode.BOX,
                            unit_of_measurement="s",
                        )
                    ),
                    vol.Required(
                        CONF_INCIDENT_RETENTION,
                        default=int(
                            value(CONF_INCIDENT_RETENTION, DEFAULT_INCIDENT_RETENTION)
                        ),
                    ): selector.NumberSelector(
                        selector.NumberSelectorConfig(
                            min=10,
                            max=1000,
                            step=10,
                            mode=selector.NumberSelectorMode.BOX,
                        )
                    ),
                }
            ),
        )
