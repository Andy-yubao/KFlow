"""Revision token tests for automatic Human Interface updates."""

import subprocess
from pathlib import Path

from kflow.core.operations import add_derivation, add_node
from kflow.core.query import query_project_graph
from kflow.core.scan import confirm
from kflow.core.storage import initialize_project
from kflow.human.revision import RevisionTracker


def _tracker(root: Path) -> RevisionTracker:
    tracker = RevisionTracker(root)
    tracker.observe_project_graph(query_project_graph(root))
    return tracker


def _git(root: Path, *arguments: str) -> None:
    subprocess.run(["git", *arguments], cwd=root, check=True, capture_output=True)


def test_project_revision_is_stable_and_ignores_unregistered_files(tmp_path) -> None:
    registered = tmp_path / "registered.md"
    registered.write_text("registered", encoding="utf-8")
    initialize_project(tmp_path)
    add_node(tmp_path, "registered", ("registered.md",))
    tracker = _tracker(tmp_path)

    first = tracker.result()["project_revision"]
    assert tracker.result()["project_revision"] == first

    (tmp_path / "notes.md").write_text("not registered", encoding="utf-8")
    assert tracker.result()["project_revision"] == first

    registered.write_text("changed", encoding="utf-8")
    assert tracker.result()["project_revision"] != first


def test_project_revision_covers_confirmations_nodes_and_derivations(tmp_path) -> None:
    for name in ("source", "output"):
        (tmp_path / f"{name}.md").write_text(name, encoding="utf-8")
    initialize_project(tmp_path)
    source = add_node(tmp_path, "source", ("source.md",))
    tracker = _tracker(tmp_path)
    node_revision = tracker.result()["project_revision"]

    output = add_node(tmp_path, "output", ("output.md",))
    after_node = tracker.result()["project_revision"]
    assert after_node != node_revision

    add_derivation(
        tmp_path,
        "derive output",
        "",
        ((source.id, "input", ""),),
        ((output.id, "output", ""),),
    )
    after_derivation = tracker.result()["project_revision"]
    assert after_derivation != after_node

    confirm(tmp_path, source.id)
    assert tracker.result()["project_revision"] != after_derivation


def test_git_revision_changes_when_head_changes(tmp_path) -> None:
    initialize_project(tmp_path)
    _git(tmp_path, "init")
    _git(tmp_path, "config", "user.email", "kflow@example.com")
    _git(tmp_path, "config", "user.name", "KFlow Test")
    _git(tmp_path, "add", ".kflow")
    _git(tmp_path, "commit", "-m", "initialize")
    tracker = _tracker(tmp_path)
    first = tracker.result()["git_revision"]

    (tmp_path / "ordinary.md").write_text("ordinary", encoding="utf-8")
    _git(tmp_path, "add", "ordinary.md")
    _git(tmp_path, "commit", "-m", "ordinary change")

    assert tracker.result()["git_revision"] != first
