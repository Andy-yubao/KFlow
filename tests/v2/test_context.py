import json

from kflow.v2.graph import KnowledgeGraph
from kflow.v2.models import (
    Derivation,
    DerivationInput,
    DerivationOutput,
    KnowledgeNode,
)
from kflow.v2.query import query_context
from kflow.v2.scan import confirm
from kflow.v2.storage import initialize_project, save_graph


def prepare_chain(tmp_path) -> None:
    graph = KnowledgeGraph.build(
        (
            KnowledgeNode("nd_a", "requirements", ("docs/requirements.md",)),
            KnowledgeNode("nd_b", "architecture", ("docs/architecture.md",)),
            KnowledgeNode("nd_c", "implementation", ("docs/implementation.md",)),
        ),
        (
            Derivation(
                "dv_ab",
                "由需求形成架构",
                "",
                (DerivationInput("nd_a", "提供需求", ""),),
                (DerivationOutput("nd_b", "形成架构", ""),),
            ),
            Derivation(
                "dv_bc",
                "由架构形成实现",
                "",
                (DerivationInput("nd_b", "提供架构", ""),),
                (DerivationOutput("nd_c", "形成实现", ""),),
            ),
        ),
    )
    for node in graph.nodes.values():
        path = tmp_path / node.files[0]
        path.parent.mkdir(exist_ok=True)
        path.write_text(f"PRIVATE CONTENT {node.name}", encoding="utf-8")
    initialize_project(tmp_path)
    save_graph(tmp_path, graph)
    for node_id in graph.topological_order():
        confirm(tmp_path, node_id)


def test_context_reports_node_status_relationships_and_derivations(tmp_path):
    prepare_chain(tmp_path)

    result = query_context(tmp_path, "architecture")

    assert result["node"] == {
        "id": "nd_b",
        "name": "architecture",
        "files": ["docs/architecture.md"],
        "changed_files": [],
    }
    assert result["status"] == "confirmed"
    assert result["reasons"] == []
    relations = result["relations"]
    assert [node["name"] for node in relations["upstream"]] == ["requirements"]
    assert [node["name"] for node in relations["downstream"]] == ["implementation"]
    assert [item["id"] for item in relations["derivations"]] == ["dv_ab", "dv_bc"]
    assert relations["derivations"][0]["inputs"] == [
        {"node": "nd_a", "name": "requirements", "short": "提供需求", "detail": ""}
    ]
    assert result["issues"] == []


def test_context_never_returns_registered_file_contents(tmp_path):
    prepare_chain(tmp_path)

    encoded = json.dumps(query_context(tmp_path, "architecture"), ensure_ascii=False)

    assert "PRIVATE CONTENT" not in encoded
