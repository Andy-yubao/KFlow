import json

from kflow.cli import main


def run_json(capsys, *arguments):
    main([*arguments, "--json"])
    return json.loads(capsys.readouterr().out)


def test_agent_workflow_uses_stable_context_to_close_review_loop(
    tmp_path, monkeypatch, capsys
):
    monkeypatch.chdir(tmp_path)
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "architecture.md").write_text(
        "PRIVATE ARCHITECTURE CONTENT", encoding="utf-8"
    )
    (docs / "implementation.md").write_text(
        "PRIVATE IMPLEMENTATION CONTENT", encoding="utf-8"
    )
    (docs / "tests.md").write_text("PRIVATE TEST CONTENT", encoding="utf-8")

    assert run_json(capsys, "init")["ok"] is True
    architecture = run_json(
        capsys,
        "add-node",
        "architecture",
        "--file",
        "docs/architecture.md",
    )["node"]
    implementation = run_json(
        capsys,
        "add-node",
        "implementation",
        "--file",
        "docs/implementation.md",
    )["node"]
    tests = run_json(
        capsys,
        "add-node",
        "tests",
        "--file",
        "docs/tests.md",
    )["node"]
    run_json(
        capsys,
        "derive",
        "--short",
        "由架构形成实现",
        "--input",
        "architecture",
        "提供架构",
        "--output",
        "implementation",
        "形成实现",
    )
    run_json(
        capsys,
        "derive",
        "--short",
        "由实现形成测试",
        "--input",
        "implementation",
        "提供实现",
        "--output",
        "tests",
        "形成测试",
    )
    for name in ("architecture", "implementation", "tests"):
        run_json(capsys, "confirm", name)

    (docs / "architecture.md").write_text(
        "PRIVATE ARCHITECTURE CONTENT CHANGED", encoding="utf-8"
    )

    status = run_json(capsys, "status")
    by_name = {item["name"]: item for item in status["nodes"]}
    assert by_name["architecture"]["reasons"] == ["files_changed"]
    assert by_name["implementation"]["reasons"] == ["input_changed"]
    assert by_name["tests"]["reasons"] == ["input_changed"]

    context = run_json(capsys, "context", "architecture")
    repeated_context = run_json(capsys, "context", "architecture")
    assert context == repeated_context
    assert set(context) == {
        "ok",
        "schema_version",
        "node",
        "upstream",
        "downstream",
        "derivations",
        "review_order",
        "issues",
    }
    assert context["node"] == {
        "id": architecture["id"],
        "name": "architecture",
        "files": ["docs/architecture.md"],
        "status": "affected",
        "reasons": ["files_changed"],
        "changed_files": ["docs/architecture.md"],
    }
    downstream = {item["name"]: item for item in context["downstream"]}
    assert downstream["implementation"]["impact_reason"] == "input_changed"
    assert downstream["implementation"]["depth"] == 1
    assert downstream["tests"]["impact_reason"] == "upstream_changed"
    assert downstream["tests"]["depth"] == 2
    assert context["review_order"] == [implementation["id"], tests["id"]]
    assert "PRIVATE" not in json.dumps(context)

    main(["context", "architecture"])
    human_context = capsys.readouterr().out
    assert "Target Node:\narchitecture" in human_context
    assert "Current Status:\naffected" in human_context
    assert "Why Relevant:\nfiles_changed" in human_context
    assert "Downstream Impact:" in human_context
    assert "implementation" in human_context
    assert "Recommended Review Order:\n1. implementation\n2. tests" in human_context

    explanation = run_json(capsys, "explain", "architecture")
    assert explanation["review_order"] == [
        architecture["id"],
        implementation["id"],
        tests["id"],
    ]
    assert explanation["affected_nodes"] == context["downstream"]

    for name in ("architecture", "implementation", "tests"):
        run_json(capsys, "confirm", name)
    final_status = run_json(capsys, "status")

    assert all(item["status"] == "confirmed" for item in final_status["nodes"])
    assert all(item["reasons"] == [] for item in final_status["nodes"])
