"""Pure structural graph diff tests."""

from copy import deepcopy

from kflow.human.graph_diff import compare_project_graphs


def _node(node_id: str, *, name: str | None = None, files: list[str] | None = None):
    return {
        "id": node_id,
        "name": name or node_id,
        "files": files or [f"docs/{node_id}.md"],
        "changed_files": [],
        "status": "confirmed",
        "reasons": [],
    }


def _role(node_id: str, *, short: str | None = None, detail: str = ""):
    return {
        "node": node_id,
        "name": node_id,
        "short": short or f"Role {node_id}",
        "detail": detail,
    }


def _derivation(
    derivation_id: str,
    inputs: list[str],
    outputs: list[str],
    *,
    short: str = "Derive outputs",
    detail: str = "Complete structural meaning.",
):
    return {
        "id": derivation_id,
        "short": short,
        "detail": detail,
        "inputs": [_role(node_id) for node_id in inputs],
        "outputs": [_role(node_id) for node_id in outputs],
    }


def _graph(nodes, derivations=(), order=None):
    nodes = list(nodes)
    derivations = list(derivations)
    return {
        "ok": True,
        "schema_version": 2,
        "project": {
            "status": "current",
            "node_count": len(nodes),
            "derivation_count": len(derivations),
            "needs_review_count": 0,
            "issue_count": 0,
        },
        "nodes": nodes,
        "derivations": derivations,
        "topological_order": order or [node["id"] for node in nodes],
        "issues": [],
    }


def test_identical_graphs_have_a_stable_empty_diff():
    graph = _graph([_node("nd_a")])

    result = compare_project_graphs(graph, deepcopy(graph))

    assert result["summary"] == {
        "added_nodes": 0,
        "removed_nodes": 0,
        "changed_nodes": 0,
        "added_derivations": 0,
        "removed_derivations": 0,
        "changed_derivations": 0,
        "topology_changed": False,
    }
    assert result["nodes"] == {"added": [], "removed": [], "changed": []}
    assert result["derivations"] == {
        "added": [],
        "removed": [],
        "changed": [],
    }


def test_nodes_are_aligned_by_id_and_compare_only_public_structure():
    before = _graph(
        [_node("nd_removed"), _node("nd_changed", name="Before")],
        order=["nd_removed", "nd_changed"],
    )
    after = _graph(
        [
            _node("nd_changed", name="After", files=["docs/a.md", "docs/b.md"]),
            _node("nd_added"),
        ],
        order=["nd_changed", "nd_added"],
    )

    result = compare_project_graphs(before, after)

    assert [item["id"] for item in result["nodes"]["added"]] == ["nd_added"]
    assert [item["id"] for item in result["nodes"]["removed"]] == ["nd_removed"]
    assert result["nodes"]["changed"] == [
        {
            "id": "nd_changed",
            "changed_fields": ["name", "files"],
            "before": {
                "id": "nd_changed",
                "name": "Before",
                "files": ["docs/nd_changed.md"],
            },
            "after": {
                "id": "nd_changed",
                "name": "After",
                "files": ["docs/a.md", "docs/b.md"],
            },
        }
    ]

    status_only = deepcopy(after)
    status_only["nodes"][0].update(
        status="affected",
        reasons=["files_changed"],
        changed_files=["docs/a.md"],
    )
    assert compare_project_graphs(after, status_only)["nodes"]["changed"] == []


def test_derivations_preserve_complete_many_to_many_semantics_and_role_changes():
    before_derivation = _derivation("dv_design", ["nd_a", "nd_b"], ["nd_c", "nd_d"])
    after_derivation = deepcopy(before_derivation)
    after_derivation["short"] = "Updated short"
    after_derivation["detail"] = "Updated detail"
    after_derivation["inputs"][0]["short"] = "Updated input role"
    after_derivation["outputs"][1]["detail"] = "Updated output role"
    before = _graph(
        [_node(f"nd_{name}") for name in "abcd"],
        [
            _derivation("dv_removed", ["nd_a"], ["nd_b"]),
            before_derivation,
        ],
    )
    after = _graph(
        [_node(f"nd_{name}") for name in "abcd"],
        [
            after_derivation,
            _derivation("dv_added", ["nd_c"], ["nd_d"]),
        ],
    )

    result = compare_project_graphs(before, after)

    assert [item["id"] for item in result["derivations"]["added"]] == ["dv_added"]
    assert [item["id"] for item in result["derivations"]["removed"]] == ["dv_removed"]
    changed = result["derivations"]["changed"][0]
    assert changed["id"] == "dv_design"
    assert changed["changed_fields"] == ["short", "detail", "inputs", "outputs"]
    assert [role["node"] for role in changed["before"]["inputs"]] == [
        "nd_a",
        "nd_b",
    ]
    assert [role["node"] for role in changed["after"]["outputs"]] == [
        "nd_c",
        "nd_d",
    ]


def test_all_supported_derivation_shapes_remain_single_objects():
    for input_ids, output_ids in (
        (["nd_a"], ["nd_b"]),
        (["nd_a"], ["nd_b", "nd_c"]),
        (["nd_a", "nd_b"], ["nd_c"]),
        (["nd_a", "nd_b"], ["nd_c", "nd_d"]),
    ):
        nodes = [_node(node_id) for node_id in sorted(set(input_ids + output_ids))]
        before = _graph(nodes)
        after = _graph(nodes, [_derivation("dv_shape", input_ids, output_ids)])
        result = compare_project_graphs(before, after)
        assert result["derivations"]["added"] == [
            _derivation("dv_shape", input_ids, output_ids)
        ]


def test_topological_order_and_all_diff_arrays_are_deterministic():
    before = _graph([_node("nd_z"), _node("nd_a")], order=["nd_a", "nd_z"])
    after = _graph(
        [_node("nd_y"), _node("nd_b")],
        order=["nd_b", "nd_y"],
    )

    first = compare_project_graphs(before, after)
    second = compare_project_graphs(before, after)

    assert first == second
    assert [item["id"] for item in first["nodes"]["added"]] == ["nd_b", "nd_y"]
    assert [item["id"] for item in first["nodes"]["removed"]] == ["nd_a", "nd_z"]
    assert first["summary"]["topology_changed"] is True
    assert first["before_topological_order"] == ["nd_a", "nd_z"]
    assert first["after_topological_order"] == ["nd_b", "nd_y"]
