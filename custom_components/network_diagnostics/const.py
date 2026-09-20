"""Constants for Network Diagnostics."""

from __future__ import annotations

DOMAIN = "network_diagnostics"
NAME = "Network Diagnostics"
VERSION = "0.2.0"
STORAGE_VERSION = 2
STORAGE_KEY_PREFIX = "network_diagnostics.incidents"

PLATFORMS = ["sensor", "binary_sensor", "event", "button"]

PANEL_URL_PATH = "network-diagnostics-app"
PANEL_TITLE = "Network Diagnostics"
PANEL_ICON = "mdi:lan-check"
STATIC_URL = "/network_diagnostics_static"

CONF_STALE_SECONDS = "stale_seconds"
CONF_FAILURE_CONFIRM_SECONDS = "failure_confirm_seconds"
CONF_RECOVERY_CONFIRM_SECONDS = "recovery_confirm_seconds"
CONF_MESH_LATENCY_MS = "mesh_latency_ms"
CONF_MESH_DEGRADATION_SECONDS = "mesh_degradation_seconds"
CONF_INCIDENT_RETENTION = "incident_retention"

DEFAULT_STALE_SECONDS = 180
DEFAULT_FAILURE_CONFIRM_SECONDS = 15
DEFAULT_RECOVERY_CONFIRM_SECONDS = 60
DEFAULT_MESH_LATENCY_MS = 25.0
DEFAULT_MESH_DEGRADATION_SECONDS = 90
DEFAULT_INCIDENT_RETENTION = 200

BEHAVIOR_DEFAULTS: dict[str, int | float] = {
    CONF_STALE_SECONDS: DEFAULT_STALE_SECONDS,
    CONF_FAILURE_CONFIRM_SECONDS: DEFAULT_FAILURE_CONFIRM_SECONDS,
    CONF_RECOVERY_CONFIRM_SECONDS: DEFAULT_RECOVERY_CONFIRM_SECONDS,
    CONF_MESH_LATENCY_MS: DEFAULT_MESH_LATENCY_MS,
    CONF_MESH_DEGRADATION_SECONDS: DEFAULT_MESH_DEGRADATION_SECONDS,
    CONF_INCIDENT_RETENTION: DEFAULT_INCIDENT_RETENTION,
}

BEHAVIOR_OPTION_KEYS = tuple(BEHAVIOR_DEFAULTS)

# Logical roles discovered from Uptime Kuma monitor names.
ROLE_GATEWAY = "gateway"
ROLE_LAN_CONTROL = "lan_control"
ROLE_MESH = "mesh"
ROLE_MESH_CHILD = "mesh_child"
ROLE_IPV4 = "ipv4"
ROLE_IPV6 = "ipv6"
ROLE_DNS_NEUTRAL = "dns_neutral"
ROLE_DNS_LOCAL = "dns_local"
ROLE_HTTPS = "https"
ROLE_SERVICE_DNS = "service_dns"
ROLE_SERVICE_PATH = "service_path"

CORE_ROLES = {
    ROLE_GATEWAY,
    ROLE_LAN_CONTROL,
    ROLE_MESH,
    ROLE_MESH_CHILD,
    ROLE_IPV4,
    ROLE_IPV6,
    ROLE_DNS_NEUTRAL,
    ROLE_DNS_LOCAL,
    ROLE_HTTPS,
    ROLE_SERVICE_DNS,
    ROLE_SERVICE_PATH,
}

GOOD_STATUS = "up"
BAD_STATUS = "down"
UNUSABLE_STATUSES = {"unknown", "unavailable", "none", "", "pending", "maintenance"}

# Current deployment monitor names are supported without requiring a rename.
LEGACY_NAME_ROLES: dict[str, tuple[str, str | None]] = {
    "Orbi LAN": (ROLE_GATEWAY, None),
    "LAN Control": (ROLE_LAN_CONTROL, None),
    "Orbi Satellite 1": (ROLE_MESH, "Satellite 1"),
    "Orbi Sarah Room": (ROLE_MESH, "Sarah Room"),
    "Internet IPv4": (ROLE_IPV4, None),
    "Google IPv4": (ROLE_IPV4, None),
    "Internet IPv6": (ROLE_IPV6, None),
    "Google IPv6": (ROLE_IPV6, None),
    "DNS via Cloudflare": (ROLE_DNS_NEUTRAL, None),
    "DNS via Orbi": (ROLE_DNS_LOCAL, None),
    "Internet HTTPS": (ROLE_HTTPS, None),
    "DNS via NextDNS 1": (ROLE_SERVICE_DNS, "NextDNS"),
    "DNS via NextDNS 2": (ROLE_SERVICE_DNS, "NextDNS"),
    "NextDNS IPv4 1": (ROLE_SERVICE_PATH, "NextDNS"),
    "NextDNS IPv4 2": (ROLE_SERVICE_PATH, "NextDNS"),
    "NextDNS IPv6 1": (ROLE_SERVICE_PATH, "NextDNS"),
    "NextDNS IPv6 2": (ROLE_SERVICE_PATH, "NextDNS"),
    "NextDNS TCP 443 1": (ROLE_SERVICE_PATH, "NextDNS"),
    "NextDNS TCP 443 2": (ROLE_SERVICE_PATH, "NextDNS"),
}

# Generic naming contract for other installations:
#   [ND:gateway] Main router
#   [ND:mesh] Upstairs AP
#   [ND:mesh-child:Upstairs AP] Wired downstream control
#   [ND:ipv4] Cloudflare
#   [ND:dns-neutral] Cloudflare DNS
#   [ND:service:NextDNS:dns] Resolver 1
#   [ND:service:NextDNS:path] Resolver path 1
NAME_MARKER_PREFIX = "[ND:"
