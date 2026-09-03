import json

from kflow.core.graph import KnowledgeGraph
from kflow.core.models import (
    Derivation,
    DerivationInput,
    DerivationOutput,
    KnowledgeNode,
)
from kflow.core.query import query_context
from kflow.core.scan import confirm
from kflow.core.storage import initialize_project, save_graph


def prepare_local_graph(tmp_path) -> None:
    names = ("a", "b", "c", "d", "e", "f", "g", "source", "terminal")
    nodes = tuple(
        KnowledgeNode(f"nd_{name}", name, (f"docs/{name}.md",)) for name in names
    )
    derivations = (
        Derivation(
            "dv_ab_cd",
            "combine-a-b",
            "Combine A and B",
            "",
            (
                DerivationInput("nd_a", "A role", ""),
                DerivationInput("nd_b", "B role", ""),
            ),
            (
                DerivationOutput("nd_c", "C role", ""),
                DerivationOutput("nd_d", "D sibling role", ""),
            ),
        ),
        Derivation(
            "dv_c_e",
            "use-c-for-e",
            "Use C for E",
            "",
            (DerivationInput("nd_c", "C consumer role", ""),),
            (DerivationOutput("nd_e", "E role", ""),),
        ),
        Derivation(
            "dv_cd_f",
            "use-c-d-for-f",
            "Use C and D for F",
            "",
            (
                DerivationInput("nd_c", "C second consumer role", ""),
                DerivationInput("nd_d", "D second input role", ""),
            ),
            (DerivationOutput("nd_f", "F role", ""),),
        ),
        Derivation(
            "dv_e_g",
            "use-e-for-g",
            "Use E for G",
            "",
            (DerivationInput("nd_e", "E role", ""),),
            (DerivationOutput("nd_g", "G role", ""),),
        ),
    )
    graph = KnowledgeGraph.build(nodes, derivations)
    for node in nodes:
        path = tmp_path / node.files[0]
        path.parent.mkdir(exist_ok=True)
        path.write_text(f"PRIVATE {node.name}", encoding="utf-8")
    initialize_project(tmp_path)
    save_graph(tmp_path, graph)
    for node_id in graph.topological_order():
        confirm(tmp_path, node_id)


def test_context_returns_only_direct_complete_derivations_and_statuses(
    tmp_path,
) -> None:
    prepare_local_graph(tmp_path)
    (tmp_path / "docs/a.md").write_text("A changed", encoding="utf-8")

    result = query_context(tmp_path, "c")

    assert result["node"]["name"] == "c"
    assert result["node"]["reasons"] == ["input_changed"]
    assert result["producing_derivation"]["id"] == "dv_ab_cd"
    assert [item["id"] for item in result["consumer_derivations"]] == [
        "dv_c_e",
        "dv_cd_f",
    ]
    assert {item["name"] for item in result["nodes"]} == {
        "a",
        "b",
        "c",
        "d",
        "e",
        "f",
    }
    by_name = {item["name"]: item for item in result["nodes"]}
    assert by_name["a"]["reasons"] == ["files_changed"]
    assert by_name["d"]["reasons"] == ["input_changed"]
    assert "g" not in by_name
    assert "review_order" not in result
    assert "impact" not in result
    assert "PRIVATE" not in json.dumps(result)


def test_context_source_and_terminal_have_explicit_empty_sides(tmp_path) -> None:
    prepare_local_graph(tmp_path)

    source = query_context(tmp_path, "source")
    terminal = query_context(tmp_path, "g")

    assert source["producing_derivation"] is None
    assert source["consumer_derivations"] == []
    assert [node["name"] for node in source["nodes"]] == ["source"]
    assert terminal["producing_derivation"]["id"] == "dv_e_g"
    assert terminal["consumer_derivations"] == []
