import json

import pytest

from kflow.cli import main


def run_json_error(capsys, *arguments):
    with pytest.raises(SystemExit) as exit_info:
        main([*arguments, "--json"])
    captured = capsys.readouterr()
    result = json.loads(captured.out)
    assert exit_info.value.code != 0
    assert captured.err == ""
    assert set(result) >= {"ok", "schema_version", "issues"}
    assert result["ok"] is False
    assert result["schema_version"] == 2
    assert isinstance(result["issues"], list) and result["issues"]
    assert set(result["issues"][0]) == {"code", "message", "references"}
    assert "Traceback" not in captured.out
    return result


def run_json(capsys, *arguments):
    main([*arguments, "--json"])
    return json.loads(capsys.readouterr().out)


def test_json_errors_use_one_machine_envelope_for_official_failures(
    tmp_path, monkeypatch, capsys
):
    monkeypatch.chdir(tmp_path)

    uninitialized = run_json_error(capsys, "overview")
    assert uninitialized["issues"][0]["code"] == "invalid_project"

    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "a.md").write_text("A", encoding="utf-8")
    (docs / "b.md").write_text("B", encoding="utf-8")
    run_json(capsys, "init")
    run_json(capsys, "add-node", "a", "--file", "docs/a.md")
    run_json(capsys, "add-node", "b", "--file", "docs/b.md")

    unknown = run_json_error(capsys, "context", "missing")
    assert unknown["issues"][0]["code"] == "unknown_node"
    assert unknown["issues"][0]["references"] == ["missing"]

    missing_file = run_json_error(
        capsys, "add-node", "missing-file", "--file", "docs/missing.md"
    )
    assert missing_file["issues"][0]["code"] == "invalid_argument"
    assert missing_file["issues"][0]["references"] == ["docs/missing.md"]

    duplicate_name = run_json_error(capsys, "add-node", "a", "--file", "docs/b.md")
    assert duplicate_name["issues"][0]["code"] == "duplicate_node_name"

    invalid_derivation = run_json_error(
        capsys,
        "derive",
        "--short",
        "invalid",
        "--input",
        "a",
        "input",
        "--output",
        "a",
        "output",
    )
    assert invalid_derivation["issues"][0]["code"] == "invalid_argument"

    run_json(
        capsys,
        "derive",
        "--short",
        "A to B",
        "--input",
        "a",
        "input",
        "--output",
        "b",
        "output",
    )
    cycle = run_json_error(
        capsys,
        "derive",
        "--short",
        "B to A",
        "--input",
        "b",
        "input",
        "--output",
        "a",
        "output",
    )
    assert cycle["issues"][0]["code"] == "cycle"

    rejected = run_json_error(capsys, "context", "a", "--affected")
    assert rejected["issues"][0]["code"] == "invalid_argument"


def test_human_errors_use_stderr_without_traceback(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)

    with pytest.raises(SystemExit) as exit_info:
        main(["overview"])

    captured = capsys.readouterr()
    assert exit_info.value.code == 2
    assert captured.out == ""
    assert "invalid_project" in captured.err
    assert "Traceback" not in captured.err


def test_argument_parser_errors_use_json_envelope(capsys):
    result = run_json_error(capsys, "derive", "--short", "missing roles")

    assert result == {
        "ok": False,
        "schema_version": 2,
        "issues": [
            {
                "code": "invalid_argument",
                "message": ("the following arguments are required: --input, --output"),
                "references": [],
            }
        ],
    }
