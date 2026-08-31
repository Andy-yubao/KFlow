import json

import pytest

from kflow.cli import build_parser, main
from kflow.core.graph import KnowledgeGraph
from kflow.core.models import (
    Derivation,
    DerivationInput,
    DerivationOutput,
    KnowledgeNode,
)
from kflow.core.scan import confirm
from kflow.core.storage import initialize_project, save_graph


def run_json(capsys, *arguments):
    main([*arguments, "--json"])
    return json.loads(capsys.readouterr().out)


def prepare_cli_graph(tmp_path) -> KnowledgeGraph:
    identities = (
        ("nd_01", "requirements", "docs/requirements.md"),
        ("nd_02", "constraints", "docs/constraints.md"),
        ("nd_03", "architecture", "docs/architecture.md"),
        ("nd_04", "api-design", "docs/api.md"),
        ("nd_05", "test-plan", "docs/tests.md"),
        ("nd_06", "implementation", "src/service.py"),
        ("nd_07", "glossary", "docs/glossary.md"),
    )
    nodes = tuple(
        KnowledgeNode(node_id, name, (path,)) for node_id, name, path in identities
    )
    derivations = (
        Derivation(
            "dv_z_first",
            "Define system architecture",
            "",
            (
                DerivationInput("nd_01", "project requirements", ""),
                DerivationInput("nd_02", "design constraints", ""),
            ),
            (DerivationOutput("nd_03", "system architecture", ""),),
        ),
        Derivation(
            "dv_m_second",
            "Design interfaces and verification",
            "",
            (DerivationInput("nd_03", "system architecture", ""),),
            (
                DerivationOutput("nd_04", "API contract", ""),
                DerivationOutput("nd_05", "verification plan", ""),
            ),
        ),
        Derivation(
            "dv_a_third",
            "Implement the service",
            "",
            (DerivationInput("nd_04", "API contract", ""),),
            (DerivationOutput("nd_06", "service implementation", ""),),
        ),
    )
    graph = KnowledgeGraph.build(nodes, derivations)
    for node in nodes:
        path = tmp_path / node.files[0]
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(node.name, encoding="utf-8")
    initialize_project(tmp_path)
    save_graph(tmp_path, graph)
    return graph


def test_cli_exposes_only_the_final_public_commands() -> None:
    parser = build_parser()
    command_parser = next(
        action for action in parser._actions if action.dest == "command"
    )

    assert tuple(command_parser.choices) == (
        "init",
        "add-node",
        "derive",
        "overview",
        "context",
        "impact",
        "review-order",
        "confirm",
        "validate",
        "ui",
    )


def test_overview_uses_topological_derivations_without_ids_or_default_status(
    tmp_path, monkeypatch, capsys
) -> None:
    monkeypatch.chdir(tmp_path)
    prepare_cli_graph(tmp_path)

    main(["overview"])
    text = capsys.readouterr().out

    assert text.startswith("KFlow project: 7 nodes, 3 derivations")
    assert (
        text.index("Define system architecture")
        < text.index("Design interfaces and verification")
        < text.index("Implement the service")
    )
    assert "Standalone nodes\n\nglossary — docs/glossary.md" in text
    assert "Need review:" not in text
    assert "[unconfirmed]" not in text
    assert "nd_" not in text and "dv_" not in text


def test_overview_preserves_complete_many_to_many_derivation(
    tmp_path, monkeypatch, capsys
) -> None:
    monkeypatch.chdir(tmp_path)
    nodes = tuple(
        KnowledgeNode(f"nd_{name}", name, (f"docs/{name}.md",))
        for name in ("a", "b", "c", "d")
    )
    derivation = Derivation(
        "dv_many",
        "Combine inputs",
        "",
        (
            DerivationInput("nd_a", "input a", ""),
            DerivationInput("nd_b", "input b", ""),
        ),
        (
            DerivationOutput("nd_c", "output c", ""),
            DerivationOutput("nd_d", "output d", ""),
        ),
    )
    for node in nodes:
        path = tmp_path / node.files[0]
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(node.name, encoding="utf-8")
    initialize_project(tmp_path)
    save_graph(tmp_path, KnowledgeGraph.build(nodes, (derivation,)))

    main(["overview"])

    assert capsys.readouterr().out == (
        "KFlow project: 4 nodes, 1 derivations\n"
        "\n"
        "a — docs/a.md\n"
        "b — docs/b.md\n"
        "  └─ Combine inputs\n"
        "     ├─→ c — docs/c.md\n"
        "     └─→ d — docs/d.md\n"
    )


def test_overview_status_marks_only_nodes_needing_review(
    tmp_path, monkeypatch, capsys
) -> None:
    monkeypatch.chdir(tmp_path)
    graph = prepare_cli_graph(tmp_path)
    for node_id in graph.topological_order():
        confirm(tmp_path, node_id)
    (tmp_path / "docs/requirements.md").write_text("changed", encoding="utf-8")

    main(["overview", "--status"])
    text = capsys.readouterr().out

    assert "Need review: 5 nodes" in text
    assert "requirements [files changed] — docs/requirements.md" in text
    assert "constraints — docs/constraints.md" in text
    assert "architecture [input changed] — docs/architecture.md" in text


def test_context_impact_and_review_order_have_distinct_human_outputs(
    tmp_path, monkeypatch, capsys
) -> None:
    monkeypatch.chdir(tmp_path)
    graph = prepare_cli_graph(tmp_path)
    for node_id in graph.topological_order():
        confirm(tmp_path, node_id)
    (tmp_path / "docs/requirements.md").write_text("changed", encoding="utf-8")

    main(["context", "architecture"])
    context = capsys.readouterr().out
    assert context.startswith("architecture [input changed]")
    assert "Produced by:" in context and "Used by:" in context
    assert "project requirements" in context and "design constraints" in context
    assert "implementation" not in context
    assert "Recommended review order" not in context

    main(["impact", "requirements"])
    impact = capsys.readouterr().out
    assert impact.startswith("Impact from: requirements")
    assert "requirements — project requirements [selected]" in impact
    assert "constraints — design constraints" in impact
    assert "Further downstream, in topological order" in impact
    assert "1. api-design\n2. test-plan\n3. implementation" in impact
    assert "docs/" not in impact

    main(["review-order"])
    review = capsys.readouterr().out
    assert review.startswith("Review order")
    assert "1. requirements — files changed\n   docs/requirements.md" in review
    assert "constraints" not in review
    assert "Derivation" not in review


def test_confirm_names_the_next_formal_review_item(
    tmp_path, monkeypatch, capsys
) -> None:
    monkeypatch.chdir(tmp_path)
    graph = prepare_cli_graph(tmp_path)
    for node_id in graph.topological_order():
        confirm(tmp_path, node_id)
    (tmp_path / "docs/requirements.md").write_text("changed", encoding="utf-8")

    main(["confirm", "requirements"])
    text = capsys.readouterr().out

    assert text == "Confirmed: requirements\nNext: architecture — input changed\n"


def test_json_option_is_equivalent_before_and_after_query_command(
    tmp_path, monkeypatch, capsys
) -> None:
    monkeypatch.chdir(tmp_path)
    prepare_cli_graph(tmp_path)

    for command in (
        ("overview",),
        ("context", "architecture"),
        ("impact", "requirements"),
        ("review-order", "architecture"),
    ):
        main([*command, "--json"])
        trailing = capsys.readouterr().out
        main(["--json", *command])
        leading = capsys.readouterr().out
        assert json.loads(trailing) == json.loads(leading)
        assert trailing == leading


def test_validate_prints_only_real_issues(tmp_path, monkeypatch, capsys) -> None:
    monkeypatch.chdir(tmp_path)
    graph = prepare_cli_graph(tmp_path)

    main(["validate"])
    assert capsys.readouterr().out == "KFlow metadata is valid.\n"

    missing = tmp_path / graph.nodes["nd_03"].files[0]
    missing.unlink()
    with pytest.raises(SystemExit) as exit_info:
        main(["validate"])
    captured = capsys.readouterr()

    assert exit_info.value.code == 2
    assert captured.err == ""
    assert captured.out == (
        "KFlow metadata is invalid.\n\n- missing_file: docs/architecture.md\n"
    )

    with pytest.raises(SystemExit):
        main(["overview", "--status"])
    overview = capsys.readouterr()
    assert overview.err == ""
    assert "Project status: invalid" in overview.out
    assert (
        "Review status unavailable until validation issues are resolved."
        in overview.out
    )
    assert "Need review: 0 nodes" not in overview.out
    assert "Validation issues\n\n- missing_file: docs/architecture.md" in overview.out
