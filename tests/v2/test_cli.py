import json

import pytest

from kflow.cli import build_parser, main


def run_cli(capsys, *arguments):
    main([*arguments, "--json"])
    return json.loads(capsys.readouterr().out)


def test_default_cli_runs_v2_core_workflow_without_domain_api(
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
    assert derived["derivation"]["inputs"] == ["a"]
    assert derived["derivation"]["outputs"] == ["b"]

    run_cli(capsys, "confirm", "a")
    run_cli(capsys, "confirm", "b")
    (docs / "a.md").write_text("A changed", encoding="utf-8")

    status = run_cli(capsys, "status")
    by_name = {item["name"]: item for item in status["nodes"]}
    assert by_name["a"]["status"] == "affected"
    assert by_name["a"]["reasons"] == ["files_changed"]
    assert by_name["b"]["status"] == "affected"
    assert by_name["b"]["reasons"] == ["input_changed"]

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
    invalid = run_cli(capsys, "validate")
    assert invalid["ok"] is False
    assert invalid["issues"][0]["code"] == "missing_file"


def test_cli_does_not_expose_v2_command_group(capsys):
    parser = build_parser()

    with pytest.raises(SystemExit):
        parser.parse_args(["v2", "init"])

    assert (
        "{init,add-node,derive,status,scan,confirm,validate,context,explain,review-order,legacy}"
        in capsys.readouterr().err
    )
