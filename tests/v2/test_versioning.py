from kflow.v2.graph import KnowledgeGraph
from kflow.v2.models import (
    Derivation,
    DerivationInput,
    DerivationOutput,
    KnowledgeNode,
)
from kflow.v2.versioning import compute_effective_versions, fingerprint_derivation


def build_chain(detail: str = "根据 A 形成 B。") -> KnowledgeGraph:
    nodes = [
        KnowledgeNode("nd_a", "a", ("docs/a.md",)),
        KnowledgeNode("nd_b", "b", ("docs/b.md",)),
    ]
    derivations = [
        Derivation(
            "dv_source",
            "登记 A",
            "登记源知识 A。",
            (),
            (DerivationOutput("nd_a", "形成 A", "登记 A。"),),
        ),
        Derivation(
            "dv_ab",
            "形成 B",
            detail,
            (DerivationInput("nd_a", "使用 A", "以 A 作为依据。"),),
            (DerivationOutput("nd_b", "形成 B", "产出 B。"),),
        ),
    ]
    return KnowledgeGraph.build(nodes, derivations)


def test_upstream_file_change_propagates_to_downstream_effective_version():
    graph = build_chain()

    before = compute_effective_versions(graph, {"nd_a": "files-a1", "nd_b": "files-b1"})
    after = compute_effective_versions(graph, {"nd_a": "files-a2", "nd_b": "files-b1"})

    assert before["nd_a"] != after["nd_a"]
    assert before["nd_b"] != after["nd_b"]


def test_own_file_change_does_not_change_upstream_version():
    graph = build_chain()

    before = compute_effective_versions(graph, {"nd_a": "files-a1", "nd_b": "files-b1"})
    after = compute_effective_versions(graph, {"nd_a": "files-a1", "nd_b": "files-b2"})

    assert before["nd_a"] == after["nd_a"]
    assert before["nd_b"] != after["nd_b"]


def test_derivation_semantic_change_changes_its_output_version():
    before_graph = build_chain("根据 A 形成 B。")
    after_graph = build_chain("根据修订后的 A 重新形成 B。")
    files = {"nd_a": "files-a1", "nd_b": "files-b1"}

    before = compute_effective_versions(before_graph, files)
    after = compute_effective_versions(after_graph, files)

    assert before["nd_a"] == after["nd_a"]
    assert before["nd_b"] != after["nd_b"]


def test_derivation_fingerprint_is_independent_of_endpoint_order():
    first = Derivation(
        "dv_design",
        "形成设计",
        "根据 A 和 B 形成 C 和 D。",
        (
            DerivationInput("nd_a", "使用 A", "输入 A。"),
            DerivationInput("nd_b", "使用 B", "输入 B。"),
        ),
        (
            DerivationOutput("nd_c", "形成 C", "输出 C。"),
            DerivationOutput("nd_d", "形成 D", "输出 D。"),
        ),
    )
    reversed_endpoints = Derivation(
        first.id,
        first.short,
        first.detail,
        tuple(reversed(first.inputs)),
        tuple(reversed(first.outputs)),
    )

    assert fingerprint_derivation(first) == fingerprint_derivation(reversed_endpoints)
