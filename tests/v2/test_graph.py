import pytest

from kflow.v2.graph import GraphValidationError, KnowledgeGraph
from kflow.v2.models import (
    Derivation,
    DerivationInput,
    DerivationOutput,
    KnowledgeNode,
)


def node(
    node_id: str, name: str | None = None, file: str | None = None
) -> KnowledgeNode:
    suffix = node_id.removeprefix("nd_")
    return KnowledgeNode(
        id=node_id,
        name=name or suffix,
        files=(file or f"docs/{suffix}.md",),
    )


def derive(
    derivation_id: str, inputs: tuple[str, ...], outputs: tuple[str, ...]
) -> Derivation:
    return Derivation(
        id=derivation_id,
        short="形成下游知识",
        detail="",
        inputs=tuple(
            DerivationInput(node_id, f"使用 {node_id}", "") for node_id in inputs
        ),
        outputs=tuple(
            DerivationOutput(node_id, f"形成 {node_id}", "") for node_id in outputs
        ),
    )


def issue_codes(error: GraphValidationError) -> set[str]:
    return {issue.code for issue in error.issues}


def test_graph_supports_source_nodes_and_many_to_many_derivations():
    nodes = [node("nd_a"), node("nd_b"), node("nd_c"), node("nd_d")]
    graph = KnowledgeGraph.build(
        nodes,
        [derive("dv_design", ("nd_a", "nd_b"), ("nd_c", "nd_d"))],
    )

    assert graph.producer_of("nd_a") is None
    assert graph.producer_of("nd_d").id == "dv_design"
    assert graph.sibling_outputs("nd_a") == ()
    assert graph.sibling_outputs("nd_c") == ("nd_d",)
    assert graph.downstream("nd_a") == {"nd_a": 0, "nd_c": 1, "nd_d": 1}
    assert graph.upstream("nd_d") == ("nd_a", "nd_b", "nd_d")


def test_graph_allows_orphan_nodes_but_rejects_multiple_producers():
    orphan = node("nd_orphan")
    graph = KnowledgeGraph.build([orphan], [])
    assert graph.producer_of("nd_orphan") is None

    nodes = [node("nd_a"), node("nd_b"), node("nd_shared")]
    with pytest.raises(GraphValidationError) as exc:
        KnowledgeGraph.build(
            nodes,
            [
                derive("dv_one", ("nd_a",), ("nd_shared",)),
                derive("dv_two", ("nd_b",), ("nd_shared",)),
            ],
        )
    assert "multiple_producers" in issue_codes(exc.value)


def test_graph_requires_unique_names_and_file_ownership():
    nodes = [
        node("nd_a", name="same", file="docs/shared.md"),
        node("nd_b", name="same", file="docs/shared.md"),
    ]

    with pytest.raises(GraphValidationError) as exc:
        KnowledgeGraph.build(nodes, [])

    codes = issue_codes(exc.value)
    assert "duplicate_node_name" in codes
    assert "duplicate_file_owner" in codes


def test_graph_rejects_missing_references():
    a = node("nd_a")
    bad = derive("dv_bad", ("nd_missing",), ("nd_a",))

    with pytest.raises(GraphValidationError) as exc:
        KnowledgeGraph.build([a], [bad])

    assert "missing_input_node" in issue_codes(exc.value)


def test_graph_rejects_cycles():
    nodes = [node("nd_a"), node("nd_b")]
    derivations = [
        derive("dv_ab", ("nd_a",), ("nd_b",)),
        derive("dv_ba", ("nd_b",), ("nd_a",)),
    ]

    with pytest.raises(GraphValidationError) as exc:
        KnowledgeGraph.build(nodes, derivations)

    assert "cycle" in issue_codes(exc.value)


def test_topological_order_is_stable_for_sources_and_sibling_outputs():
    nodes = [node("nd_d"), node("nd_c"), node("nd_b"), node("nd_a")]
    graph = KnowledgeGraph.build(
        nodes,
        [derive("dv_design", ("nd_a", "nd_b"), ("nd_c", "nd_d"))],
    )

    assert graph.topological_order() == ("nd_a", "nd_b", "nd_c", "nd_d")


def test_graph_queries_reject_unknown_nodes():
    graph = KnowledgeGraph.build([node("nd_a")], [])

    with pytest.raises(KeyError, match="unknown node"):
        graph.producer_of("nd_missing")
    with pytest.raises(KeyError, match="unknown node"):
        graph.consumer_derivations("nd_missing")
