import json

from kflow.core.graph import KnowledgeGraph
from kflow.core.models import (
    Derivation,
    DerivationInput,
    DerivationOutput,
    KnowledgeNode,
)
from kflow.core.storage import (
    initialize_project,
    load_confirmations,
    load_graph,
    save_confirmation,
    save_graph,
)
from kflow.core.versioning import (
    build_confirmation,
    compute_effective_versions,
    fingerprint_file,
    fingerprint_files,
)


def build_many_to_many_graph() -> KnowledgeGraph:
    nodes = tuple(
        KnowledgeNode(f"nd_{name}", name, (f"docs/{name}.md",))
        for name in ("a", "b", "c", "d")
    )
    derivation = Derivation(
        "dv_design",
        "design",
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
    return KnowledgeGraph.build(nodes, (derivation,))


def test_graph_and_confirmation_round_trip_preserves_semantics(tmp_path):
    graph = build_many_to_many_graph()
    for node in graph.nodes.values():
        path = tmp_path / node.files[0]
        path.parent.mkdir(exist_ok=True)
        path.write_bytes(node.id.encode("utf-8"))

    initialize_project(tmp_path)
    save_graph(tmp_path, graph)

    file_facts = {
        node.files[0]: fingerprint_file((tmp_path / node.files[0]).read_bytes())
        for node in graph.nodes.values()
    }
    aggregates = {
        node.id: fingerprint_files({path: file_facts[path] for path in node.files})
        for node in graph.nodes.values()
    }
    versions = compute_effective_versions(graph, aggregates)
    confirmation = build_confirmation(graph, "nd_c", file_facts, versions)
    save_confirmation(tmp_path, confirmation)

    restored = load_graph(tmp_path)
    restored_confirmation = load_confirmations(tmp_path)["nd_c"]

    assert restored.nodes == graph.nodes
    assert restored.derivations == graph.derivations
    assert restored.producer_of("nd_c").id == "dv_design"
    assert restored.sibling_outputs("nd_c") == ("nd_d",)
    assert restored.upstream("nd_d") == ("nd_a", "nd_b", "nd_d")
    assert restored.downstream("nd_a") == {"nd_a": 0, "nd_c": 1, "nd_d": 1}
    assert restored_confirmation == confirmation
    assert (
        restored_confirmation.files[0].fingerprint == confirmation.files[0].fingerprint
    )


def test_storage_uses_typed_records_and_stable_endpoint_order(tmp_path):
    initialize_project(tmp_path)
    save_graph(tmp_path, build_many_to_many_graph())

    node_data = json.loads((tmp_path / ".kflow/nodes/nd_a.json").read_text("utf-8"))
    derivation_data = json.loads(
        (tmp_path / ".kflow/derivations/dv_design.json").read_text("utf-8")
    )

    assert node_data["kind"] == "node"
    assert node_data["schema_version"] == 3
    assert derivation_data["kind"] == "derivation"
    assert derivation_data["name"] == "design"
    assert [item["node"] for item in derivation_data["inputs"]] == ["nd_a", "nd_b"]
    assert [item["node"] for item in derivation_data["outputs"]] == ["nd_c", "nd_d"]
    assert not tuple((tmp_path / ".kflow").rglob("*.tmp"))
