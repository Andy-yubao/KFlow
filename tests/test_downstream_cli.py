"""CLI behavior of ``kflow confirm NODE --downstream``."""

import json
from importlib import import_module

import pytest

from kflow.cli import main
from kflow.core.graph import KnowledgeGraph
from kflow.core.models import (
    Derivation,
    DerivationInput,
    DerivationOutput,
    KnowledgeNode,
)
from kflow.core.scan import confirm
from kflow.core.schema_versions import DOWNSTREAM_CONFIRM_SCHEMA_VERSION
from kflow.core.storage import initialize_project, save_graph

scan_module = import_module("kflow.core.scan")


def prepare_chain(tmp_path) -> KnowledgeGraph:
    """a -> b -> c plus an unrelated x -> y branch."""
    identities = (
        ("nd_a", "a", "docs/a.md"),
        ("nd_b", "b", "docs/b.md"),
        ("nd_c", "c", "docs/c.md"),
        ("nd_x", "x", "docs/x.md"),
        ("nd_y", "y", "docs/y.md"),
    )
    nodes = tuple(
        KnowledgeNode(node_id, name, (path,)) for node_id, name, path in identities
    )
    derivations = (
        Derivation(
            "dv_ab",
            "a-to-b",
            "Derive b from a",
            "",
            (DerivationInput("nd_a", "input a", ""),),
            (DerivationOutput("nd_b", "output b", ""),),
        ),
        Derivation(
            "dv_bc",
            "b-to-c",
            "Derive c from b",
            "",
            (DerivationInput("nd_b", "input b", ""),),
            (DerivationOutput("nd_c", "output c", ""),),
        ),
        Derivation(
            "dv_xy",
            "x-to-y",
            "Derive y from x",
            "",
            (DerivationInput("nd_x", "input x", ""),),
            (DerivationOutput("nd_y", "output y", ""),),
        ),
    )
    graph = KnowledgeGraph.build(nodes, derivations)
    for node in nodes:
        path = tmp_path / node.files[0]
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(node.name, encoding="utf-8")
    initialize_project(tmp_path)
    save_graph(tmp_path, graph)
    for node_id in graph.topological_order():
        confirm(tmp_path, node_id)
    return graph


def run_json(capsys, *arguments):
    main([*arguments, "--json"])
    return json.loads(capsys.readouterr().out)


def run_json_error(capsys, *arguments):
    with pytest.raises(SystemExit) as exit_info:
        main([*arguments, "--json"])
    captured = capsys.readouterr()
    result = json.loads(captured.out)
    assert exit_info.value.code != 0
    assert captured.err == ""
    assert result["ok"] is False
    return result


def change_file(tmp_path, name: str, content: str) -> None:
    (tmp_path / "docs" / f"{name}.md").write_text(content, encoding="utf-8")


def test_confirm_downstream_text_confirms_the_reachable_review_debt(
    tmp_path, monkeypatch, capsys
) -> None:
    monkeypatch.chdir(tmp_path)
    prepare_chain(tmp_path)
    change_file(tmp_path, "a", "a changed")

    main(["confirm", "a", "--downstream"])
    text = capsys.readouterr().out

    assert text == (
        "Confirmed downstream from: a\n"
        "\n"
        "1. a\n"
        "2. b\n"
        "3. c\n"
        "\n"
        "3 nodes confirmed.\n"
        "Review scope is clear.\n"
    )
    assert "Confirmed: a" not in text  # downstream text, not single-node text


def test_confirm_downstream_skips_current_root_and_still_confirms_affected(
    tmp_path, monkeypatch, capsys
) -> None:
    monkeypatch.chdir(tmp_path)
    prepare_chain(tmp_path)
    change_file(tmp_path, "b", "b changed")

    main(["confirm", "a", "--downstream"])
    text = capsys.readouterr().out

    assert text == (
        "Confirmed downstream from: a\n"
        "\n"
        "1. b\n"
        "2. c\n"
        "\n"
        "2 nodes confirmed.\n"
        "Review scope is clear.\n"
    )


def test_confirm_downstream_with_no_review_debt_reports_nothing_to_do(
    tmp_path, monkeypatch, capsys
) -> None:
    monkeypatch.chdir(tmp_path)
    prepare_chain(tmp_path)

    main(["confirm", "a", "--downstream"])
    text = capsys.readouterr().out

    assert text == ("No nodes need confirmation from a.\nReview scope is clear.\n")


def test_confirm_downstream_json_reports_scope_confirmed_and_remaining(
    tmp_path, monkeypatch, capsys
) -> None:
    monkeypatch.chdir(tmp_path)
    prepare_chain(tmp_path)
    change_file(tmp_path, "a", "a changed")

    result = run_json(capsys, "confirm", "a", "--downstream")

    assert result["ok"] is True
    assert result["schema_version"] == DOWNSTREAM_CONFIRM_SCHEMA_VERSION
    assert result["scope"] == {"id": "nd_a", "name": "a", "files": ["docs/a.md"]}
    assert result["confirmed"] == [
        {"id": "nd_a", "name": "a", "files": ["docs/a.md"]},
        {"id": "nd_b", "name": "b", "files": ["docs/b.md"]},
        {"id": "nd_c", "name": "c", "files": ["docs/c.md"]},
    ]
    assert result["skipped_current"] == []
    assert result["remaining"] == []
    assert result["issues"] == []


def test_json_option_equivalent_before_and_after_downstream_command(
    tmp_path, monkeypatch, capsys
) -> None:
    first = tmp_path / "first"
    second = tmp_path / "second"
    first.mkdir()
    second.mkdir()
    prepare_chain(first)
    prepare_chain(second)
    change_file(first, "a", "a changed")
    change_file(second, "a", "a changed")

    monkeypatch.chdir(first)
    main(["confirm", "a", "--downstream", "--json"])
    trailing = capsys.readouterr().out
    monkeypatch.chdir(second)
    main(["--json", "confirm", "a", "--downstream"])
    leading = capsys.readouterr().out
    assert json.loads(trailing) == json.loads(leading)
    assert trailing == leading


def test_plain_confirm_text_is_unchanged_by_downstream_flag(
    tmp_path, monkeypatch, capsys
) -> None:
    monkeypatch.chdir(tmp_path)
    prepare_chain(tmp_path)
    change_file(tmp_path, "a", "a changed")

    main(["confirm", "a"])
    text = capsys.readouterr().out

    assert text == "Confirmed: a\nNext: b — input changed\n"


def test_confirm_downstream_never_affects_an_unrelated_branch(
    tmp_path, monkeypatch, capsys
) -> None:
    monkeypatch.chdir(tmp_path)
    prepare_chain(tmp_path)
    change_file(tmp_path, "a", "a changed")
    change_file(tmp_path, "x", "x changed")

    main(["confirm", "a", "--downstream"])
    text = capsys.readouterr().out

    assert text == (
        "Confirmed downstream from: a\n"
        "\n"
        "1. a\n"
        "2. b\n"
        "3. c\n"
        "\n"
        "3 nodes confirmed.\n"
        "Review scope is clear.\n"
    )
    assert "x" not in text


def test_confirm_downstream_json_failure_marks_already_confirmed_nodes(
    tmp_path, monkeypatch, capsys
) -> None:
    monkeypatch.chdir(tmp_path)
    prepare_chain(tmp_path)
    change_file(tmp_path, "a", "a changed")
    real_save = scan_module.save_confirmation

    def fail_on_b(root, confirmation):
        if confirmation.node == "nd_b":
            raise OSError("simulated write failure")
        return real_save(root, confirmation)

    monkeypatch.setattr(scan_module, "save_confirmation", fail_on_b)

    result = run_json_error(capsys, "confirm", "a", "--downstream")

    assert result["schema_version"] == DOWNSTREAM_CONFIRM_SCHEMA_VERSION
    assert result["scope"]["name"] == "a"
    assert result["confirmed"] == [{"id": "nd_a", "name": "a", "files": ["docs/a.md"]}]
    assert result["failed_node"]["name"] == "b"
    assert result["issues"][0]["code"] == "io_error"
    assert "cannot confirm node b" in result["issues"][0]["message"]


def test_confirm_downstream_partial_failure_is_explicit_in_text(
    tmp_path, monkeypatch, capsys
) -> None:
    monkeypatch.chdir(tmp_path)
    prepare_chain(tmp_path)
    change_file(tmp_path, "a", "a changed")
    real_save = scan_module.save_confirmation

    def fail_on_b(root, confirmation):
        if confirmation.node == "nd_b":
            raise OSError("simulated write failure")
        return real_save(root, confirmation)

    monkeypatch.setattr(scan_module, "save_confirmation", fail_on_b)

    with pytest.raises(SystemExit) as exit_info:
        main(["confirm", "a", "--downstream"])
    captured = capsys.readouterr()

    assert exit_info.value.code == 2
    assert captured.err == ""
    assert "Confirmed downstream from: a" in captured.out
    assert "Confirmed:\n1. a" in captured.out
    assert "Stopped at: b" in captured.out
    assert "simulated write failure" in captured.out


def test_confirm_downstream_unknown_node_uses_unknown_node_envelope(
    tmp_path, monkeypatch, capsys
) -> None:
    monkeypatch.chdir(tmp_path)
    prepare_chain(tmp_path)

    result = run_json_error(capsys, "confirm", "missing", "--downstream")

    assert result["issues"][0]["code"] == "unknown_node"
    assert result["schema_version"] == 3


def test_confirm_downstream_without_node_is_an_argument_error(
    tmp_path, monkeypatch, capsys
) -> None:
    monkeypatch.chdir(tmp_path)
    prepare_chain(tmp_path)

    result = run_json_error(capsys, "confirm", "--downstream")

    assert result["issues"][0]["code"] == "invalid_argument"
    assert result["schema_version"] == 3
