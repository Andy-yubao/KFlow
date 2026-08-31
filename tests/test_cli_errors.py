import json

import pytest

from kflow.cli import _format_issue, _print_issues, main


def run_json_error(capsys, *arguments):
    with pytest.raises(SystemExit) as exit_info:
        main([*arguments, "--json"])
    captured = capsys.readouterr()
    result = json.loads(captured.out)
    assert exit_info.value.code != 0
    assert captured.err == ""
    assert result["ok"] is False
    assert isinstance(result["schema_version"], int)
    assert result["issues"]
    assert set(result["issues"][0]) == {"code", "message", "references"}
    return result


def test_json_domain_errors_use_machine_envelope(tmp_path, monkeypatch, capsys) -> None:
    monkeypatch.chdir(tmp_path)

    uninitialized = run_json_error(capsys, "overview")
    assert uninitialized["schema_version"] == 2
    assert uninitialized["issues"][0]["code"] == "invalid_project"

    main(["init", "--json"])
    capsys.readouterr()
    unknown = run_json_error(capsys, "context", "missing")
    assert unknown["schema_version"] == 3
    assert unknown["issues"][0]["code"] == "unknown_node"
    assert unknown["issues"][0]["message"] == "unknown node: missing"
    assert unknown["issues"][0]["references"] == ["missing"]


@pytest.mark.parametrize(
    ("issue", "expected"),
    [
        (
            {
                "code": "missing_file",
                "message": "node file is missing: docs/missing.md",
                "references": ["nd_missing", "docs/missing.md"],
            },
            "docs/missing.md",
        ),
        (
            {
                "code": "unreadable_file",
                "message": "node file cannot be read: docs/private.md",
                "references": ["nd_private", "docs/private.md"],
            },
            "docs/private.md",
        ),
        (
            {
                "code": "cycle",
                "message": "derivation projection contains a cycle",
                "references": ["nd_a", "nd_b"],
            },
            "derivation projection contains a cycle",
        ),
        (
            {
                "code": "multiple_producers",
                "message": "node has multiple producing derivations: nd_out",
                "references": ["nd_out", "dv_a", "dv_b"],
            },
            "node has multiple producing derivations: nd_out",
        ),
        (
            {
                "code": "duplicate_node_name",
                "message": "node name has multiple owners: design",
                "references": ["nd_a", "nd_b"],
            },
            "node name has multiple owners: design",
        ),
        (
            {
                "code": "unknown_node",
                "message": "unknown node: missing",
                "references": ["missing"],
            },
            "unknown node: missing",
        ),
    ],
)
def test_human_issue_format_keeps_graph_messages_and_path_details(
    issue, expected, capsys
) -> None:
    original = json.loads(json.dumps(issue))

    assert _format_issue(issue) == expected
    _print_issues([issue])
    assert capsys.readouterr().out == f"- {issue['code']}: {expected}\n"
    assert json.loads(json.dumps(issue)) == original
    assert issue == original


@pytest.mark.parametrize(
    "arguments",
    [
        ("status",),
        ("scan",),
        ("explain", "node"),
        ("context", "node", "--affected"),
        ("impact",),
    ],
)
def test_removed_or_incomplete_commands_are_argument_errors(capsys, arguments) -> None:
    result = run_json_error(capsys, *arguments)

    assert result["issues"][0]["code"] == "invalid_argument"
    assert result["schema_version"] == 3


def test_human_errors_use_stderr_without_traceback(
    tmp_path, monkeypatch, capsys
) -> None:
    monkeypatch.chdir(tmp_path)

    with pytest.raises(SystemExit) as exit_info:
        main(["overview"])

    captured = capsys.readouterr()
    assert exit_info.value.code == 2
    assert captured.out == ""
    assert "invalid_project" in captured.err
    assert "Traceback" not in captured.err


def test_json_without_command_uses_machine_error_envelope(capsys) -> None:
    result = run_json_error(capsys)

    assert result["issues"][0]["message"] == "a command is required"


def test_human_mode_without_command_still_prints_help(capsys) -> None:
    with pytest.raises(SystemExit):
        main([])

    captured = capsys.readouterr()
    assert "usage: kflow" in captured.out
    assert captured.err == ""
