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
    assert unknown["issues"][0]["references"] == ["missing"]


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
