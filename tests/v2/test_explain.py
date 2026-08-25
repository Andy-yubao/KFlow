import json

from kflow.v2.graph import KnowledgeGraph
from kflow.v2.models import (
    Derivation,
    DerivationInput,
    DerivationOutput,
    KnowledgeNode,
)
from kflow.v2.query import query_impact
from kflow.v2.scan import confirm
from kflow.v2.storage import initialize_project, save_graph


def prepare_graph(tmp_path) -> None:
    graph = KnowledgeGraph.build(
        tuple(
            KnowledgeNode(f"nd_{name}", name, (f"docs/{name}.md",))
            for name in ("a", "b", "c", "d")
        ),
        (
            Derivation(
                "dv_ab",
                "由 A 形成 B",
                "",
                (DerivationInput("nd_a", "提供 A", ""),),
                (DerivationOutput("nd_b", "形成 B", ""),),
            ),
            Derivation(
                "dv_bc",
                "由 B 形成 C",
                "",
                (DerivationInput("nd_b", "提供 B", ""),),
                (DerivationOutput("nd_c", "形成 C", ""),),
            ),
        ),
    )
    for node in graph.nodes.values():
        path = tmp_path / node.files[0]
        path.parent.mkdir(exist_ok=True)
        path.write_text(f"SECRET {node.name}", encoding="utf-8")
    initialize_project(tmp_path)
    save_graph(tmp_path, graph)
    for node_id in graph.topological_order():
        confirm(tmp_path, node_id)


def test_explain_distinguishes_direct_and_indirect_impact(tmp_path):
    prepare_graph(tmp_path)
    (tmp_path / "docs/a.md").write_text("a changed", encoding="utf-8")

    result = query_impact(tmp_path, "a")

    impact = result["impact"]
    assert [item["id"] for item in impact["changed_nodes"]] == ["nd_a"]
    assert impact["changed_nodes"][0]["reasons"] == ["files_changed"]
    by_id = {item["id"]: item for item in impact["affected_nodes"]}
    assert by_id["nd_b"]["depth"] == 1
    assert by_id["nd_b"]["impact_reason"] == "input_changed"
    assert by_id["nd_b"]["reasons"] == ["input_changed"]
    assert by_id["nd_c"]["depth"] == 2
    assert by_id["nd_c"]["impact_reason"] == "upstream_changed"
    assert by_id["nd_c"]["reasons"] == ["input_changed"]
    assert by_id["nd_c"]["paths"] == [
        {
            "root": "nd_a",
            "nodes": ["nd_a", "nd_b", "nd_c"],
            "derivations": ["dv_ab", "dv_bc"],
        }
    ]
    assert result["review_order"] == ["nd_a", "nd_b", "nd_c"]
    assert "SECRET" not in json.dumps(result)


def test_automatic_impact_merges_change_roots_with_stable_review_order(tmp_path):
    prepare_graph(tmp_path)
    (tmp_path / "docs/a.md").write_text("a changed", encoding="utf-8")
    (tmp_path / "docs/b.md").write_text("b changed", encoding="utf-8")

    result = query_impact(tmp_path)

    impact = result["impact"]
    assert [item["id"] for item in impact["changed_nodes"]] == ["nd_a", "nd_b"]
    by_id = {item["id"]: item for item in impact["affected_nodes"]}
    assert by_id["nd_b"]["roots"] == ["nd_a"]
    assert by_id["nd_c"]["depth"] == 1
    assert by_id["nd_c"]["roots"] == ["nd_a", "nd_b"]
    assert [path["root"] for path in by_id["nd_c"]["paths"]] == ["nd_a", "nd_b"]
    assert result["review_order"] == ["nd_a", "nd_b", "nd_c"]


def test_review_order_prefers_nearer_ready_nodes_without_breaking_topology(tmp_path):
    graph = KnowledgeGraph.build(
        tuple(
            KnowledgeNode(f"nd_{name}", name, (f"docs/{name}.md",))
            for name in ("a", "b", "c", "z")
        ),
        (
            Derivation(
                "dv_ab",
                "由 A 形成 B",
                "",
                (DerivationInput("nd_a", "提供 A", ""),),
                (DerivationOutput("nd_b", "形成 B", ""),),
            ),
            Derivation(
                "dv_bc",
                "由 B 形成 C",
                "",
                (DerivationInput("nd_b", "提供 B", ""),),
                (DerivationOutput("nd_c", "形成 C", ""),),
            ),
            Derivation(
                "dv_az",
                "由 A 形成 Z",
                "",
                (DerivationInput("nd_a", "提供 A", ""),),
                (DerivationOutput("nd_z", "形成 Z", ""),),
            ),
        ),
    )
    for node in graph.nodes.values():
        path = tmp_path / node.files[0]
        path.parent.mkdir(exist_ok=True)
        path.write_text(node.name, encoding="utf-8")
    initialize_project(tmp_path)
    save_graph(tmp_path, graph)
    for node_id in graph.topological_order():
        confirm(tmp_path, node_id)
    (tmp_path / "docs/a.md").write_text("a changed", encoding="utf-8")

    result = query_impact(tmp_path)

    assert result["review_order"] == ["nd_a", "nd_b", "nd_z", "nd_c"]
