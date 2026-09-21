"""Constants for Network Diagnostics."""

from __future__ import annotations

DOMAIN = "network_diagnostics"
NAME = "Network Diagnostics"
VERSION = "0.3.1"
CONFIG_VERSION = 3
STORAGE_VERSION = 3
STORAGE_KEY_PREFIX = "network_diagnostics.incidents"

PLATFORMS = ["sensor", "binary_sensor", "event", "button"]

PANEL_URL_PATH = "network-diagnostics-app"
PANEL_TITLE = "Network Diagnostics"
PANEL_ICON = "mdi:lan-check"
STATIC_URL = "/network_diagnostics_static"

CONF_CONFIGURED = "configured"
CONF_MONITORS = "monitors"
CONF_ROLE = "role"
CONF_PARENT = "parent"
CONF_SERVICE = "service"

CONF_STALE_SECONDS = "stale_seconds"
CONF_FAILURE_CONFIRM_SECONDS = "failure_confirm_seconds"
CONF_RECOVERY_CONFIRM_SECONDS = "recovery_confirm_seconds"
CONF_BASELINE_WINDOW_MINUTES = "baseline_window_minutes"
CONF_BASELINE_MIN_SAMPLES = "baseline_min_samples"
CONF_BASELINE_RATIO = "baseline_ratio"
CONF_BASELINE_MIN_DELTA_MS = "baseline_min_delta_ms"
CONF_DEGRADATION_SECONDS = "degradation_seconds"
CONF_INCIDENT_RETENTION = "incident_retention"

DEFAULT_STALE_SECONDS = 180
DEFAULT_FAILURE_CONFIRM_SECONDS = 15
DEFAULT_RECOVERY_CONFIRM_SECONDS = 60
DEFAULT_BASELINE_WINDOW_MINUTES = 60
DEFAULT_BASELINE_MIN_SAMPLES = 12
DEFAULT_BASELINE_RATIO = 2.5
DEFAULT_BASELINE_MIN_DELTA_MS = 10.0
DEFAULT_DEGRADATION_SECONDS = 90
DEFAULT_INCIDENT_RETENTION = 200

BEHAVIOR_DEFAULTS: dict[str, int | float] = {
    CONF_STALE_SECONDS: DEFAULT_STALE_SECONDS,
    CONF_FAILURE_CONFIRM_SECONDS: DEFAULT_FAILURE_CONFIRM_SECONDS,
    CONF_RECOVERY_CONFIRM_SECONDS: DEFAULT_RECOVERY_CONFIRM_SECONDS,
    CONF_BASELINE_WINDOW_MINUTES: DEFAULT_BASELINE_WINDOW_MINUTES,
    CONF_BASELINE_MIN_SAMPLES: DEFAULT_BASELINE_MIN_SAMPLES,
    CONF_BASELINE_RATIO: DEFAULT_BASELINE_RATIO,
    CONF_BASELINE_MIN_DELTA_MS: DEFAULT_BASELINE_MIN_DELTA_MS,
    CONF_DEGRADATION_SECONDS: DEFAULT_DEGRADATION_SECONDS,
    CONF_INCIDENT_RETENTION: DEFAULT_INCIDENT_RETENTION,
}
BEHAVIOR_OPTION_KEYS = tuple(BEHAVIOR_DEFAULTS)

# Generic semantic roles. The source code intentionally contains no vendor,
# service-provider, household, topology, address, or deployment-specific roles.
ROLE_IGNORE = "ignore"
ROLE_GATEWAY = "gateway"
ROLE_NETWORK_NODE = "network_node"
ROLE_MESH_NODE = "mesh_node"
ROLE_FIXED_CLIENT = "fixed_client"
ROLE_LAN_CONTROL = "lan_control"
ROLE_IPV4_CONTROL = "ipv4_control"
ROLE_IPV6_CONTROL = "ipv6_control"
ROLE_DNS_NEUTRAL = "dns_neutral"
ROLE_DNS_LOCAL = "dns_local"
ROLE_SERVICE_DNS = "service_dns"
ROLE_SERVICE_PATH = "service_path"
ROLE_HTTPS_CONTROL = "https_control"

ROLE_DISPLAY_NAMES = {
    ROLE_IGNORE: "Ignore",
    ROLE_GATEWAY: "Gateway",
    ROLE_NETWORK_NODE: "Network Node",
    ROLE_MESH_NODE: "Mesh / Wireless Node",
    ROLE_FIXED_CLIENT: "Fixed Downstream Client",
    ROLE_LAN_CONTROL: "LAN Control",
    ROLE_IPV4_CONTROL: "IPv4 Internet Control",
    ROLE_IPV6_CONTROL: "IPv6 Internet Control",
    ROLE_DNS_NEUTRAL: "Independent DNS Control",
    ROLE_DNS_LOCAL: "Local DNS Control",
    ROLE_SERVICE_DNS: "Service DNS Control",
    ROLE_SERVICE_PATH: "Service Path Control",
    ROLE_HTTPS_CONTROL: "HTTPS Control",
}

LOCAL_PARENT_ROLES = {ROLE_GATEWAY, ROLE_NETWORK_NODE, ROLE_MESH_NODE}
LOCAL_CHILD_ROLES = {ROLE_NETWORK_NODE, ROLE_MESH_NODE, ROLE_FIXED_CLIENT}
TOPOLOGY_NODE_ROLES = {ROLE_GATEWAY, ROLE_NETWORK_NODE, ROLE_MESH_NODE, ROLE_FIXED_CLIENT}
CONTROL_ROLES = {
    ROLE_LAN_CONTROL,
    ROLE_IPV4_CONTROL,
    ROLE_IPV6_CONTROL,
    ROLE_DNS_NEUTRAL,
    ROLE_DNS_LOCAL,
    ROLE_SERVICE_DNS,
    ROLE_SERVICE_PATH,
    ROLE_HTTPS_CONTROL,
}
SERVICE_ROLES = {ROLE_SERVICE_DNS, ROLE_SERVICE_PATH}
ALL_ASSIGNABLE_ROLES = tuple(ROLE_DISPLAY_NAMES)

GOOD_STATUS = "up"
BAD_STATUS = "down"
UNUSABLE_STATUSES = {"unknown", "unavailable", "none", "", "pending", "maintenance"}

# Uptime Kuma calls these Tags. Home Assistant has a separate, unrelated Label
# feature, so the integration keeps the terminology distinct.
KUMA_TAG_ENABLED = "Network Diagnostics"
KUMA_TAG_ROLE = "Network Diagnostics Role"
KUMA_TAG_PARENT = "Network Diagnostics Parent"
KUMA_TAG_SERVICE = "Network Diagnostics Service"
KUMA_TAG_ENABLED_VALUE = "Enabled"

ISSUE_CONFIGURATION_REQUIRED = "configuration_required"
ISSUE_CONFIGURED_MONITOR_MISSING = "configured_monitor_missing"
ISSUE_INVALID_CONFIGURATION = "invalid_configuration"
ISSUE_STALE_PROVIDER = "stale_provider"
