from typing import get_type_hints

from kflow.core.query import (
    QUERY_SCHEMA_FIELDS,
    QueryResult,
    query_affected_context,
    query_context,
    query_impact,
)
from kflow.core.graph import KnowledgeGraph
from kflow.core.models import KnowledgeNode
from kflow.core.scan import confirm
from kflow.core.storage import initialize_project, save_graph


PUBLIC_QUERY_FUNCTIONS = (
    query_context,
    query_impact,
    query_affected_context,
)


def assert_query_contract(result: QueryResult) -> None:
    assert set(result) == QUERY_SCHEMA_FIELDS
    assert result["schema_version"] == 2
    assert set(result["relations"]) == {
        "upstream",
        "downstream",
        "derivations",
    }
    assert set(result["impact"]) == {"changed_nodes", "affected_nodes"}
    assert isinstance(result["reasons"], list)
    assert isinstance(result["review_order"], list)
    assert isinstance(result["issues"], list)


def test_public_query_functions_declare_one_stable_result_type() -> None:
    assert QUERY_SCHEMA_FIELDS == {
        "ok",
        "schema_version",
        "node",
        "status",
        "reasons",
        "relations",
        "impact",
        "review_order",
        "issues",
    }
    for function in PUBLIC_QUERY_FUNCTIONS:
        assert get_type_hints(function)["return"] is QueryResult


def test_initialized_empty_project_has_stable_success_results(tmp_path) -> None:
    initialize_project(tmp_path)

    affected = query_affected_context(tmp_path)
    impact = query_impact(tmp_path)

    for result in (affected, impact):
        assert_query_contract(result)
        assert result == {
            "ok": True,
            "schema_version": 2,
            "node": None,
            "status": "confirmed",
            "reasons": [],
            "relations": {
                "upstream": [],
                "downstream": [],
                "derivations": [],
            },
            "impact": {"changed_nodes": [], "affected_nodes": []},
            "review_order": [],
            "issues": [],
        }


def test_unknown_node_error_preserves_the_public_contract(tmp_path) -> None:
    initialize_project(tmp_path)

    for function in (query_context, query_impact):
        result = function(tmp_path, "missing")

        assert_query_contract(result)
        assert result["ok"] is False
        assert result["status"] == "error"
        assert result["issues"] == [
            {
                "code": "unknown_node",
                "message": "unknown node: missing",
                "references": ["missing"],
            }
        ]


def test_context_and_impact_accept_registered_file_path_without_returning_content(
    tmp_path,
) -> None:
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "architecture.md").write_text("PRIVATE CONTENT", encoding="utf-8")
    (docs / "architecture.svg").write_text("PRIVATE SVG", encoding="utf-8")
    initialize_project(tmp_path)
    save_graph(
        tmp_path,
        KnowledgeGraph.build(
            (
                KnowledgeNode(
                    "nd_architecture",
                    "architecture",
                    ("docs/architecture.md", "docs/architecture.svg"),
                ),
            ),
            (),
        ),
    )
    confirm(tmp_path, "architecture")

    by_name = query_context(tmp_path, "architecture")
    by_path = query_context(tmp_path, "docs/architecture.md")
    impact = query_impact(tmp_path, "docs/architecture.svg")

    for result in (by_path, impact):
        assert_query_contract(result)
        assert result["node"]["id"] == by_name["node"]["id"]
        assert "PRIVATE" not in str(result)

    for reference in (
        "docs/unmanaged.md",
        "C:/project/docs/architecture.md",
        "../docs/architecture.md",
    ):
        unresolved = query_context(tmp_path, reference)
        assert_query_contract(unresolved)
        assert unresolved["issues"][0]["code"] == "unknown_node"


def test_uninitialized_project_error_is_stable_for_every_query(tmp_path) -> None:
    calls = (
        lambda: query_context(tmp_path, "missing"),
        lambda: query_impact(tmp_path, "missing"),
        lambda: query_affected_context(tmp_path),
    )

    for call in calls:
        result = call()

        assert_query_contract(result)
        assert result["ok"] is False
        assert result["status"] == "error"
        assert result["issues"][0]["code"] == "invalid_project"
        assert result["impact"] == {"changed_nodes": [], "affected_nodes": []}
        assert result["review_order"] == []
