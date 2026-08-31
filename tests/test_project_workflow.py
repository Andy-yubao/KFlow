import json

from kflow.cli import main


def run_json(capsys, *arguments):
    main([*arguments, "--json"])
    return json.loads(capsys.readouterr().out)


def test_real_cli_workflow_needs_no_scan_step(tmp_path, monkeypatch, capsys) -> None:
    monkeypatch.chdir(tmp_path)
    docs = tmp_path / "docs"
    docs.mkdir()
    for name in ("requirements", "architecture", "implementation", "tests"):
        (docs / f"{name}.md").write_text(name, encoding="utf-8")

    run_json(capsys, "init")
    for name in ("requirements", "architecture", "implementation", "tests"):
        run_json(capsys, "add-node", name, "--file", f"docs/{name}.md")
    run_json(
        capsys,
        "derive",
        "--short",
        "requirements produce architecture",
        "--input",
        "requirements",
        "requirements role",
        "--output",
        "architecture",
        "architecture role",
    )
    run_json(
        capsys,
        "derive",
        "--short",
        "architecture produces implementation and tests",
        "--input",
        "architecture",
        "architecture role",
        "--output",
        "implementation",
        "implementation role",
        "--output",
        "tests",
        "tests role",
    )
    for name in ("requirements", "architecture", "implementation", "tests"):
        run_json(capsys, "confirm", name)

    (docs / "architecture.md").write_text("changed", encoding="utf-8")

    overview = run_json(capsys, "overview", "--status")
    context = run_json(capsys, "context", "architecture")
    impact = run_json(capsys, "impact", "architecture")
    review = run_json(capsys, "review-order")

    by_name = {item["name"]: item for item in overview["nodes"]}
    by_id = {item["id"]: item for item in overview["nodes"]}
    assert by_name["architecture"]["reasons"] == ["files_changed"]
    assert context["node"]["reasons"] == ["files_changed"]
    output_names = {"implementation", "tests"}
    expected_outputs = [
        by_id[node_id]["name"]
        for node_id in overview["topological_order"]
        if by_id[node_id]["name"] in output_names
    ]
    assert [item["name"] for item in impact["direct_outputs"]] == expected_outputs
    assert [item["id"] for item in review["nodes"]] == [
        node_id
        for node_id in overview["topological_order"]
        if by_id[node_id]["reasons"]
    ]

    for name in ("architecture", "implementation", "tests"):
        run_json(capsys, "confirm", name)
    assert run_json(capsys, "review-order")["review_order"] == []
