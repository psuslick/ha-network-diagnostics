from custom_components.network_diagnostics.const import ROLE_MESH_NODE
from custom_components.network_diagnostics.tag_hints import parse_tag_hint


def test_readable_tag_mapping_prefills_setup():
    hint = parse_tag_hint(
        {
            "tags": [
                {"name": "Network Diagnostics", "value": "Enabled"},
                {"name": "Network Diagnostics Role", "value": "Mesh / Wireless Node"},
                {"name": "Network Diagnostics Parent", "value": "Gateway A"},
                {"name": "Network Diagnostics Service", "value": "Service A"},
            ]
        }
    )
    assert hint.enrolled is True
    assert hint.role == ROLE_MESH_NODE
    assert hint.parent_name == "Gateway A"
    assert hint.service == "Service A"


def test_colon_string_tag_shape_is_supported():
    hint = parse_tag_hint(
        {"tags": ["Network Diagnostics:Enabled", "Network Diagnostics Role:Gateway"]}
    )
    assert hint.enrolled is True
    assert hint.role == "gateway"


def test_tags_are_optional_and_unknown_values_do_not_create_roles():
    hint = parse_tag_hint(None)
    assert hint.enrolled is False
    assert hint.role is None
    assert parse_tag_hint({"tags": ["Network Diagnostics Role=Unknown Role"]}).role is None
