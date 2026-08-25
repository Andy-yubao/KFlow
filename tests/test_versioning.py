import pytest

from kflow.core.graph import KnowledgeGraph
from kflow.core.models import (
    Derivation,
    DerivationInput,
    DerivationOutput,
    KnowledgeNode,
)
from kflow.core.versioning import (
    build_confirmation,
    compute_effective_versions,
    fingerprint_derivation,
    fingerprint_file,
    fingerprint_files,
)


def build_chain(detail: str = "根据 A 形成 B。") -> KnowledgeGraph:
    nodes = [
        KnowledgeNode("nd_a", "a", ("docs/a.md",)),
        KnowledgeNode("nd_b", "b", ("docs/b.md",)),
    ]
    derivations = [
        Derivation(
            "dv_ab",
            "形成 B",
            detail,
            (DerivationInput("nd_a", "使用 A", ""),),
            (DerivationOutput("nd_b", "形成 B", ""),),
        ),
    ]
    return KnowledgeGraph.build(nodes, derivations)


def files_fingerprints(a: bytes = b"a1", b: bytes = b"b1"):
    return {
        "nd_a": fingerprint_files({"docs/a.md": fingerprint_file(a)}),
        "nd_b": fingerprint_files({"docs/b.md": fingerprint_file(b)}),
    }


def test_source_and_derived_nodes_use_distinct_effective_version_formulas():
    graph = build_chain()
    versions = compute_effective_versions(graph, files_fingerprints())

    source_only = KnowledgeGraph.build([graph.nodes["nd_b"]], [])
    source_b = compute_effective_versions(
        source_only, {"nd_b": files_fingerprints()["nd_b"]}
    )

    assert versions["nd_a"] != versions["nd_b"]
    assert versions["nd_b"] != source_b["nd_b"]


def test_upstream_file_change_propagates_to_downstream_effective_version():
    graph = build_chain()

    before = compute_effective_versions(graph, files_fingerprints(a=b"a1"))
    after = compute_effective_versions(graph, files_fingerprints(a=b"a2"))

    assert before["nd_a"] != after["nd_a"]
    assert before["nd_b"] != after["nd_b"]


def test_own_file_change_does_not_change_upstream_version():
    graph = build_chain()

    before = compute_effective_versions(graph, files_fingerprints(b=b"b1"))
    after = compute_effective_versions(graph, files_fingerprints(b=b"b2"))

    assert before["nd_a"] == after["nd_a"]
    assert before["nd_b"] != after["nd_b"]


def test_derivation_semantic_change_changes_its_output_version():
    before_graph = build_chain("根据 A 形成 B。")
    after_graph = build_chain("根据修订后的 A 重新形成 B。")
    files = files_fingerprints()

    before = compute_effective_versions(before_graph, files)
    after = compute_effective_versions(after_graph, files)

    assert before["nd_a"] == after["nd_a"]
    assert before["nd_b"] != after["nd_b"]


def test_derivation_fingerprint_is_independent_of_endpoint_order():
    first = Derivation(
        "dv_design",
        "形成设计",
        "",
        (
            DerivationInput("nd_a", "使用 A", ""),
            DerivationInput("nd_b", "使用 B", ""),
        ),
        (
            DerivationOutput("nd_c", "形成 C", ""),
            DerivationOutput("nd_d", "形成 D", ""),
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


def test_files_fingerprint_is_order_independent_but_path_sensitive():
    a = fingerprint_file(b"a")
    b = fingerprint_file(b"b")

    first = fingerprint_files({"docs/a.md": a, "docs/b.md": b})
    reordered = fingerprint_files({"docs/b.md": b, "docs/a.md": a})
    renamed = fingerprint_files({"docs/a.md": a, "docs/c.md": b})

    assert first == reordered
    assert first != renamed


def test_files_fingerprint_rejects_non_repository_paths():
    with pytest.raises(ValueError):
        fingerprint_files({"../outside.md": fingerprint_file(b"outside")})


def test_many_to_many_input_and_derivation_changes_reach_every_output():
    nodes = [
        KnowledgeNode(node_id, node_id, (f"docs/{node_id}.md",))
        for node_id in ("nd_a", "nd_b", "nd_c", "nd_d")
    ]

    def graph(detail):
        return KnowledgeGraph.build(
            nodes,
            [
                Derivation(
                    "dv_design",
                    "形成 C 和 D",
                    detail,
                    (
                        DerivationInput("nd_a", "使用 A", ""),
                        DerivationInput("nd_b", "使用 B", ""),
                    ),
                    (
                        DerivationOutput("nd_c", "形成 C", ""),
                        DerivationOutput("nd_d", "形成 D", ""),
                    ),
                )
            ],
        )

    baseline_files = {
        node.id: fingerprint_files(
            {node.files[0]: fingerprint_file(node.id.encode("utf-8"))}
        )
        for node in nodes
    }
    changed_input_files = dict(baseline_files)
    changed_input_files["nd_a"] = fingerprint_files(
        {"docs/nd_a.md": fingerprint_file(b"changed A")}
    )

    baseline = compute_effective_versions(graph("原始推导"), baseline_files)
    input_changed = compute_effective_versions(graph("原始推导"), changed_input_files)
    derivation_changed = compute_effective_versions(graph("修订推导"), baseline_files)

    assert input_changed["nd_c"] != baseline["nd_c"]
    assert input_changed["nd_d"] != baseline["nd_d"]
    assert derivation_changed["nd_c"] != baseline["nd_c"]
    assert derivation_changed["nd_d"] != baseline["nd_d"]


def test_build_confirmation_is_single_node_and_does_not_change_versions_or_sibling():
    nodes = [
        KnowledgeNode("nd_a", "a", ("docs/a.md",)),
        KnowledgeNode("nd_c", "c", ("docs/c.md",)),
        KnowledgeNode("nd_d", "d", ("docs/d.md",)),
    ]
    derivation = Derivation(
        "dv_outputs",
        "形成 C 和 D",
        "",
        (DerivationInput("nd_a", "使用 A", ""),),
        (
            DerivationOutput("nd_c", "形成 C", ""),
            DerivationOutput("nd_d", "形成 D", ""),
        ),
    )
    graph = KnowledgeGraph.build(nodes, [derivation])
    file_facts = {
        "docs/a.md": fingerprint_file(b"a"),
        "docs/c.md": fingerprint_file(b"c"),
        "docs/d.md": fingerprint_file(b"d"),
    }
    aggregate = {
        node.id: fingerprint_files({path: file_facts[path] for path in node.files})
        for node in nodes
    }
    versions_before = compute_effective_versions(graph, aggregate)

    confirmation_c = build_confirmation(graph, "nd_c", file_facts, versions_before)
    versions_after = compute_effective_versions(graph, aggregate)

    assert confirmation_c.node == "nd_c"
    assert tuple(item.node for item in confirmation_c.inputs) == ("nd_a",)
    assert confirmation_c.producing_derivation.id == "dv_outputs"
    assert versions_after == versions_before
    assert graph.sibling_outputs(confirmation_c.node) == ("nd_d",)
