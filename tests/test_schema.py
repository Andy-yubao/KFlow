from kflow.core.graph import KnowledgeGraph
from kflow.core.models import KnowledgeNode
from kflow.core.query import QUERY_SCHEMA_FIELDS, query_affected_context, query_context
from kflow.core.query import query_impact
from kflow.core.scan import confirm
from kflow.core.storage import initialize_project, save_graph, save_node


def prepare_project(tmp_path) -> None:
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs/node.md").write_text("PRIVATE", encoding="utf-8")
    initialize_project(tmp_path)
    save_graph(
        tmp_path,
        KnowledgeGraph.build(
            (KnowledgeNode("nd_node", "node", ("docs/node.md",)),), ()
        ),
    )
    confirm(tmp_path, "node")


def assert_stable_query_schema(result: dict) -> None:
    assert set(result) == QUERY_SCHEMA_FIELDS
    assert result["schema_version"] == 2
    assert set(result["relations"]) == {"upstream", "downstream", "derivations"}
    assert set(result["impact"]) == {"changed_nodes", "affected_nodes"}
    assert isinstance(result["reasons"], list)
    assert isinstance(result["review_order"], list)
    assert isinstance(result["issues"], list)


def test_context_and_explain_share_stable_top_level_schema(tmp_path):
    prepare_project(tmp_path)

    context = query_context(tmp_path, "node")
    explanation = query_impact(tmp_path, "node")

    assert_stable_query_schema(context)
    assert_stable_query_schema(explanation)
    assert context["ok"] is True
    assert explanation["ok"] is True


def test_project_context_has_stable_empty_result(tmp_path):
    prepare_project(tmp_path)
    (tmp_path / "docs/unrelated.md").write_text("PRIVATE", encoding="utf-8")
    save_node(
        tmp_path,
        KnowledgeNode("nd_unrelated", "unrelated", ("docs/unrelated.md",)),
    )

    result = query_affected_context(tmp_path)

    assert_stable_query_schema(result)
    assert result["node"] is None
    assert result["status"] == "confirmed"
    assert result["reasons"] == []
    assert result["impact"] == {"changed_nodes": [], "affected_nodes": []}
    assert result["review_order"] == []


def test_query_error_preserves_schema_and_machine_readable_issue(tmp_path):
    prepare_project(tmp_path)

    result = query_context(tmp_path, "missing")

    assert_stable_query_schema(result)
    assert result["ok"] is False
    assert result["node"] is None
    assert result["status"] == "error"
    assert result["issues"] == [
        {
            "code": "unknown_node",
            "message": "unknown node: missing",
            "references": ["missing"],
        }
    ]
