from kflow.core.graph import KnowledgeGraph
from kflow.core.models import (
    Derivation,
    DerivationInput,
    DerivationOutput,
    KnowledgeNode,
)
from kflow.core.query import query_review_order
from kflow.core.scan import confirm
from kflow.core.storage import initialize_project, save_derivation, save_graph


def prepare_review_graph(tmp_path) -> KnowledgeGraph:
    nodes = tuple(
        KnowledgeNode(f"nd_{name}", name, (f"docs/{name}.md",))
        for name in ("a", "b", "c", "d", "standalone")
    )
    graph = KnowledgeGraph.build(
        nodes,
        (
            Derivation(
                "dv_ab_c",
                "combine-roots",
                "Combine roots",
                "",
                (
                    DerivationInput("nd_a", "A role", ""),
                    DerivationInput("nd_b", "B role", ""),
                ),
                (DerivationOutput("nd_c", "C role", ""),),
            ),
            Derivation(
                "dv_c_d",
                "continue-once",
                "Continue once",
                "",
                (DerivationInput("nd_c", "C role", ""),),
                (DerivationOutput("nd_d", "D role", ""),),
            ),
        ),
    )
    for node in nodes:
        path = tmp_path / node.files[0]
        path.parent.mkdir(exist_ok=True)
        path.write_text(node.name, encoding="utf-8")
    initialize_project(tmp_path)
    save_graph(tmp_path, graph)
    for node_id in graph.topological_order():
        confirm(tmp_path, node_id)
    return graph


def test_global_review_order_merges_roots_and_deduplicates_convergence(
    tmp_path,
) -> None:
    prepare_review_graph(tmp_path)
    (tmp_path / "docs/a.md").write_text("A changed", encoding="utf-8")
    (tmp_path / "docs/b.md").write_text("B changed", encoding="utf-8")

    result = query_review_order(tmp_path)

    assert result["review_order"] == ["nd_a", "nd_b", "nd_c", "nd_d"]
    assert [item["name"] for item in result["nodes"]] == ["a", "b", "c", "d"]
    assert result["nodes"][0]["reasons"] == ["files_changed"]
    assert result["nodes"][2]["reasons"] == ["input_changed"]


def test_scoped_review_order_is_inclusive_but_filters_current_root(tmp_path) -> None:
    prepare_review_graph(tmp_path)
    (tmp_path / "docs/c.md").write_text("C changed", encoding="utf-8")

    first = query_review_order(tmp_path, "c")
    confirm(tmp_path, "c")
    remaining = query_review_order(tmp_path, "c")
    confirm(tmp_path, "d")
    clear = query_review_order(tmp_path, "c")

    assert first["review_order"] == ["nd_c", "nd_d"]
    assert remaining["review_order"] == ["nd_d"]
    assert clear["review_order"] == []
    assert clear["scope"]["name"] == "c"


def test_derivation_changes_and_unconfirmed_nodes_are_review_items(tmp_path) -> None:
    prepare_review_graph(tmp_path)
    save_derivation(
        tmp_path,
        Derivation(
            "dv_c_d",
            "continue-once",
            "Changed derivation",
            "",
            (DerivationInput("nd_c", "C changed role", ""),),
            (DerivationOutput("nd_d", "D role", ""),),
        ),
    )
    new_path = tmp_path / "docs/new.md"
    new_path.write_text("new", encoding="utf-8")
    graph = KnowledgeGraph.build(
        (
            *prepare_nodes_for_reload(tmp_path),
            KnowledgeNode("nd_new", "new", ("docs/new.md",)),
        ),
        tuple(load_derivations_for_reload(tmp_path)),
    )
    save_graph(tmp_path, graph)

    result = query_review_order(tmp_path)
    by_name = {item["name"]: item for item in result["nodes"]}

    assert by_name["d"]["reasons"] == ["derivation_changed"]
    assert by_name["new"]["reasons"] == ["unconfirmed"]


def prepare_nodes_for_reload(tmp_path):
    from kflow.core.storage import load_graph

    return tuple(load_graph(tmp_path).nodes.values())


def load_derivations_for_reload(tmp_path):
    from kflow.core.storage import load_graph

    return tuple(load_graph(tmp_path).derivations.values())
