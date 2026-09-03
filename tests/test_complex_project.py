from kflow.core.graph import KnowledgeGraph
from kflow.core.models import (
    Derivation,
    DerivationInput,
    DerivationOutput,
    KnowledgeNode,
)
from kflow.core.query import query_impact, query_review_order
from kflow.core.scan import confirm
from kflow.core.storage import initialize_project, save_graph


def prepare_complex_project(tmp_path) -> KnowledgeGraph:
    nodes = tuple(
        KnowledgeNode(f"nd_{name}", name, (f"docs/{name}.md",))
        for name in (
            "requirements",
            "architecture",
            "hardware",
            "software",
            "implementation",
            "tests",
        )
    )
    graph = KnowledgeGraph.build(
        nodes,
        (
            Derivation(
                "dv_requirements_architecture",
                "requirements-architecture",
                "由需求形成架构",
                "",
                (DerivationInput("nd_requirements", "提供需求", ""),),
                (DerivationOutput("nd_architecture", "形成架构", ""),),
            ),
            Derivation(
                "dv_architecture_designs",
                "architecture-designs",
                "由架构形成软硬件设计",
                "",
                (DerivationInput("nd_architecture", "提供架构", ""),),
                (
                    DerivationOutput("nd_hardware", "形成硬件设计", ""),
                    DerivationOutput("nd_software", "形成软件设计", ""),
                ),
            ),
            Derivation(
                "dv_designs_implementation",
                "designs-implementation",
                "综合软硬件设计形成实现",
                "",
                (
                    DerivationInput("nd_hardware", "提供硬件设计", ""),
                    DerivationInput("nd_software", "提供软件设计", ""),
                ),
                (DerivationOutput("nd_implementation", "形成实现", ""),),
            ),
            Derivation(
                "dv_implementation_tests",
                "implementation-tests",
                "由实现形成测试",
                "",
                (DerivationInput("nd_implementation", "提供实现", ""),),
                (DerivationOutput("nd_tests", "形成测试", ""),),
            ),
        ),
    )
    for node in graph.nodes.values():
        path = tmp_path / node.files[0]
        path.parent.mkdir(exist_ok=True)
        path.write_text(f"PRIVATE {node.name}", encoding="utf-8")
    initialize_project(tmp_path)
    save_graph(tmp_path, graph)
    for node_id in graph.topological_order():
        confirm(tmp_path, node_id)
    return graph


def test_complex_branches_propagate_with_stable_review_order(tmp_path) -> None:
    graph = prepare_complex_project(tmp_path)
    (tmp_path / "docs/requirements.md").write_text(
        "PRIVATE requirements changed", encoding="utf-8"
    )

    result = query_review_order(tmp_path)

    assert result["ok"] is True
    assert {item["id"] for item in result["nodes"]} == set(graph.nodes)
    assert result["review_order"] == [
        "nd_requirements",
        "nd_architecture",
        "nd_hardware",
        "nd_software",
        "nd_implementation",
        "nd_tests",
    ]


def test_multi_output_branch_reports_both_direct_outputs(tmp_path) -> None:
    prepare_complex_project(tmp_path)
    (tmp_path / "docs/architecture.md").write_text(
        "PRIVATE architecture changed", encoding="utf-8"
    )

    result = query_impact(tmp_path, "architecture")
    assert [item["name"] for item in result["direct_outputs"]] == [
        "hardware",
        "software",
    ]
    assert [item["name"] for item in result["further_downstream"]] == [
        "implementation",
        "tests",
    ]
