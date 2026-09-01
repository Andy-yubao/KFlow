"""CLI tests for Human Interface lifecycle commands."""

import json

import pytest

from kflow.cli import build_parser, main
from kflow.human import runtime


def test_ui_parser_accepts_port_and_no_open() -> None:
    start = build_parser().parse_args(["ui", "start", "--port", "8766", "--no-open"])
    assert start.command == "ui"
    assert start.ui_command == "start"
    assert start.port == 8766
    assert start.no_open is True


def test_ui_start_passes_options_to_the_lifecycle_runner(tmp_path, monkeypatch) -> None:
    calls = []
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        "kflow.cli.start_ui",
        lambda root, *, port, open_browser: calls.append((root, port, open_browser)),
    )

    main(["ui", "start", "--port", "8766", "--no-open"])

    assert calls == [(tmp_path, 8766, False)]


def test_ui_without_action_prints_help_without_starting(monkeypatch, capsys) -> None:
    monkeypatch.setattr(
        "kflow.cli.start_ui",
        lambda *args, **kwargs: pytest.fail("UI server should not start"),
    )

    with pytest.raises(SystemExit) as exit_info:
        main(["ui"])

    assert exit_info.value.code != 0
    output = capsys.readouterr()
    assert "usage: kflow ui" in output.out
    assert "start" in output.out
    assert "stop" in output.out
    assert "status" in output.out


@pytest.mark.parametrize(
    "arguments",
    [
        ["ui", "--foreground"],
        ["ui", "start", "--foreground"],
    ],
)
def test_ui_rejects_removed_foreground_option(arguments, monkeypatch) -> None:
    monkeypatch.setattr(
        "kflow.cli.start_ui",
        lambda *args, **kwargs: pytest.fail("UI server should not start"),
    )

    with pytest.raises(SystemExit) as exit_info:
        main(arguments)

    assert exit_info.value.code == 2


def test_ui_stop_and_status_dispatch_without_starting(tmp_path, monkeypatch) -> None:
    calls = []
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("kflow.cli.stop_ui", lambda root: calls.append(("stop", root)))
    monkeypatch.setattr(
        "kflow.cli.print_ui_status", lambda root: calls.append(("status", root))
    )
    monkeypatch.setattr(
        "kflow.cli.start_ui", lambda *args, **kwargs: pytest.fail("must not start")
    )

    main(["ui", "status"])
    main(["ui", "stop"])

    assert calls == [("status", tmp_path), ("stop", tmp_path)]


@pytest.mark.parametrize(
    "arguments",
    [
        ["ui", "start"],
        ["ui", "start", "--no-open"],
    ],
)
def test_ui_start_forms_reject_uninitialized_directory_without_side_effects(
    tmp_path, monkeypatch, capsys, arguments
) -> None:
    state_dir = tmp_path / "user state"
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv(runtime.STATE_DIRECTORY_ENV, str(state_dir))
    monkeypatch.setattr(
        runtime.subprocess,
        "Popen",
        lambda *_args, **_kwargs: pytest.fail("must not spawn"),
    )
    monkeypatch.setattr(
        runtime.webbrowser,
        "open",
        lambda *_args, **_kwargs: pytest.fail("must not open browser"),
    )

    with pytest.raises(SystemExit) as exit_info:
        main(arguments)

    assert exit_info.value.code == 2
    assert "Run `kflow init` first." in capsys.readouterr().err
    assert not state_dir.exists()
    assert not (tmp_path / ".kflow").exists()

    main(["init", str(tmp_path)])
    assert (tmp_path / ".kflow" / "project.json").is_file()


@pytest.mark.parametrize("arguments", [["ui", "--json"], ["--json", "ui"]])
def test_ui_rejects_json_before_starting(arguments, monkeypatch, capsys) -> None:
    monkeypatch.setattr(
        "kflow.cli.start_ui",
        lambda *args, **kwargs: pytest.fail("UI server should not start"),
    )

    with pytest.raises(SystemExit) as exit_info:
        main(arguments)

    assert exit_info.value.code == 2
    result = json.loads(capsys.readouterr().out)
    assert result == {
        "ok": False,
        "schema_version": 3,
        "issues": [
            {
                "code": "invalid_argument",
                "message": "ui does not support --json",
                "references": [],
            }
        ],
    }
