"""Read-only HTTP boundary tests for the Human Interface."""

import json
import re
import threading
from contextlib import contextmanager
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from kflow.core.operations import add_node
from kflow.core.query import query_project_graph
from kflow.core.storage import initialize_project
from kflow.human.server import create_ui_server


@contextmanager
def running_ui(root):
    server = create_ui_server(root)
    thread = threading.Thread(target=server.serve_forever)
    thread.start()
    host, port = server.server_address[:2]
    try:
        yield server, f"http://{host}:{port}"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)
        assert not thread.is_alive()


def get_json(url: str) -> dict:
    with urlopen(url, timeout=2) as response:
        assert response.headers.get_content_type() == "application/json"
        assert response.headers.get_content_charset() == "utf-8"
        assert response.headers["Cache-Control"] == "no-store"
        return json.load(response)


def test_server_binds_loopback_and_allocates_an_ephemeral_port(tmp_path) -> None:
    server = create_ui_server(tmp_path)
    try:
        host, port = server.server_address[:2]
        assert host == "127.0.0.1"
        assert isinstance(port, int)
        assert port > 0
    finally:
        server.server_close()


def test_health_endpoint_returns_stable_json(tmp_path) -> None:
    with running_ui(tmp_path) as (_server, base_url):
        assert get_json(f"{base_url}/api/health") == {
            "ok": True,
            "service": "kflow-human-interface",
        }


def test_project_endpoint_matches_public_query_and_excludes_contents(tmp_path) -> None:
    docs = tmp_path / "docs"
    docs.mkdir()
    secret = "PRIVATE DOCUMENT BODY"
    (docs / "architecture.md").write_text(secret, encoding="utf-8")
    initialize_project(tmp_path)
    add_node(tmp_path, "architecture", ("docs/architecture.md",))

    with running_ui(tmp_path) as (_server, base_url):
        with urlopen(f"{base_url}/api/project", timeout=2) as response:
            body = response.read().decode("utf-8")

    assert json.loads(body) == query_project_graph(tmp_path)
    assert secret not in body


def test_project_endpoint_preserves_empty_and_uninitialized_results(tmp_path) -> None:
    initialize_project(tmp_path)
    with running_ui(tmp_path) as (_server, base_url):
        empty = get_json(f"{base_url}/api/project")
    assert empty["ok"] is True
    assert empty["nodes"] == []

    other = tmp_path / "other"
    other.mkdir()
    with running_ui(other) as (_server, base_url):
        invalid = get_json(f"{base_url}/api/project")
    assert invalid["ok"] is False
    assert invalid["issues"]


def test_static_frontend_and_built_asset_are_served(tmp_path) -> None:
    with running_ui(tmp_path) as (_server, base_url):
        with urlopen(f"{base_url}/", timeout=2) as response:
            html = response.read().decode("utf-8")
            assert response.headers.get_content_type() == "text/html"
            assert int(response.headers["Content-Length"]) == len(html.encode("utf-8"))

        asset_path = re.search(r'(?:src|href)="(/assets/[^"]+)"', html)
        assert asset_path is not None
        with urlopen(f"{base_url}{asset_path.group(1)}", timeout=2) as response:
            assert int(response.headers["Content-Length"]) > 0


def test_missing_static_resource_returns_404(tmp_path) -> None:
    with running_ui(tmp_path) as (_server, base_url):
        for path in ("/missing.js", "/%2e%2e/README.md"):
            try:
                urlopen(f"{base_url}{path}", timeout=2)
            except HTTPError as error:
                assert error.code == 404
            else:
                raise AssertionError(
                    f"unsafe or missing static resource unexpectedly succeeded: {path}"
                )


def test_non_get_methods_return_405(tmp_path) -> None:
    with running_ui(tmp_path) as (_server, base_url):
        request = Request(
            f"{base_url}/api/project",
            data=b"{}",
            method="POST",
        )
        try:
            urlopen(request, timeout=2)
        except HTTPError as error:
            assert error.code == 405
            assert error.headers["Allow"] == "GET"
        else:
            raise AssertionError("POST unexpectedly succeeded")
