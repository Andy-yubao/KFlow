"""Local read-only HTTP server for the KFlow Human Interface."""

import json
import hmac
import mimetypes
import os
import subprocess
import sys
import threading
import uuid
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from importlib import resources
from pathlib import Path, PurePosixPath, PureWindowsPath
from urllib.parse import parse_qs, unquote, urlsplit

from kflow.core.query import query_project_graph, query_review_order
from kflow.human.git_snapshot import (
    DEFAULT_HISTORY_LIMIT,
    MAX_HISTORY_LIMIT,
    graph_diff_against_revision,
    is_full_hex_commit_id,
    query_git_history,
    unavailable_git_history,
)
from kflow.human.graph_diff import unavailable_graph_diff
from kflow.human.revision import RevisionTracker

LOOPBACK_ADDRESS = "127.0.0.1"
SERVICE_NAME = "kflow-human-interface"
MAX_JSON_BODY_BYTES = 64 * 1024


def create_ui_server(
    root: Path,
    port: int = 0,
    *,
    instance_id: str | None = None,
    control_token: str | None = None,
) -> ThreadingHTTPServer:
    """Create a loopback-only Human Interface server without starting it."""
    project_root = Path(root).resolve()
    project_identity = str(project_root)
    handler = _handler_for(
        project_root,
        project_identity,
        instance_id or uuid.uuid4().hex,
        control_token,
    )
    return ThreadingHTTPServer((LOOPBACK_ADDRESS, port), handler)


def run_ui(root: Path, port: int = 0, open_browser: bool = True) -> None:
    """Run the Human Interface in the foreground until interrupted."""
    server = create_ui_server(root, port)
    actual_port = server.server_address[1]
    url = f"http://{LOOPBACK_ADDRESS}:{actual_port}/"
    print(f"KFlow Human Interface: {url}", flush=True)
    print("Press Ctrl+C to stop.", flush=True)

    if open_browser:
        webbrowser.open(url)

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


def _handler_for(
    root: Path,
    project_identity: str,
    instance_id: str,
    control_token: str | None,
) -> type[BaseHTTPRequestHandler]:
    revision_tracker = RevisionTracker(root)

    class HumanInterfaceHandler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:  # noqa: N802
            request = urlsplit(self.path)
            path = request.path
            if path == "/api/health":
                self._send_json(
                    {
                        "ok": True,
                        "service": SERVICE_NAME,
                        "project_root": project_identity,
                        "instance_id": instance_id,
                    }
                )
                return
            if path == "/api/project":
                result = query_project_graph(root)
                revision_tracker.observe_project_graph(result)
                self._send_json(result)
                return
            if path == "/api/revision":
                if not revision_tracker.observed:
                    revision_tracker.observe_project_graph(query_project_graph(root))
                self._send_json(revision_tracker.result())
                return
            if path == "/api/review-order":
                self._send_json(query_review_order(root))
                return
            if path == "/api/git-history":
                self._git_history(request.query)
                return
            if path == "/api/graph-diff":
                self._graph_diff(request.query)
                return
            if path in {"/api/open-file", "/api/shutdown"}:
                self._method_not_allowed("POST")
                return
            self._serve_static(path)

        def _git_history(self, query: str) -> None:
            parameters = parse_qs(query, keep_blank_values=True)
            if set(parameters) - {"limit"} or len(parameters.get("limit", [])) > 1:
                self._send_json(
                    unavailable_git_history(
                        "Git history accepts only one integer limit parameter.",
                        ok=False,
                    ),
                    status=400,
                )
                return
            limit = DEFAULT_HISTORY_LIMIT
            if "limit" in parameters:
                try:
                    limit = int(parameters["limit"][0])
                except ValueError:
                    limit = 0
                if not 1 <= limit <= MAX_HISTORY_LIMIT:
                    self._send_json(
                        unavailable_git_history(
                            f"Git history limit must be between 1 and {MAX_HISTORY_LIMIT}.",
                            ok=False,
                        ),
                        status=400,
                    )
                    return
            self._send_json(query_git_history(root, limit=limit))

        def _graph_diff(self, query: str) -> None:
            parameters = parse_qs(query, keep_blank_values=True)
            if set(parameters) - {"base"} or len(parameters.get("base", [])) > 1:
                self._send_json(_invalid_graph_diff_query(), status=400)
                return
            base = None
            if "base" in parameters:
                base = parameters["base"][0]
                if not is_full_hex_commit_id(base):
                    self._send_json(_invalid_graph_diff_query(), status=400)
                    return
            self._send_json(graph_diff_against_revision(root, base))

        def do_POST(self) -> None:  # noqa: N802
            path = urlsplit(self.path).path
            if path == "/api/open-file":
                self._open_file()
                return
            if path == "/api/shutdown":
                self._shutdown()
                return
            self._method_not_allowed("GET")

        def do_PUT(self) -> None:  # noqa: N802
            self._method_not_allowed()

        def do_PATCH(self) -> None:  # noqa: N802
            self._method_not_allowed()

        def do_DELETE(self) -> None:  # noqa: N802
            self._method_not_allowed()

        def do_HEAD(self) -> None:  # noqa: N802
            self._method_not_allowed()

        def do_OPTIONS(self) -> None:  # noqa: N802
            self._method_not_allowed()

        def _open_file(self) -> None:
            request, issue = self._read_json_object()
            if issue is not None:
                self._send_json(_open_file_error(None, *issue), status=400)
                return

            requested_path = request.get("path")
            candidate, issue = _resolve_registered_file(root, requested_path)
            if issue is not None:
                path = requested_path if isinstance(requested_path, str) else None
                self._send_json(_open_file_error(path, *issue), status=400)
                return

            assert candidate is not None
            try:
                _open_registered_file(candidate)
            except (OSError, subprocess.SubprocessError) as error:
                self._send_json(
                    _open_file_error(
                        requested_path,
                        "open_failed",
                        f"unable to open registered file: {error}",
                    ),
                    status=500,
                )
                return
            self._send_json({"ok": True, "path": requested_path})

        def _shutdown(self) -> None:
            supplied = self.headers.get("X-KFlow-Control-Token", "")
            if control_token is None or not hmac.compare_digest(
                supplied, control_token
            ):
                self._send_json(
                    {
                        "ok": False,
                        "issues": [
                            {
                                "code": "invalid_control_token",
                                "message": "shutdown control token is invalid",
                                "references": [],
                            }
                        ],
                    },
                    status=403,
                )
                return
            self._send_json({"ok": True})
            threading.Thread(target=self.server.shutdown, daemon=True).start()

        def _read_json_object(self) -> tuple[dict, tuple[str, str] | None]:
            try:
                content_length = int(self.headers.get("Content-Length", "0"))
            except ValueError:
                return {}, ("invalid_request", "invalid Content-Length")
            if content_length <= 0 or content_length > MAX_JSON_BODY_BYTES:
                return {}, ("invalid_request", "request body size is invalid")
            try:
                value = json.loads(self.rfile.read(content_length))
            except (json.JSONDecodeError, UnicodeDecodeError):
                return {}, ("invalid_request", "request body must be valid JSON")
            if not isinstance(value, dict):
                return {}, ("invalid_request", "request body must be a JSON object")
            return value, None

        def _send_json(self, result: dict, *, status: int = 200) -> None:
            body = json.dumps(
                result,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
            self._send_bytes(
                status,
                body,
                "application/json; charset=utf-8",
                cache_control="no-store",
            )

        def _serve_static(self, request_path: str) -> None:
            resource_path = _safe_static_path(request_path)
            if resource_path is None:
                self._send_bytes(404, b"Not Found\n", "text/plain; charset=utf-8")
                return

            static_root = resources.files("kflow.human").joinpath("static")
            resource = static_root.joinpath(*resource_path.parts)
            if not resource.is_file():
                self._send_bytes(404, b"Not Found\n", "text/plain; charset=utf-8")
                return

            content_type, _encoding = mimetypes.guess_type(resource_path.name)
            self._send_bytes(
                200,
                resource.read_bytes(),
                content_type or "application/octet-stream",
                cache_control="no-cache",
            )

        def _method_not_allowed(self, allow: str | None = None) -> None:
            try:
                content_length = int(self.headers.get("Content-Length", "0"))
            except ValueError:
                content_length = 0
            if content_length > 0:
                self.rfile.read(content_length)
            self.send_response(405)
            allowed_method = allow or (
                "POST"
                if urlsplit(self.path).path in {"/api/open-file", "/api/shutdown"}
                else "GET"
            )
            self.send_header("Allow", allowed_method)
            self.send_header("Connection", "close")
            body = b"Method Not Allowed\n"
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)
            self.close_connection = True

        def _send_bytes(
            self,
            status: int,
            body: bytes,
            content_type: str,
            *,
            cache_control: str = "no-store",
        ) -> None:
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", cache_control)
            self.end_headers()
            try:
                self.wfile.write(body)
                self.wfile.flush()
            except (BrokenPipeError, ConnectionAbortedError, ConnectionResetError):
                return

        def log_message(self, format: str, *args) -> None:
            return

    return HumanInterfaceHandler


def _open_file_error(path: str | None, code: str, message: str) -> dict:
    return {
        "ok": False,
        "path": path,
        "issues": [
            {
                "code": code,
                "message": message,
                "references": [] if path is None else [path],
            }
        ],
    }


def _invalid_graph_diff_query() -> dict:
    result = unavailable_graph_diff(
        "invalid_argument",
        "Graph Diff base must be one full hexadecimal commit object ID.",
    )
    result["ok"] = False
    return result


def _resolve_registered_file(
    root: Path, requested_path: object
) -> tuple[Path | None, tuple[str, str] | None]:
    if not isinstance(requested_path, str) or not requested_path:
        return None, ("invalid_path", "path must be a non-empty string")

    parsed = urlsplit(requested_path)
    posix_path = PurePosixPath(requested_path)
    windows_path = PureWindowsPath(requested_path)
    if (
        parsed.scheme
        or parsed.netloc
        or posix_path.is_absolute()
        or windows_path.is_absolute()
        or windows_path.drive
        or "\\" in requested_path
        or any(part in {"", ".", ".."} for part in posix_path.parts)
    ):
        return None, ("invalid_path", "path must be a safe project-relative path")

    project = query_project_graph(root)
    registered_files = {
        file_path for node in project["nodes"] for file_path in node["files"]
    }
    if requested_path not in registered_files:
        return None, (
            "unregistered_file",
            "path is not registered in the project graph",
        )

    project_root = Path(root).resolve()
    candidate = project_root.joinpath(*posix_path.parts)
    if not candidate.exists():
        return None, ("file_not_found", "registered file does not exist")
    try:
        resolved = candidate.resolve(strict=True)
        resolved.relative_to(project_root)
    except (OSError, ValueError):
        return None, (
            "path_outside_project",
            "registered file resolves outside the project",
        )
    if not resolved.is_file():
        return None, ("not_regular_file", "registered path is not a regular file")
    return resolved, None


def _open_registered_file(path: Path) -> None:
    """Open one validated registered file with the platform default application."""
    if sys.platform == "win32":
        os.startfile(path)  # type: ignore[attr-defined]
        return
    command = (
        ["open", str(path)] if sys.platform == "darwin" else ["xdg-open", str(path)]
    )
    subprocess.run(command, check=True)


def _safe_static_path(request_path: str) -> PurePosixPath | None:
    decoded = unquote(request_path)
    if "\\" in decoded or ":" in decoded:
        return None
    if decoded == "/":
        return PurePosixPath("index.html")
    if not decoded.startswith("/") or decoded.startswith("//"):
        return None

    relative = PurePosixPath(decoded[1:])
    if not relative.parts or any(part in {"", ".", ".."} for part in relative.parts):
        return None
    return relative
