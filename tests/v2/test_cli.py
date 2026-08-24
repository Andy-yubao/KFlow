import json

from kflow.cli import main


def run_cli(capsys, *arguments):
    main(["v2", *arguments, "--json"])
    return json.loads(capsys.readouterr().out)


def test_v2_cli_runs_core_workflow_without_domain_api(tmp_path, monkeypatch, capsys):
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

    validation = run_cli(capsys, "validate")
    assert validation == {"ok": True, "schema_version": 2, "issues": []}

    (docs / "b.md").unlink()
    invalid = run_cli(capsys, "validate")
    assert invalid["ok"] is False
    assert invalid["issues"][0]["code"] == "missing_file"
