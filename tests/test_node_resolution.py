import pytest

from kflow.core.graph import KnowledgeGraph
from kflow.core.models import KnowledgeNode
from kflow.core.scan import resolve_node_id


@pytest.fixture
def graph() -> KnowledgeGraph:
    return KnowledgeGraph.build(
        (
            KnowledgeNode(
                "nd_architecture",
                "architecture",
                ("docs/architecture.md", "docs/architecture.svg"),
            ),
            KnowledgeNode("nd_other", "other", ("docs/other.md",)),
        ),
        (),
    )


@pytest.mark.parametrize(
    "reference",
    (
        "nd_architecture",
        "architecture",
        "docs/architecture.md",
        "docs/architecture.svg",
        "./docs/architecture.md",
        "docs\\architecture.md",
    ),
)
def test_resolver_accepts_exact_node_references(graph, reference):
    assert resolve_node_id(graph, reference) == "nd_architecture"


@pytest.mark.parametrize(
    "reference",
    (
        "docs/unmanaged.md",
        "architecture.md",
        "docs/architecture",
        "/docs/architecture.md",
        "C:/project/docs/architecture.md",
        "C:\\project\\docs\\architecture.md",
        "../docs/architecture.md",
        "docs/../docs/architecture.md",
        "./../docs/architecture.md",
    ),
)
def test_resolver_rejects_unregistered_similar_and_unsafe_paths(graph, reference):
    with pytest.raises(KeyError, match="unknown node"):
        resolve_node_id(graph, reference)
