import json

import pytest

from kflow.cli import build_parser, main


def run_cli(capsys, *arguments):
    main([*arguments, "--json"])
    return json.loads(capsys.readouterr().out)


def test_default_cli_runs_official_workflow_without_domain_api(
    tmp_path, monkeypatch, capsys
):
    monkeypatch.chdir(tmp_path)
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "a.md").write_text("A", encoding="utf-8")
    (docs / "b.md").write_text("B", encoding="utf-8")

    assert run_cli(capsys, "init")["ok"] is True
    assert (
        run_cli(capsys, "add-node", "a", "--file", "docs/a.md")["node"]["name"] == "a"
    )
    assert (
        run_cli(capsys, "add-node", "b", "--file", "docs/b.md")["node"]["name"] == "b"
    )
    derived = run_cli(
        capsys,
        "derive",
        "--short",
        "由 A 形成 B",
        "--input",
        "a",
        "使用 A",
        "--output",
        "b",
        "形成 B",
    )
    assert derived["derivation"]["inputs"] == [
        {
            "node": next(
                item["node"]
                for item in derived["derivation"]["inputs"]
                if item["name"] == "a"
            ),
            "name": "a",
            "short": "使用 A",
            "detail": "",
        }
    ]
    assert derived["derivation"]["outputs"][0]["name"] == "b"
    assert derived["derivation"]["outputs"][0]["node"].startswith("nd_")

    run_cli(capsys, "confirm", "a")
    run_cli(capsys, "confirm", "b")
    (docs / "a.md").write_text("A changed", encoding="utf-8")

    status = run_cli(capsys, "status")
    by_name = {item["name"]: item for item in status["nodes"]}
    assert by_name["a"]["status"] == "affected"
    assert by_name["a"]["reasons"] == ["files_changed"]
    assert by_name["b"]["status"] == "affected"
    assert by_name["b"]["reasons"] == ["input_changed"]

    main(["status"])
    status_text = capsys.readouterr().out
    assert "State: attention required" in status_text
    assert "a [files_changed]" in status_text
    assert "b [input_changed]" in status_text
    assert "Why:" in status_text
    assert "kflow context --affected" in status_text

    context = run_cli(capsys, "context", "b")
    assert context["node"]["name"] == "b"
    assert [node["name"] for node in context["relations"]["upstream"]] == ["a"]

    explanation = run_cli(capsys, "explain", "a")
    affected = explanation["impact"]["affected_nodes"]
    assert affected[0]["name"] == "b"
    assert affected[0]["impact_reason"] == "input_changed"

    review_order = run_cli(capsys, "review-order")
    assert review_order["review_order"] == [
        by_name["a"]["id"],
        by_name["b"]["id"],
    ]

    main(["explain", "a"])
    explanation_text = capsys.readouterr().out
    assert "Direct impact:\nb" in explanation_text
    assert "Reason: input_changed via a -> b" in explanation_text

    main(["review-order"])
    assert "1. a\n2. b" in capsys.readouterr().out

    validation = run_cli(capsys, "validate")
    assert validation == {"ok": True, "schema_version": 2, "issues": []}

    (docs / "b.md").unlink()
    with pytest.raises(SystemExit) as exit_info:
        main(["validate", "--json"])
    assert exit_info.value.code == 2
    invalid = json.loads(capsys.readouterr().out)
    assert invalid["ok"] is False
    assert invalid["issues"][0]["code"] == "missing_file"


def test_cli_exposes_only_official_commands():
    parser = build_parser()
    command_parser = next(
        action for action in parser._actions if action.dest == "command"
    )

    assert tuple(command_parser.choices) == (
        "init",
        "add-node",
        "derive",
        "overview",
        "status",
        "scan",
        "confirm",
        "validate",
        "context",
        "explain",
        "review-order",
    )


def test_node_commands_accept_registered_file_paths_in_json_and_human_output(
    tmp_path, monkeypatch, capsys
):
    monkeypatch.chdir(tmp_path)
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "architecture.md").write_text("architecture", encoding="utf-8")

    run_cli(capsys, "init")
    node = run_cli(
        capsys,
        "add-node",
        "architecture",
        "--file",
        "docs/architecture.md",
    )["node"]

    context = run_cli(capsys, "context", "docs/architecture.md")
    explanation = run_cli(capsys, "explain", ".\\docs\\architecture.md")
    confirmation = run_cli(capsys, "confirm", "./docs/architecture.md")

    assert context["node"]["id"] == node["id"]
    assert explanation["node"]["id"] == node["id"]
    assert confirmation["node"] == node["id"]

    main(["context", "docs/architecture.md"])
    assert "Target Node:\narchitecture" in capsys.readouterr().out
    main(["explain", "docs/architecture.md"])
    assert "Cause:\narchitecture" in capsys.readouterr().out
    main(["confirm", "docs/architecture.md"])
    assert f"Confirmed Node {node['id']}" in capsys.readouterr().out


def test_overview_cli_matches_public_graph_and_shows_complete_derivation(
    tmp_path, monkeypatch, capsys
):
    monkeypatch.chdir(tmp_path)
    docs = tmp_path / "docs"
    docs.mkdir()
    for name in ("a", "b", "c"):
        (docs / f"{name}.md").write_text(f"PRIVATE {name}", encoding="utf-8")

    run_cli(capsys, "init")
    nodes = {
        name: run_cli(capsys, "add-node", name, "--file", f"docs/{name}.md")["node"]
        for name in ("a", "b", "c")
    }
    derived = run_cli(
        capsys,
        "derive",
        "--short",
        "合并 A 和 B",
        "--input",
        "docs/a.md",
        "使用 A",
        "--input",
        "b",
        "使用 B",
        "--output",
        "c",
        "形成 C",
    )["derivation"]

    overview = run_cli(capsys, "overview")

    assert overview["topological_order"] == [
        *sorted((nodes["a"]["id"], nodes["b"]["id"])),
        nodes["c"]["id"],
    ]
    assert overview["derivations"] == [derived]
    inputs_by_name = {item["name"]: item for item in derived["inputs"]}
    assert inputs_by_name["a"]["node"] == nodes["a"]["id"]
    assert "PRIVATE" not in json.dumps(overview, ensure_ascii=False)

    main(["overview"])
    text = capsys.readouterr().out
    assert "KFlow project overview" in text
    assert "Summary: 3 Nodes; 1 Derivations; 3 need review; 0 issues" in text
    assert text.index(f"a ({nodes['a']['id']})") < text.index(f"c ({nodes['c']['id']})")
    assert text.index(f"b ({nodes['b']['id']})") < text.index(f"c ({nodes['c']['id']})")
    assert "Inputs:" in text and "Outputs:" in text
    assert "kflow context --affected" in text


def test_derive_by_registered_path_returns_canonical_identity_in_human_output(
    tmp_path, monkeypatch, capsys
):
    monkeypatch.chdir(tmp_path)
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "a.md").write_text("A", encoding="utf-8")
    (docs / "b.md").write_text("B", encoding="utf-8")
    run_cli(capsys, "init")
    a = run_cli(capsys, "add-node", "a", "--file", "docs/a.md")["node"]
    b = run_cli(capsys, "add-node", "b", "--file", "docs/b.md")["node"]

    result = run_cli(
        capsys,
        "derive",
        "--short",
        "A 到 B",
        "--detail",
        "完整语义",
        "--input",
        "docs/a.md",
        "使用 A",
        "--output",
        "docs/b.md",
        "形成 B",
    )

    derivation = result["derivation"]
    assert derivation["detail"] == "完整语义"
    assert derivation["inputs"][0] == {
        "node": a["id"],
        "name": "a",
        "short": "使用 A",
        "detail": "",
    }
    assert derivation["outputs"][0]["node"] == b["id"]

    # A second project exercises human output without relying on the raw references.
    other = tmp_path / "other"
    other.mkdir()
    (other / "a.md").write_text("A", encoding="utf-8")
    (other / "b.md").write_text("B", encoding="utf-8")
    monkeypatch.chdir(other)
    run_cli(capsys, "init")
    run_cli(capsys, "add-node", "source", "--file", "a.md")
    run_cli(capsys, "add-node", "target", "--file", "b.md")
    main(
        [
            "derive",
            "--short",
            "source to target",
            "--input",
            "a.md",
            "source role",
            "--output",
            "b.md",
            "target role",
        ]
    )
    human = capsys.readouterr().out
    assert "source (nd_" in human
    assert "target (nd_" in human
    assert "Inputs: a.md" not in human
