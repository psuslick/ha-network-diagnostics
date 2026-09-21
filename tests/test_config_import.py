import pytest

from custom_components.network_diagnostics.config_import import (
    CONFIG_FILE_FORMAT,
    CONFIG_FILE_VERSION,
    ConfigImportError,
    ImportInventoryItem,
    import_monitor_config,
)
from custom_components.network_diagnostics.const import (
    CONF_PARENT,
    CONF_ROLE,
    CONF_SERVICE,
    ROLE_GATEWAY,
    ROLE_MESH_NODE,
    ROLE_SERVICE_DNS,
)


def inventory():
    return [
        ImportInventoryItem("entry:1", "Gateway A"),
        ImportInventoryItem("entry:2", "Mesh Node A"),
        ImportInventoryItem("entry:3", "Service DNS A"),
    ]


def test_portable_config_resolves_names_to_stable_local_ids():
    payload = {
        "format": CONFIG_FILE_FORMAT,
        "version": CONFIG_FILE_VERSION,
        "monitors": [
            {"name": "Gateway A", "role": "Gateway"},
            {
                "name": "Mesh Node A",
                "role": "mesh_node",
                "parent": "Gateway A",
            },
            {
                "name": "Service DNS A",
                "role": "Service DNS Control",
                "service": "Service A",
            },
        ],
    }
    config = import_monitor_config(payload, inventory())
    assert config["entry:1"][CONF_ROLE] == ROLE_GATEWAY
    assert config["entry:2"][CONF_ROLE] == ROLE_MESH_NODE
    assert config["entry:2"][CONF_PARENT] == "entry:1"
    assert config["entry:3"][CONF_ROLE] == ROLE_SERVICE_DNS
    assert config["entry:3"][CONF_SERVICE] == "Service A"


def test_missing_monitor_fails_closed():
    payload = {
        "format": CONFIG_FILE_FORMAT,
        "version": CONFIG_FILE_VERSION,
        "monitors": [{"name": "Missing", "role": "Gateway"}],
    }
    with pytest.raises(ConfigImportError, match="was not found"):
        import_monitor_config(payload, inventory())


def test_ambiguous_monitor_name_fails_closed():
    duplicate_inventory = [
        ImportInventoryItem("entry:1", "Same Name"),
        ImportInventoryItem("entry:2", "Same Name"),
    ]
    payload = {
        "format": CONFIG_FILE_FORMAT,
        "version": CONFIG_FILE_VERSION,
        "monitors": [{"name": "Same Name", "role": "Gateway"}],
    }
    with pytest.raises(ConfigImportError, match="ambiguous"):
        import_monitor_config(payload, duplicate_inventory)


def test_parent_must_be_in_imported_model():
    payload = {
        "format": CONFIG_FILE_FORMAT,
        "version": CONFIG_FILE_VERSION,
        "monitors": [
            {"name": "Mesh Node A", "role": "Mesh / Wireless Node", "parent": "Gateway A"}
        ],
    }
    with pytest.raises(ConfigImportError, match="not included"):
        import_monitor_config(payload, inventory())


def test_unknown_fields_and_roles_are_rejected():
    payload = {
        "format": CONFIG_FILE_FORMAT,
        "version": CONFIG_FILE_VERSION,
        "monitors": [
            {"name": "Gateway A", "role": "Magic Router", "target": "should-not-be-here"}
        ],
    }
    with pytest.raises(ConfigImportError):
        import_monitor_config(payload, inventory())


def test_wrong_format_version_is_rejected():
    with pytest.raises(ConfigImportError, match="Unsupported"):
        import_monitor_config(
            {"format": CONFIG_FILE_FORMAT, "version": 99, "monitors": []},
            inventory(),
        )
