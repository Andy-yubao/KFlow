"""Read-only HTTP boundary tests for the Human Interface."""

import json
import re
import threading
from contextlib import contextmanager
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from kflow.core.operations import add_node
from kflow.core.query import query_project_graph, query_review_order
from kflow.core.scan import confirm
from kflow.core.storage import initialize_project
from kflow.human import server as human_server
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


def post_json(url: str, body: object) -> tuple[int, dict]:
    request = Request(
        url,
        data=json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        response = urlopen(request, timeout=2)
    except HTTPError as error:
        return error.code, json.load(error)
    with response:
        return response.status, json.load(response)


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


def test_review_order_endpoint_matches_public_query(tmp_path) -> None:
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "architecture.md").write_text("architecture", encoding="utf-8")
    initialize_project(tmp_path)
    architecture = add_node(tmp_path, "architecture", ("docs/architecture.md",))
    confirm(tmp_path, architecture.id)
    (docs / "architecture.md").write_text("changed", encoding="utf-8")

    with running_ui(tmp_path) as (_server, base_url):
        result = get_json(f"{base_url}/api/review-order")

    assert result == query_review_order(tmp_path)
    assert result["review_order"] == [architecture.id]


def test_graph_diff_endpoint_returns_adapter_json_without_affecting_project(
    tmp_path, monkeypatch
) -> None:
    initialize_project(tmp_path)
    expected = {
        "ok": True,
        "available": False,
        "schema_version": 2,
        "base": None,
        "summary": None,
        "nodes": {"added": [], "removed": [], "changed": []},
        "derivations": {"added": [], "removed": [], "changed": []},
        "before_topological_order": [],
        "after_topological_order": [],
        "issues": [
            {
                "code": "git_history_unavailable",
                "message": "No HEAD commit is available.",
                "references": [],
            }
        ],
    }
    called = []

    def graph_diff(root, base=None):
        called.append((root, base))
        return expected

    monkeypatch.setattr(human_server, "graph_diff_against_revision", graph_diff)

    with running_ui(tmp_path) as (_server, base_url):
        result = get_json(f"{base_url}/api/graph-diff")
        project = get_json(f"{base_url}/api/project")

    assert result == expected
    assert called == [(tmp_path.resolve(), None)]
    assert project == query_project_graph(tmp_path)


def test_git_history_and_selected_graph_diff_endpoints_are_no_store(
    tmp_path, monkeypatch
) -> None:
    initialize_project(tmp_path)
    commit_id = "a1b2c3d4"
    history = {
        "ok": True,
        "available": True,
        "schema_version": 1,
        "head": {
            "commit": "b2c3d4e5",
            "short_commit": "bbbbbbb",
            "subject": "HEAD subject",
            "committed_at": "2026-08-29T10:00:00+08:00",
        },
        "commits": [
            {
                "commit": commit_id,
                "short_commit": "aaaaaaa",
                "subject": "structure subject",
                "committed_at": "2026-08-28T10:00:00+08:00",
            }
        ],
        "issues": [],
    }
    diff = {
        "ok": True,
        "available": False,
        "schema_version": 2,
        "base": None,
        "summary": None,
        "nodes": {"added": [], "removed": [], "changed": []},
        "derivations": {"added": [], "removed": [], "changed": []},
        "before_topological_order": [],
        "after_topological_order": [],
        "issues": [],
    }
    history_calls = []
    diff_calls = []

    def get_history(root, limit=30):
        history_calls.append((root, limit))
        return history

    def get_diff(root, base=None):
        diff_calls.append((root, base))
        return diff

    monkeypatch.setattr(human_server, "query_git_history", get_history)
    monkeypatch.setattr(human_server, "graph_diff_against_revision", get_diff)

    with running_ui(tmp_path) as (_server, base_url):
        assert get_json(f"{base_url}/api/git-history?limit=12") == history
        assert get_json(f"{base_url}/api/graph-diff?base={commit_id}") == diff

    assert history_calls == [(tmp_path.resolve(), 12)]
    assert diff_calls == [(tmp_path.resolve(), commit_id)]


def test_history_queries_reject_invalid_limit_and_base_without_hiding_project(
    tmp_path,
) -> None:
    initialize_project(tmp_path)
    with running_ui(tmp_path) as (_server, base_url):
        for path in (
            "/api/git-history?limit=0",
            "/api/git-history?limit=not-an-integer",
            "/api/graph-diff?base=HEAD~3",
            "/api/graph-diff?base=",
        ):
            try:
                urlopen(f"{base_url}{path}", timeout=2)
            except HTTPError as error:
                assert error.code == 400
                result = json.load(error)
                assert result["ok"] is False
                assert result["available"] is False
                assert result["issues"][0]["code"] == "invalid_argument"
            else:
                raise AssertionError(f"invalid query unexpectedly succeeded: {path}")

        assert get_json(f"{base_url}/api/project") == query_project_graph(tmp_path)


def test_open_file_opens_registered_regular_file(tmp_path, monkeypatch) -> None:
    docs = tmp_path / "docs"
    docs.mkdir()
    registered = docs / "architecture.md"
    registered.write_text("architecture", encoding="utf-8")
    initialize_project(tmp_path)
    add_node(tmp_path, "architecture", ("docs/architecture.md",))
    opened: list[Path] = []
    monkeypatch.setattr(human_server, "_open_registered_file", opened.append)

    with running_ui(tmp_path) as (_server, base_url):
        status, result = post_json(
            f"{base_url}/api/open-file", {"path": "docs/architecture.md"}
        )

    assert status == 200
    assert result == {"ok": True, "path": "docs/architecture.md"}
    assert opened == [registered.resolve()]


def test_open_file_rejects_unregistered_and_unsafe_paths(tmp_path, monkeypatch) -> None:
    docs = tmp_path / "docs"
    docs.mkdir()
    registered = docs / "architecture.md"
    registered.write_text("architecture", encoding="utf-8")
    unregistered = docs / "notes.md"
    unregistered.write_text("notes", encoding="utf-8")
    directory = docs / "folder"
    directory.mkdir()
    initialize_project(tmp_path)
    add_node(tmp_path, "architecture", ("docs/architecture.md",))
    opened: list[Path] = []
    monkeypatch.setattr(human_server, "_open_registered_file", opened.append)

    rejected = (
        "docs/notes.md",
        str(registered.resolve()),
        "../architecture.md",
        "docs/folder",
        "docs/missing.md",
        "https://example.com/architecture.md",
        "docs/architecture.md --unsafe",
    )
    with running_ui(tmp_path) as (_server, base_url):
        for path in rejected:
            status, result = post_json(f"{base_url}/api/open-file", {"path": path})
            assert status == 400
            assert result["ok"] is False
            assert result["path"] == path
            assert result["issues"]
            assert set(result["issues"][0]) == {"code", "message", "references"}

    assert opened == []


def test_open_file_rejects_registered_path_that_is_missing_or_a_directory(
    tmp_path, monkeypatch
) -> None:
    registered = tmp_path / "registered.md"
    registered.write_text("registered", encoding="utf-8")
    initialize_project(tmp_path)
    add_node(tmp_path, "registered", ("registered.md",))
    opened: list[Path] = []
    monkeypatch.setattr(human_server, "_open_registered_file", opened.append)

    registered.unlink()
    with running_ui(tmp_path) as (_server, base_url):
        missing_status, missing = post_json(
            f"{base_url}/api/open-file", {"path": "registered.md"}
        )
    assert missing_status == 400
    assert missing["issues"][0]["code"] == "file_not_found"

    registered.mkdir()
    with running_ui(tmp_path) as (_server, base_url):
        directory_status, directory = post_json(
            f"{base_url}/api/open-file", {"path": "registered.md"}
        )
    assert directory_status == 400
    assert directory["issues"][0]["code"] == "not_regular_file"
    assert opened == []


def test_open_file_rejects_registered_symlink_outside_project(
    tmp_path, monkeypatch
) -> None:
    outside = tmp_path.parent / f"{tmp_path.name}-outside.md"
    outside.write_text("outside", encoding="utf-8")
    link = tmp_path / "linked.md"
    link.write_text("inside", encoding="utf-8")
    initialize_project(tmp_path)
    add_node(tmp_path, "linked", ("linked.md",))
    link.unlink()
    try:
        link.symlink_to(outside)
    except OSError:
        outside.unlink()
        return
    opened: list[Path] = []
    monkeypatch.setattr(human_server, "_open_registered_file", opened.append)
    try:
        with running_ui(tmp_path) as (_server, base_url):
            status, result = post_json(
                f"{base_url}/api/open-file", {"path": "linked.md"}
            )
        assert status == 400
        assert result["issues"][0]["code"] == "path_outside_project"
        assert opened == []
    finally:
        outside.unlink()


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


def test_unknown_post_and_other_unsupported_methods_return_405(tmp_path) -> None:
    with running_ui(tmp_path) as (_server, base_url):
        for request, allow in (
            (Request(f"{base_url}/api/project", data=b"{}", method="POST"), "GET"),
            (
                Request(f"{base_url}/api/graph-diff", data=b"{}", method="POST"),
                "GET",
            ),
            (
                Request(f"{base_url}/api/git-history", data=b"{}", method="POST"),
                "GET",
            ),
            (Request(f"{base_url}/api/open-file", data=b"{}", method="PUT"), "POST"),
            (Request(f"{base_url}/api/open-file", method="GET"), "POST"),
        ):
            try:
                urlopen(request, timeout=2)
            except HTTPError as error:
                assert error.code == 405
                assert error.headers["Allow"] == allow
            else:
                raise AssertionError(f"{request.method} unexpectedly succeeded")
