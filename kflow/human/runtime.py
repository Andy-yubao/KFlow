"""Per-project background process lifecycle for the Human Interface."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import secrets
import subprocess
import sys
import threading
import time
import uuid
import webbrowser
from contextlib import contextmanager
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from kflow.core.query import query_project_graph
from kflow.human.server import LOOPBACK_ADDRESS, SERVICE_NAME, create_ui_server, run_ui


START_TIMEOUT_SECONDS = 10.0
STOP_TIMEOUT_SECONDS = 5.0
CONTROL_TOKEN_ENV = "KFLOW_UI_CONTROL_TOKEN"
STATE_DIRECTORY_ENV = "KFLOW_UI_STATE_DIR"


@dataclass(frozen=True, slots=True)
class RuntimeState:
    project_root: str
    pid: int
    port: int
    started_at: str
    instance_id: str
    control_token: str

    @property
    def url(self) -> str:
        return f"http://{LOOPBACK_ADDRESS}:{self.port}/"


def canonical_project_root(root: Path) -> Path:
    return Path(root).resolve()


def instance_key(root: Path) -> str:
    normalized = os.path.normcase(str(canonical_project_root(root)))
    value = normalized.encode("utf-8", errors="surrogatepass")
    return hashlib.sha256(value).hexdigest()


def runtime_directory() -> Path:
    override = os.environ.get(STATE_DIRECTORY_ENV)
    if override:
        return Path(override)
    if os.name == "nt":
        base = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
        return base / "KFlow" / "ui"
    xdg_state = os.environ.get("XDG_STATE_HOME")
    base = Path(xdg_state) if xdg_state else Path.home() / ".local" / "state"
    return base / "kflow" / "ui"


def state_path(root: Path) -> Path:
    return runtime_directory() / f"{instance_key(root)}.json"


def start_ui(
    root: Path,
    *,
    port: int = 0,
    open_browser: bool = True,
    foreground: bool = False,
) -> RuntimeState | None:
    """Start or reuse the current project's UI instance."""
    project_root = canonical_project_root(root)
    _require_initialized_project(project_root)
    if foreground:
        run_ui(project_root, port=port, open_browser=open_browser)
        return None

    path = state_path(project_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    if os.name != "nt":
        path.parent.chmod(0o700)
    with _startup_lock(path):
        existing = inspect_ui(project_root)
        if existing is not None:
            print(f"KFlow Human Interface is already running: {existing.url}")
            if open_browser:
                webbrowser.open(existing.url)
            return existing
        return _spawn_background(
            project_root,
            path,
            port=port,
            open_browser=open_browser,
        )


def _require_initialized_project(root: Path) -> None:
    """Reject invalid storage before creating any local runtime state."""
    result = query_project_graph(root)
    if any(issue.get("code") == "invalid_project" for issue in result["issues"]):
        raise RuntimeError("KFlow project is not initialized. Run `kflow init` first.")


def _spawn_background(
    project_root: Path,
    path: Path,
    *,
    port: int,
    open_browser: bool,
) -> RuntimeState:
    instance_id = uuid.uuid4().hex
    control_token = secrets.token_urlsafe(32)
    log_path = path.with_suffix(".log")
    environment = os.environ.copy()
    environment[CONTROL_TOKEN_ENV] = control_token
    command = [
        sys.executable,
        "-m",
        "kflow.human.runtime",
        "serve",
        "--project-root",
        str(project_root),
        "--port",
        str(port),
        "--instance-id",
        instance_id,
        "--state-file",
        str(path),
    ]
    popen_options: dict = {
        "cwd": project_root,
        "env": environment,
        "stdin": subprocess.DEVNULL,
    }
    if os.name == "nt":
        popen_options["creationflags"] = (
            subprocess.CREATE_NEW_PROCESS_GROUP
            | subprocess.DETACHED_PROCESS
            | subprocess.CREATE_NO_WINDOW
        )
    else:
        popen_options["start_new_session"] = True

    with log_path.open("ab") as log:
        process = subprocess.Popen(
            command,
            stdout=log,
            stderr=log,
            **popen_options,
        )

    deadline = time.monotonic() + START_TIMEOUT_SECONDS
    state: RuntimeState | None = None
    while time.monotonic() < deadline:
        if process.poll() is not None:
            break
        candidate = _load_state(path)
        if (
            candidate is not None
            and candidate.pid == process.pid
            and candidate.instance_id == instance_id
            and candidate.control_token == control_token
            and _health_matches(candidate, project_root)
        ):
            state = candidate
            break
        time.sleep(0.05)

    if state is None:
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                process.kill()
        _remove_state_if_owned(path, instance_id)
        raise RuntimeError(f"background service did not become healthy; see {log_path}")

    print(f"KFlow Human Interface: {state.url}")
    if open_browser:
        webbrowser.open(state.url)
    return state


def inspect_ui(root: Path) -> RuntimeState | None:
    """Return a health-verified state, cleaning any stale record."""
    project_root = canonical_project_root(root)
    path = state_path(project_root)
    state = _load_state(path)
    if state is None:
        _remove_file(path)
        return None
    if not _pid_is_alive(state.pid) or not _health_matches(state, project_root):
        _remove_state_if_owned(path, state.instance_id)
        return None
    return state


def stop_ui(root: Path) -> bool:
    """Stop only the health-verified instance for the current project."""
    project_root = canonical_project_root(root)
    state = inspect_ui(project_root)
    if state is None:
        print(f"KFlow Human Interface is stopped for {project_root}")
        return False

    request = Request(
        f"http://{LOOPBACK_ADDRESS}:{state.port}/api/shutdown",
        data=b"{}",
        method="POST",
        headers={
            "Accept": "application/json",
            "Content-Type": "application/json",
            "X-KFlow-Control-Token": state.control_token,
        },
    )
    try:
        with urlopen(request, timeout=1) as response:
            if response.status != 200:
                raise RuntimeError("shutdown request was rejected")
    except (HTTPError, URLError, OSError) as error:
        raise RuntimeError(
            f"unable to stop the verified UI instance: {error}"
        ) from error

    path = state_path(project_root)
    deadline = time.monotonic() + STOP_TIMEOUT_SECONDS
    while time.monotonic() < deadline:
        if not _pid_is_alive(state.pid):
            _remove_state_if_owned(path, state.instance_id)
            print(f"Stopped KFlow Human Interface for {project_root}")
            return True
        time.sleep(0.05)
    raise RuntimeError("the UI instance did not stop in time")


def print_ui_status(root: Path) -> RuntimeState | None:
    project_root = canonical_project_root(root)
    state = inspect_ui(project_root)
    if state is None:
        print("Status: stopped")
        print(f"Project root: {project_root}")
        print("Local URL: -")
        print("PID: -")
        print("Started at: -")
        return None
    print("Status: running")
    print(f"Project root: {state.project_root}")
    print(f"Local URL: {state.url}")
    print(f"PID: {state.pid}")
    print(f"Started at: {state.started_at}")
    return state


def serve_background(root: Path, port: int, instance_id: str, path: Path) -> None:
    """Internal detached child process entrypoint."""
    project_root = canonical_project_root(root)
    control_token = os.environ.pop(CONTROL_TOKEN_ENV, "")
    if not control_token:
        raise RuntimeError("missing background control token")
    server = create_ui_server(
        project_root,
        port,
        instance_id=instance_id,
        control_token=control_token,
    )
    state = RuntimeState(
        project_root=str(project_root),
        pid=os.getpid(),
        port=int(server.server_address[1]),
        started_at=datetime.now(timezone.utc).isoformat(),
        instance_id=instance_id,
        control_token=control_token,
    )
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        deadline = time.monotonic() + 2.0
        while time.monotonic() < deadline and not _health_matches(state, project_root):
            time.sleep(0.02)
        if not _health_matches(state, project_root):
            raise RuntimeError("background server failed its local health check")
        _write_state(path, state)
        thread.join()
    finally:
        if thread.is_alive():
            server.shutdown()
            thread.join(timeout=2)
        server.server_close()
        _remove_state_if_owned(path, instance_id)


@contextmanager
def _startup_lock(path: Path):
    lock_path = path.with_suffix(".lock")
    deadline = time.monotonic() + START_TIMEOUT_SECONDS + 2.0
    descriptor: int | None = None
    while descriptor is None:
        try:
            descriptor = os.open(
                lock_path,
                os.O_CREAT | os.O_EXCL | os.O_WRONLY,
                0o600,
            )
        except FileExistsError:
            try:
                age = time.time() - lock_path.stat().st_mtime
            except OSError:
                age = 0
            if age > START_TIMEOUT_SECONDS * 2:
                _remove_file(lock_path)
                continue
            if time.monotonic() >= deadline:
                raise RuntimeError("another UI start is still in progress")
            time.sleep(0.05)
    try:
        os.write(descriptor, str(os.getpid()).encode("ascii"))
        yield
    finally:
        os.close(descriptor)
        _remove_file(lock_path)


def _health_matches(state: RuntimeState, project_root: Path) -> bool:
    try:
        with urlopen(
            f"http://{LOOPBACK_ADDRESS}:{state.port}/api/health", timeout=0.5
        ) as response:
            if response.status != 200:
                return False
            result = json.load(response)
    except (HTTPError, URLError, OSError, ValueError):
        return False
    return (
        result.get("ok") is True
        and result.get("service") == SERVICE_NAME
        and isinstance(result.get("project_root"), str)
        and os.path.normcase(result["project_root"])
        == os.path.normcase(str(project_root))
        and result.get("instance_id") == state.instance_id
    )


def _pid_is_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    if os.name == "nt":
        return _windows_pid_is_alive(pid)
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True


def _windows_pid_is_alive(pid: int) -> bool:
    import ctypes

    process_query_limited_information = 0x1000
    still_active = 259
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.OpenProcess.argtypes = [ctypes.c_uint32, ctypes.c_int, ctypes.c_uint32]
    kernel32.OpenProcess.restype = ctypes.c_void_p
    kernel32.GetExitCodeProcess.argtypes = [
        ctypes.c_void_p,
        ctypes.POINTER(ctypes.c_uint32),
    ]
    kernel32.GetExitCodeProcess.restype = ctypes.c_int
    kernel32.CloseHandle.argtypes = [ctypes.c_void_p]
    kernel32.CloseHandle.restype = ctypes.c_int
    handle = kernel32.OpenProcess(process_query_limited_information, False, pid)
    if not handle:
        return False
    try:
        exit_code = ctypes.c_uint32()
        if not kernel32.GetExitCodeProcess(handle, ctypes.byref(exit_code)):
            return False
        return exit_code.value == still_active
    finally:
        kernel32.CloseHandle(handle)


def _load_state(path: Path) -> RuntimeState | None:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        state = RuntimeState(**value)
    except (OSError, UnicodeError, json.JSONDecodeError, TypeError):
        return None
    if (
        not state.project_root
        or isinstance(state.pid, bool)
        or not isinstance(state.pid, int)
        or state.pid <= 0
        or isinstance(state.port, bool)
        or not isinstance(state.port, int)
        or not 1 <= state.port <= 65535
        or not state.started_at
        or not state.instance_id
        or not state.control_token
    ):
        return None
    return state


def _write_state(path: Path, state: RuntimeState) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    try:
        temporary.write_text(
            json.dumps(asdict(state), ensure_ascii=False, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        if os.name != "nt":
            temporary.chmod(0o600)
        os.replace(temporary, path)
    finally:
        _remove_file(temporary)


def _remove_state_if_owned(path: Path, instance_id: str) -> None:
    state = _load_state(path)
    if state is not None and state.instance_id == instance_id:
        _remove_file(path)


def _remove_file(path: Path) -> None:
    try:
        path.unlink()
    except FileNotFoundError:
        pass


def _build_internal_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("action", choices=("serve",))
    parser.add_argument("--project-root", required=True)
    parser.add_argument("--port", type=int, required=True)
    parser.add_argument("--instance-id", required=True)
    parser.add_argument("--state-file", required=True)
    return parser


def main(argv: list[str] | None = None) -> None:
    args = _build_internal_parser().parse_args(argv)
    serve_background(
        Path(args.project_root),
        args.port,
        args.instance_id,
        Path(args.state_file),
    )


if __name__ == "__main__":
    main()
