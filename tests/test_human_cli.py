"""CLI tests for the foreground Human Interface launcher."""

import json

import pytest

from kflow.cli import build_parser, main


def test_ui_parser_accepts_port_and_no_open() -> None:
    args = build_parser().parse_args(["ui", "--port", "8765", "--no-open"])

    assert args.command == "ui"
    assert args.port == 8765
    assert args.no_open is True


def test_ui_passes_options_to_the_official_runner(tmp_path, monkeypatch) -> None:
    calls = []
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        "kflow.cli.run_ui",
        lambda root, *, port, open_browser: calls.append((root, port, open_browser)),
    )

    main(["ui", "--port", "8765", "--no-open"])

    assert calls == [(tmp_path, 8765, False)]


@pytest.mark.parametrize("arguments", [["ui", "--json"], ["--json", "ui"]])
def test_ui_rejects_json_before_starting(arguments, monkeypatch, capsys) -> None:
    monkeypatch.setattr(
        "kflow.cli.run_ui",
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
