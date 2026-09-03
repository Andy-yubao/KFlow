import json
from typing import get_type_hints

from kflow.core.graph import KnowledgeGraph
from kflow.core.models import KnowledgeNode
from kflow.core.query import (
    ContextResult,
    ImpactResult,
    ReviewOrderResult,
    query_context,
    query_impact,
    query_review_order,
)
from kflow.core.scan import confirm
from kflow.core.storage import initialize_project, save_graph


def prepare_project(tmp_path) -> None:
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "architecture.md").write_text("PRIVATE", encoding="utf-8")
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


def test_public_queries_have_separate_typed_results() -> None:
    assert get_type_hints(query_context)["return"] is ContextResult
    assert get_type_hints(query_impact)["return"] is ImpactResult
    assert get_type_hints(query_review_order)["return"] is ReviewOrderResult


def test_query_versions_change_only_for_derivation_shapes(tmp_path) -> None:
    prepare_project(tmp_path)

    context = query_context(tmp_path, "architecture")
    impact = query_impact(tmp_path, "architecture")
    review = query_review_order(tmp_path)

    assert set(context) == {
        "ok",
        "schema_version",
        "node",
        "nodes",
        "producing_derivation",
        "consumer_derivations",
        "issues",
    }
    assert set(impact) == {
        "ok",
        "schema_version",
        "node",
        "direct_derivations",
        "direct_outputs",
        "further_downstream",
        "issues",
    }
    assert set(review) == {
        "ok",
        "schema_version",
        "scope",
        "nodes",
        "review_order",
        "issues",
    }
    assert context["schema_version"] == 4
    assert impact["schema_version"] == 4
    assert review["schema_version"] == 3
    assert "PRIVATE" not in json.dumps((context, impact, review))


def test_context_and_impact_accept_registered_paths(tmp_path) -> None:
    prepare_project(tmp_path)

    by_name = query_context(tmp_path, "architecture")
    by_path = query_context(tmp_path, ".\\docs\\architecture.md")
    impact = query_impact(tmp_path, "docs/architecture.svg")

    assert by_path["node"]["id"] == by_name["node"]["id"]
    assert impact["node"]["id"] == by_name["node"]["id"]


def test_query_errors_keep_their_command_shape(tmp_path) -> None:
    initialize_project(tmp_path)

    context = query_context(tmp_path, "missing")
    impact = query_impact(tmp_path, "missing")
    review = query_review_order(tmp_path, "missing")

    assert context["node"] is None and context["consumer_derivations"] == []
    assert impact["node"] is None and impact["direct_derivations"] == []
    assert review["scope"] is None and review["review_order"] == []
    for result, version in ((context, 4), (impact, 4), (review, 3)):
        assert result["ok"] is False
        assert result["schema_version"] == version
        assert result["issues"][0] == {
            "code": "unknown_node",
            "message": "unknown node: missing",
            "references": ["missing"],
        }
