"""Config and options flow for Network Diagnostics."""

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
    CONF_FAILURE_CONFIRM_SECONDS,
    CONF_INCIDENT_RETENTION,
    CONF_MESH_DEGRADATION_SECONDS,
    CONF_MESH_LATENCY_MS,
    CONF_RECOVERY_CONFIRM_SECONDS,
    CONF_STALE_SECONDS,
    DEFAULT_FAILURE_CONFIRM_SECONDS,
    DEFAULT_INCIDENT_RETENTION,
    DEFAULT_MESH_DEGRADATION_SECONDS,
    DEFAULT_MESH_LATENCY_MS,
    DEFAULT_RECOVERY_CONFIRM_SECONDS,
    DEFAULT_STALE_SECONDS,
    DOMAIN,
    NAME,
)


class NetworkDiagnosticsConfigFlow(ConfigFlow, domain=DOMAIN):
    """Create the single Network Diagnostics config entry."""

    VERSION = 2

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")
        if user_input is not None:
            return self.async_create_entry(title=NAME, data={})
        return self.async_show_form(step_id="user", data_schema=vol.Schema({}))

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: ConfigEntry,
    ) -> OptionsFlow:
        return NetworkDiagnosticsOptionsFlow()


class NetworkDiagnosticsOptionsFlow(OptionsFlowWithReload):
    """Edit only diagnostic behavior; monitor mapping is automatic."""

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        current = dict(self.config_entry.options)
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)
        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_STALE_SECONDS,
                        default=int(current.get(CONF_STALE_SECONDS, DEFAULT_STALE_SECONDS)),
                    ): selector.NumberSelector(
                        selector.NumberSelectorConfig(
                            min=60, max=900, step=10, mode=selector.NumberSelectorMode.BOX
                        )
                    ),
                    vol.Required(
                        CONF_FAILURE_CONFIRM_SECONDS,
                        default=int(
                            current.get(
                                CONF_FAILURE_CONFIRM_SECONDS,
                                DEFAULT_FAILURE_CONFIRM_SECONDS,
                            )
                        ),
                    ): selector.NumberSelector(
                        selector.NumberSelectorConfig(
                            min=0, max=300, step=1, mode=selector.NumberSelectorMode.BOX
                        )
                    ),
                    vol.Required(
                        CONF_RECOVERY_CONFIRM_SECONDS,
                        default=int(
                            current.get(
                                CONF_RECOVERY_CONFIRM_SECONDS,
                                DEFAULT_RECOVERY_CONFIRM_SECONDS,
                            )
                        ),
                    ): selector.NumberSelector(
                        selector.NumberSelectorConfig(
                            min=0, max=600, step=1, mode=selector.NumberSelectorMode.BOX
                        )
                    ),
                    vol.Required(
                        CONF_MESH_LATENCY_MS,
                        default=float(
                            current.get(CONF_MESH_LATENCY_MS, DEFAULT_MESH_LATENCY_MS)
                        ),
                    ): selector.NumberSelector(
                        selector.NumberSelectorConfig(
                            min=5,
                            max=1000,
                            step=1,
                            mode=selector.NumberSelectorMode.BOX,
                            unit_of_measurement="ms",
                        )
                    ),
                    vol.Required(
                        CONF_MESH_DEGRADATION_SECONDS,
                        default=int(
                            current.get(
                                CONF_MESH_DEGRADATION_SECONDS,
                                DEFAULT_MESH_DEGRADATION_SECONDS,
                            )
                        ),
                    ): selector.NumberSelector(
                        selector.NumberSelectorConfig(
                            min=15, max=1800, step=5, mode=selector.NumberSelectorMode.BOX
                        )
                    ),
                    vol.Required(
                        CONF_INCIDENT_RETENTION,
                        default=int(
                            current.get(CONF_INCIDENT_RETENTION, DEFAULT_INCIDENT_RETENTION)
                        ),
                    ): selector.NumberSelector(
                        selector.NumberSelectorConfig(
                            min=10, max=1000, step=10, mode=selector.NumberSelectorMode.BOX
                        )
                    ),
                }
            ),
        )
