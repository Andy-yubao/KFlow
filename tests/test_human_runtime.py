"""Background Human Interface lifecycle tests."""

import json
import os
import socket
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from pathlib import Path

import pytest

from kflow.core.storage import initialize_project
from kflow.human import runtime
from kflow.human.runtime import RuntimeState


def _state(root: Path, **changes) -> RuntimeState:
    value = RuntimeState(
        project_root=str(runtime.canonical_project_root(root)),
        pid=os.getpid(),
        port=8765,
        started_at="2026-09-01T10:00:00+00:00",
        instance_id="instance-one",
        control_token="secret-token",
    )
    return replace(value, **changes)


def test_instance_key_is_stable_and_separates_projects(tmp_path) -> None:
    first = tmp_path / "项目 one"
    second = tmp_path / "项目 two"
    first.mkdir()
    second.mkdir()

    assert runtime.instance_key(first) == runtime.instance_key(first / ".")
    assert runtime.instance_key(first) != runtime.instance_key(second)


def test_inspect_cleans_corrupt_stale_and_reused_pid_state(
    tmp_path, monkeypatch
) -> None:
    state_dir = tmp_path / "state"
    project = tmp_path / "project"
    project.mkdir()
    monkeypatch.setenv(runtime.STATE_DIRECTORY_ENV, str(state_dir))
    path = runtime.state_path(project)
    path.parent.mkdir(parents=True)

    path.write_text("not json", encoding="utf-8")
    assert runtime.inspect_ui(project) is None
    assert not path.exists()

    runtime._write_state(path, _state(project, pid=999_999))
    monkeypatch.setattr(runtime, "_pid_is_alive", lambda _pid: False)
    assert runtime.inspect_ui(project) is None
    assert not path.exists()

    runtime._write_state(path, _state(project))
    monkeypatch.setattr(runtime, "_pid_is_alive", lambda _pid: True)
    monkeypatch.setattr(runtime, "_health_matches", lambda *_args: False)
    assert runtime.inspect_ui(project) is None
    assert not path.exists()


def test_start_reuses_one_verified_instance_and_opens_existing_url(
    tmp_path, monkeypatch
) -> None:
    project = tmp_path / "项目 with spaces"
    project.mkdir()
    existing = _state(project)
    opened = []
    monkeypatch.setattr(runtime, "inspect_ui", lambda _root: existing)
    monkeypatch.setattr(runtime.webbrowser, "open", opened.append)
    monkeypatch.setattr(
        runtime.subprocess,
        "Popen",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("must not spawn a second instance")
        ),
    )

    result = runtime.start_ui(project)

    assert result == existing
    assert opened == [existing.url]


def test_status_reports_all_fields_for_running_and_stopped(
    tmp_path, monkeypatch, capsys
) -> None:
    project = tmp_path / "project"
    project.mkdir()
    state = _state(project)
    monkeypatch.setattr(runtime, "inspect_ui", lambda _root: state)
    runtime.print_ui_status(project)
    running = capsys.readouterr().out
    assert "Status: running" in running
    assert state.project_root in running
    assert state.url in running
    assert str(state.pid) in running
    assert state.started_at in running

    monkeypatch.setattr(runtime, "inspect_ui", lambda _root: None)
    runtime.print_ui_status(project)
    stopped = capsys.readouterr().out
    assert "Status: stopped" in stopped
    assert "Local URL: -" in stopped
    assert "PID: -" in stopped
    assert "Started at: -" in stopped


def test_stop_is_idempotent_when_no_instance_exists(
    tmp_path, monkeypatch, capsys
) -> None:
    monkeypatch.setattr(runtime, "inspect_ui", lambda _root: None)
    assert runtime.stop_ui(tmp_path) is False
    assert "stopped" in capsys.readouterr().out


def test_runtime_state_is_user_level_not_inside_kflow(tmp_path, monkeypatch) -> None:
    state_dir = tmp_path / "user state"
    project = tmp_path / "project"
    project.mkdir()
    monkeypatch.setenv(runtime.STATE_DIRECTORY_ENV, str(state_dir))

    path = runtime.state_path(project)

    assert path.parent == state_dir
    assert project not in path.parents
    assert path.suffix == ".json"


def test_state_loader_rejects_invalid_port_and_extra_fields(tmp_path) -> None:
    path = tmp_path / "state.json"
    value = runtime.asdict(_state(tmp_path))
    value["port"] = 0
    path.write_text(json.dumps(value), encoding="utf-8")
    assert runtime._load_state(path) is None

    value["port"] = 8765
    value["unexpected"] = True
    path.write_text(json.dumps(value), encoding="utf-8")
    assert runtime._load_state(path) is None


def test_pid_probe_distinguishes_current_and_missing_process() -> None:
    assert runtime._pid_is_alive(os.getpid()) is True
    assert runtime._pid_is_alive(2_147_483_647) is False


def test_real_background_instances_reuse_per_project_and_separate_projects(
    tmp_path, monkeypatch
) -> None:
    state_dir = tmp_path / "user state"
    first_project = tmp_path / "项目 one"
    second_project = tmp_path / "project two"
    first_project.mkdir()
    second_project.mkdir()
    initialize_project(first_project)
    initialize_project(second_project)
    monkeypatch.setenv(runtime.STATE_DIRECTORY_ENV, str(state_dir))
    monkeypatch.setattr(runtime.webbrowser, "open", lambda _url: True)

    with ThreadPoolExecutor(max_workers=2) as executor:
        starts = [
            executor.submit(runtime.start_ui, first_project, open_browser=False)
            for _ in range(2)
        ]
        first, reused = [start.result() for start in starts]
    second = None
    try:
        second = runtime.start_ui(second_project, open_browser=False)
        assert first is not None
        assert reused is not None
        assert second is not None
        assert reused.pid == first.pid
        assert reused.instance_id == first.instance_id
        assert second.pid != first.pid
        assert runtime.inspect_ui(first_project) == first
        assert runtime.inspect_ui(second_project) == second
    finally:
        if second is not None:
            runtime.stop_ui(second_project)
        if first is not None:
            runtime.stop_ui(first_project)


def test_port_conflict_fails_cleanly_without_runtime_state(
    tmp_path, monkeypatch
) -> None:
    project = tmp_path / "project with spaces"
    project.mkdir()
    initialize_project(project)
    monkeypatch.setenv(runtime.STATE_DIRECTORY_ENV, str(tmp_path / "user state"))
    with socket.socket() as occupied:
        occupied.bind((runtime.LOOPBACK_ADDRESS, 0))
        occupied.listen()
        port = occupied.getsockname()[1]
        with pytest.raises(RuntimeError, match="did not become healthy"):
            runtime.start_ui(project, port=port, open_browser=False)

    assert runtime.inspect_ui(project) is None
    assert not runtime.state_path(project).exists()
