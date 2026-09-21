from custom_components.network_diagnostics.const import (
    ROLE_FIXED_CLIENT,
    ROLE_GATEWAY,
    ROLE_MESH_NODE,
    ROLE_NETWORK_NODE,
)
from custom_components.network_diagnostics.observations import ObservationSet
from custom_components.network_diagnostics.topology import (
    ancestor_ids,
    descendant_ids,
    failed_root_nodes,
    impact_for,
    path_names,
    topology_payload,
    validate_topology,
)


def test_arbitrary_depth_and_impact(make_binding):
    bindings = [
        make_binding("g", "Gateway A", ROLE_GATEWAY),
        make_binding("s", "Switch A", ROLE_NETWORK_NODE, parent_id="g"),
        make_binding("m", "Mesh Node A", ROLE_MESH_NODE, parent_id="s"),
        make_binding("c", "Fixed Client A", ROLE_FIXED_CLIENT, parent_id="m"),
    ]
    assert ancestor_ids("c", bindings) == ["m", "s", "g"]
    assert descendant_ids("g", bindings) == ["s", "m", "c"]
    assert path_names("c", bindings) == (
        "Gateway A",
        "Switch A",
        "Mesh Node A",
        "Fixed Client A",
    )
    impact = impact_for("s", bindings)
    assert impact is not None
    assert impact.ancestors == ("Gateway A",)
    assert impact.descendants == ("Mesh Node A", "Fixed Client A")
    assert impact.direct_children == ("Mesh Node A",)


def test_topology_payload_is_human_readable(make_binding):
    bindings = [
        make_binding("g", "Gateway A", ROLE_GATEWAY),
        make_binding("m", "Mesh Node A", ROLE_MESH_NODE, parent_id="g"),
        make_binding("c", "Fixed Client A", ROLE_FIXED_CLIENT, parent_id="m"),
    ]
    rows = topology_payload(bindings)
    gateway = next(row for row in rows if row["monitor_id"] == "g")
    assert gateway["role_name"] == "Gateway"
    assert gateway["children"] == ["Mesh Node A"]
    assert gateway["impact"] == ["Mesh Node A", "Fixed Client A"]


def test_cycle_is_blocking(make_binding):
    bindings = [
        make_binding("a", "Node A", ROLE_NETWORK_NODE, parent_id="b"),
        make_binding("b", "Node B", ROLE_NETWORK_NODE, parent_id="a"),
    ]
    _warnings, blockers = validate_topology(bindings)
    assert any("cycle" in item.lower() for item in blockers)


def test_missing_parent_is_blocking(make_binding):
    bindings = [make_binding("m", "Mesh Node A", ROLE_MESH_NODE, parent_id="missing")]
    _warnings, blockers = validate_topology(bindings)
    assert any("not configured" in item for item in blockers)


def test_failed_ancestor_suppresses_descendant_root(make_binding, make_observation):
    gateway = make_binding("g", "Gateway A", ROLE_GATEWAY)
    mesh = make_binding("m", "Mesh Node A", ROLE_MESH_NODE, parent_id="g")
    child = make_binding("c", "Fixed Client A", ROLE_FIXED_CLIENT, parent_id="m")
    obs = ObservationSet(
        observations=[
            make_observation(gateway, True),
            make_observation(mesh, False),
            make_observation(child, False),
        ]
    )
    roots = failed_root_nodes(obs)
    assert len(roots) == 1
    root, downstream = roots[0]
    assert root.binding.monitor_id == "m"
    assert [item.binding.monitor_id for item in downstream] == ["c"]
