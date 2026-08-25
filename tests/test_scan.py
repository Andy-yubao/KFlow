import json

from kflow.core.graph import KnowledgeGraph
from kflow.core.models import KnowledgeNode
from kflow.core.scan import confirm, scan_and_sync
from kflow.core.storage import initialize_project, save_graph, save_node


def prepare_project(tmp_path) -> KnowledgeNode:
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "managed.md").write_text("one", encoding="utf-8")
    node = KnowledgeNode("nd_managed", "managed", ("docs/managed.md",))
    initialize_project(tmp_path)
    save_graph(tmp_path, KnowledgeGraph.build((node,), ()))
    confirm(tmp_path, node.id)
    return node


def test_scan_reports_modified_file_and_updates_fingerprint_cache(tmp_path):
    prepare_project(tmp_path)
    path = tmp_path / "docs/managed.md"
    path.write_text("two", encoding="utf-8")

    first = scan_and_sync(tmp_path)
    cache = json.loads((tmp_path / ".kflow/cache/scan.json").read_text("utf-8"))
    second = scan_and_sync(tmp_path)

    assert first.modified_files == ("docs/managed.md",)
    assert first.scanned.statuses["nd_managed"].reasons == ("files_changed",)
    observed = first.scanned.file_fingerprints["docs/managed.md"]
    assert cache["files"]["docs/managed.md"] == {
        "algorithm": observed.algorithm,
        "value": observed.value,
    }
    assert second.modified_files == ()
    assert second.unchanged_files == ("docs/managed.md",)


def test_scan_reports_newly_managed_file_as_added(tmp_path):
    node = prepare_project(tmp_path)
    (tmp_path / "docs/new.md").write_text("new", encoding="utf-8")
    save_node(
        tmp_path,
        KnowledgeNode(node.id, node.name, (*node.files, "docs/new.md")),
    )

    result = scan_and_sync(tmp_path)

    assert result.added_files == ("docs/new.md",)
    assert result.scanned.statuses[node.id].reasons == ("files_changed",)


def test_scan_reports_deleted_file_as_issue_and_change(tmp_path):
    prepare_project(tmp_path)
    scan_and_sync(tmp_path)
    (tmp_path / "docs/managed.md").unlink()

    result = scan_and_sync(tmp_path)

    assert result.deleted_files == ("docs/managed.md",)
    assert [issue.code for issue in result.scanned.issues] == ["missing_file"]
    assert result.scanned.statuses == {}
