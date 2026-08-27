"""Local read-only HTTP server for the KFlow Human Interface."""

import json
import mimetypes
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from importlib import resources
from pathlib import Path, PurePosixPath
from urllib.parse import unquote, urlsplit

from kflow.core.query import query_project_graph

LOOPBACK_ADDRESS = "127.0.0.1"
SERVICE_NAME = "kflow-human-interface"


def create_ui_server(root: Path, port: int = 0) -> ThreadingHTTPServer:
    """Create a loopback-only Human Interface server without starting it."""
    project_root = Path(root).resolve()
    handler = _handler_for(project_root)
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


def _handler_for(root: Path) -> type[BaseHTTPRequestHandler]:
    class HumanInterfaceHandler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:  # noqa: N802
            path = urlsplit(self.path).path
            if path == "/api/health":
                self._send_json({"ok": True, "service": SERVICE_NAME})
                return
            if path == "/api/project":
                self._send_json(query_project_graph(root))
                return
            self._serve_static(path)

        def do_POST(self) -> None:  # noqa: N802
            self._method_not_allowed()

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

        def _send_json(self, result: dict) -> None:
            body = json.dumps(
                result,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
            self._send_bytes(
                200,
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

        def _method_not_allowed(self) -> None:
            try:
                content_length = int(self.headers.get("Content-Length", "0"))
            except ValueError:
                content_length = 0
            if content_length > 0:
                self.rfile.read(content_length)
            self.send_response(405)
            self.send_header("Allow", "GET")
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
            self.wfile.write(body)

        def log_message(self, format: str, *args) -> None:
            return

    return HumanInterfaceHandler


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
