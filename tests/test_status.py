from kflow.core.graph import KnowledgeGraph
from kflow.core.models import (
    Derivation,
    DerivationInput,
    DerivationOutput,
    KnowledgeNode,
)
from kflow.core.scan import confirm, scan
from kflow.core.storage import initialize_project, save_graph


def build_chain() -> KnowledgeGraph:
    nodes = tuple(
        KnowledgeNode(f"nd_{name}", name, (f"docs/{name}.md",))
        for name in ("a", "b", "c")
    )
    derivations = (
        Derivation(
            "dv_ab",
            "a-to-b",
            "形成 B",
            "",
            (DerivationInput("nd_a", "使用 A", ""),),
            (DerivationOutput("nd_b", "形成 B", ""),),
        ),
        Derivation(
            "dv_bc",
            "b-to-c",
            "形成 C",
            "",
            (DerivationInput("nd_b", "使用 B", ""),),
            (DerivationOutput("nd_c", "形成 C", ""),),
        ),
    )
    return KnowledgeGraph.build(nodes, derivations)


def prepare_project(tmp_path) -> KnowledgeGraph:
    graph = build_chain()
    for node in graph.nodes.values():
        path = tmp_path / node.files[0]
        path.parent.mkdir(exist_ok=True)
        path.write_text(node.name, encoding="utf-8")
    initialize_project(tmp_path)
    save_graph(tmp_path, graph)
    return graph


def test_source_change_affects_downstream_and_confirmation_does_not_cascade(tmp_path):
    prepare_project(tmp_path)
    for node_id in ("nd_a", "nd_b", "nd_c"):
        confirm(tmp_path, node_id)

    before = scan(tmp_path)
    (tmp_path / "docs/a.md").write_text("a changed", encoding="utf-8")
    changed = scan(tmp_path)

    assert changed.statuses["nd_a"].reasons == ("files_changed",)
    assert changed.statuses["nd_b"].reasons == ("input_changed",)
    assert changed.statuses["nd_c"].reasons == ("input_changed",)
    assert changed.statuses["nd_a"].status == "affected"

    confirm(tmp_path, "nd_b")
    after = scan(tmp_path)

    assert after.statuses["nd_b"].status == "confirmed"
    assert after.statuses["nd_b"].reasons == ()
    assert after.statuses["nd_c"].status == "affected"
    assert after.statuses["nd_c"].reasons == ("input_changed",)
    assert before.effective_versions != changed.effective_versions
    assert changed.effective_versions == after.effective_versions


def test_unconfirmed_nodes_remain_explicit_while_coarse_status_is_valid(tmp_path):
    prepare_project(tmp_path)

    result = scan(tmp_path)

    assert result.statuses["nd_a"].status == "valid"
    assert result.statuses["nd_a"].reasons == ("unconfirmed",)
    assert result.statuses["nd_a"].needs_review is True
