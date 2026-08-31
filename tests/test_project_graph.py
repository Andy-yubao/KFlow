import json
from typing import get_type_hints

from kflow.core import ProjectGraphResult, query_project_graph
from kflow.core.graph import KnowledgeGraph
from kflow.core.models import (
    Derivation,
    DerivationInput,
    DerivationOutput,
    KnowledgeNode,
)
from kflow.core.scan import confirm
from kflow.core.storage import initialize_project, save_graph


def prepare_many_to_many_project(tmp_path) -> None:
    nodes = tuple(
        KnowledgeNode(f"nd_{name}", name, (f"docs/{name}.md",))
        for name in ("a", "b", "c", "d")
    )
    derivation = Derivation(
        "dv_design",
        "形成 C 和 D",
        "保留多输入、多输出语义。",
        (
            DerivationInput("nd_a", "使用 A", "输入 A 的约束。"),
            DerivationInput("nd_b", "使用 B", "输入 B 的约束。"),
        ),
        (
            DerivationOutput("nd_c", "形成 C", "输出 C。"),
            DerivationOutput("nd_d", "形成 D", "输出 D。"),
        ),
    )
    for node in nodes:
        path = tmp_path / node.files[0]
        path.parent.mkdir(exist_ok=True)
        path.write_text(f"PRIVATE CONTENT {node.name}", encoding="utf-8")
    initialize_project(tmp_path)
    save_graph(tmp_path, KnowledgeGraph.build(nodes, (derivation,)))


def test_project_graph_is_a_public_typed_query_with_stable_empty_result(tmp_path):
    initialize_project(tmp_path)

    result = query_project_graph(tmp_path)

    assert get_type_hints(query_project_graph)["return"] is ProjectGraphResult
    assert result == {
        "ok": True,
        "schema_version": 2,
        "project": {
            "status": "current",
            "node_count": 0,
            "derivation_count": 0,
            "needs_review_count": 0,
            "issue_count": 0,
        },
        "nodes": [],
        "derivations": [],
        "topological_order": [],
        "issues": [],
    }


def test_project_graph_preserves_all_facts_statuses_and_deterministic_order(tmp_path):
    prepare_many_to_many_project(tmp_path)
    confirm(tmp_path, "a")
    (tmp_path / "docs/a.md").write_text("A changed", encoding="utf-8")

    result = query_project_graph(tmp_path)
    repeated = query_project_graph(tmp_path)

    assert result == repeated
    assert result["project"] == {
        "status": "attention_required",
        "node_count": 4,
        "derivation_count": 1,
        "needs_review_count": 4,
        "issue_count": 0,
    }
    assert result["topological_order"] == ["nd_a", "nd_b", "nd_c", "nd_d"]
    assert [node["id"] for node in result["nodes"]] == result["topological_order"]
    by_id = {node["id"]: node for node in result["nodes"]}
    assert by_id["nd_a"]["status"] == "affected"
    assert by_id["nd_a"]["reasons"] == ["files_changed"]
    assert by_id["nd_a"]["changed_files"] == ["docs/a.md"]
    assert by_id["nd_b"]["status"] == "valid"
    assert by_id["nd_b"]["reasons"] == ["unconfirmed"]

    assert result["derivations"] == [
        {
            "id": "dv_design",
            "short": "形成 C 和 D",
            "detail": "保留多输入、多输出语义。",
            "inputs": [
                {
                    "node": "nd_a",
                    "name": "a",
                    "short": "使用 A",
                    "detail": "输入 A 的约束。",
                },
                {
                    "node": "nd_b",
                    "name": "b",
                    "short": "使用 B",
                    "detail": "输入 B 的约束。",
                },
            ],
            "outputs": [
                {
                    "node": "nd_c",
                    "name": "c",
                    "short": "形成 C",
                    "detail": "输出 C。",
                },
                {
                    "node": "nd_d",
                    "name": "d",
                    "short": "形成 D",
                    "detail": "输出 D。",
                },
            ],
        }
    ]
    assert "PRIVATE CONTENT" not in json.dumps(result, ensure_ascii=False)


def test_project_graph_v2_keeps_machine_order_independent_from_topology(tmp_path):
    nodes = (
        KnowledgeNode("nd_z_source", "source", ("docs/source.md",)),
        KnowledgeNode("nd_m_peer", "peer", ("docs/peer.md",)),
        KnowledgeNode("nd_a_later", "later", ("docs/later.md",)),
        KnowledgeNode("nd_b_final", "final", ("docs/final.md",)),
    )
    derivations = (
        Derivation(
            "dv_z_first",
            "First in topology",
            "",
            (DerivationInput("nd_z_source", "source role", ""),),
            (DerivationOutput("nd_a_later", "later role", ""),),
        ),
        Derivation(
            "dv_a_second",
            "Second in topology",
            "",
            (
                DerivationInput("nd_m_peer", "peer role", ""),
                DerivationInput("nd_a_later", "later role", ""),
            ),
            (DerivationOutput("nd_b_final", "final role", ""),),
        ),
    )
    for node in nodes:
        path = tmp_path / node.files[0]
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(node.name, encoding="utf-8")
    initialize_project(tmp_path)
    save_graph(tmp_path, KnowledgeGraph.build(nodes, derivations))

    result = query_project_graph(tmp_path)

    assert result["topological_order"] == [
        "nd_m_peer",
        "nd_z_source",
        "nd_a_later",
        "nd_b_final",
    ]
    assert [item["id"] for item in result["derivations"]] == [
        "dv_a_second",
        "dv_z_first",
    ]
    assert [item["node"] for item in result["derivations"][0]["inputs"]] == [
        "nd_a_later",
        "nd_m_peer",
    ]


def test_project_graph_reports_scan_issues_without_losing_graph_facts(tmp_path):
    prepare_many_to_many_project(tmp_path)
    (tmp_path / "docs/c.md").unlink()

    result = query_project_graph(tmp_path)

    assert result["ok"] is False
    assert result["project"]["status"] == "invalid"
    assert result["project"]["issue_count"] == 1
    assert result["project"]["node_count"] == 4
    assert result["issues"][0]["code"] == "missing_file"


def test_project_graph_uninitialized_error_keeps_stable_shape(tmp_path):
    result = query_project_graph(tmp_path)

    assert result["ok"] is False
    assert result["schema_version"] == 2
    assert result["project"]["status"] == "invalid"
    assert result["nodes"] == []
    assert result["derivations"] == []
    assert result["topological_order"] == []
    assert result["issues"][0]["code"] == "invalid_project"
