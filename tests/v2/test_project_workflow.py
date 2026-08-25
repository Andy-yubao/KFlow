import json

from kflow.cli import main


def run_json(capsys, *arguments):
    main([*arguments, "--json"])
    return json.loads(capsys.readouterr().out)


def test_real_project_scan_context_and_confirm_workflow(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    docs = tmp_path / "docs"
    docs.mkdir()
    for name in ("requirements", "architecture", "implementation", "tests"):
        (docs / f"{name}.md").write_text(f"PRIVATE {name}", encoding="utf-8")

    run_json(capsys, "init")
    nodes = {
        name: run_json(capsys, "add-node", name, "--file", f"docs/{name}.md")["node"]
        for name in ("requirements", "architecture", "implementation", "tests")
    }
    run_json(
        capsys,
        "derive",
        "--short",
        "requirements produce architecture",
        "--input",
        "requirements",
        "provides requirements",
        "--output",
        "architecture",
        "forms architecture",
    )
    run_json(
        capsys,
        "derive",
        "--short",
        "architecture produces implementation and tests",
        "--input",
        "architecture",
        "provides architecture",
        "--output",
        "implementation",
        "forms implementation",
        "--output",
        "tests",
        "forms tests",
    )
    for name in nodes:
        run_json(capsys, "confirm", name)

    (docs / "architecture.md").write_text(
        "PRIVATE architecture changed", encoding="utf-8"
    )

    scanned = run_json(capsys, "scan")
    explanation = run_json(capsys, "explain", "architecture")
    project = run_json(capsys, "context", "--affected")

    assert scanned["changes"] == {
        "added": [],
        "modified": ["docs/architecture.md"],
        "deleted": [],
    }
    assert {item["name"] for item in explanation["impact"]["affected_nodes"]} == {
        "implementation",
        "tests",
    }
    assert project["review_order"] == [
        nodes["architecture"]["id"],
        *sorted((nodes["implementation"]["id"], nodes["tests"]["id"])),
    ]
    assert "PRIVATE" not in json.dumps(project)

    run_json(capsys, "confirm", "architecture")
    remaining = run_json(capsys, "context", "--affected")
    assert remaining["review_order"] == sorted(
        (nodes["implementation"]["id"], nodes["tests"]["id"])
    )

    for name in ("implementation", "tests"):
        run_json(capsys, "confirm", name)
    closed = run_json(capsys, "context", "--affected")

    assert closed["status"] == "confirmed"
    assert closed["review_order"] == []
    assert closed["impact"] == {"changed_nodes": [], "affected_nodes": []}
