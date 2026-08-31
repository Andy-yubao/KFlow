from kflow.core.graph import KnowledgeGraph
from kflow.core.models import (
    Derivation,
    DerivationInput,
    DerivationOutput,
    KnowledgeNode,
)
from kflow.core.query import query_impact
from kflow.core.storage import initialize_project, save_graph


def prepare_impact_graph(tmp_path) -> None:
    nodes = tuple(
        KnowledgeNode(f"nd_{name}", name, (f"docs/{name}.md",))
        for name in ("a", "b", "c", "d", "e", "f", "g")
    )
    derivations = (
        Derivation(
            "dv_ab_cd",
            "Combine A and B",
            "",
            (
                DerivationInput("nd_a", "A selected role", ""),
                DerivationInput("nd_b", "B peer role", ""),
            ),
            (
                DerivationOutput("nd_c", "C output", ""),
                DerivationOutput("nd_d", "D output", ""),
            ),
        ),
        Derivation(
            "dv_a_e",
            "Use A for E",
            "",
            (DerivationInput("nd_a", "A second role", ""),),
            (DerivationOutput("nd_e", "E output", ""),),
        ),
        Derivation(
            "dv_cde_f",
            "Converge at F",
            "",
            (
                DerivationInput("nd_c", "C role", ""),
                DerivationInput("nd_d", "D role", ""),
                DerivationInput("nd_e", "E role", ""),
            ),
            (DerivationOutput("nd_f", "F output", ""),),
        ),
        Derivation(
            "dv_f_g",
            "Continue to G",
            "",
            (DerivationInput("nd_f", "F role", ""),),
            (DerivationOutput("nd_g", "G output", ""),),
        ),
    )
    graph = KnowledgeGraph.build(nodes, derivations)
    for node in nodes:
        path = tmp_path / node.files[0]
        path.parent.mkdir(exist_ok=True)
        path.write_text(node.name, encoding="utf-8")
    initialize_project(tmp_path)
    save_graph(tmp_path, graph)


def test_impact_keeps_direct_derivations_atomic_and_further_nodes_unique(
    tmp_path,
) -> None:
    prepare_impact_graph(tmp_path)

    result = query_impact(tmp_path, "a")

    assert [item["id"] for item in result["direct_derivations"]] == [
        "dv_ab_cd",
        "dv_a_e",
    ]
    first = result["direct_derivations"][0]
    assert [role["name"] for role in first["inputs"]] == ["a", "b"]
    assert [role["name"] for role in first["outputs"]] == ["c", "d"]
    assert [item["name"] for item in result["direct_outputs"]] == ["c", "d", "e"]
    assert [item["name"] for item in result["further_downstream"]] == ["f", "g"]


def test_impact_with_no_consumer_has_no_downstream_sections(tmp_path) -> None:
    prepare_impact_graph(tmp_path)

    result = query_impact(tmp_path, "g")

    assert result["direct_derivations"] == []
    assert result["direct_outputs"] == []
    assert result["further_downstream"] == []
