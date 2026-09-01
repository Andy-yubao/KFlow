"""Revision token tests for automatic Human Interface updates."""

import os
import subprocess
from pathlib import Path

import pytest

from kflow.core.operations import add_derivation, add_node
from kflow.core.query import query_project_graph
from kflow.core.scan import confirm
from kflow.core.storage import initialize_project
from kflow.human import revision
from kflow.human.revision import (
    RevisionTracker,
    git_revision,
    metadata_revision,
    project_revision,
)


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


def test_steady_revision_probe_does_not_read_contents_or_query_the_graph(
    tmp_path, monkeypatch
) -> None:
    registered = tmp_path / "registered.md"
    registered.write_text("registered", encoding="utf-8")
    initialize_project(tmp_path)
    add_node(tmp_path, "registered", ("registered.md",))
    tracker = _tracker(tmp_path)
    first = tracker.result()

    monkeypatch.setattr(
        Path,
        "read_bytes",
        lambda _path: pytest.fail("revision probe must not read file contents"),
    )
    monkeypatch.setattr(
        revision,
        "query_project_graph",
        lambda _root: pytest.fail("unchanged metadata must not reload the graph"),
    )

    assert tracker.result() == first


def test_metadata_change_refreshes_registered_scope_and_removes_deleted_nodes(
    tmp_path, monkeypatch
) -> None:
    first_file = tmp_path / "first.md"
    second_file = tmp_path / "second.md"
    first_file.write_text("first", encoding="utf-8")
    second_file.write_text("second", encoding="utf-8")
    initialize_project(tmp_path)
    add_node(tmp_path, "first", ("first.md",))
    tracker = _tracker(tmp_path)
    original_query = revision.query_project_graph
    calls: list[Path] = []

    def counted_query(root: Path) -> dict:
        calls.append(root)
        return original_query(root)

    monkeypatch.setattr(revision, "query_project_graph", counted_query)
    second = add_node(tmp_path, "second", ("second.md",))
    after_add = tracker.result()["project_revision"]
    assert calls == [tmp_path.resolve()]

    second_file.write_text("second changed and longer", encoding="utf-8")
    after_registered_change = tracker.result()["project_revision"]
    assert after_registered_change != after_add
    assert calls == [tmp_path.resolve()]

    (tmp_path / ".kflow" / "nodes" / f"{second.id}.json").unlink()
    after_remove = tracker.result()["project_revision"]
    assert len(calls) == 2
    second_file.write_text("now ignored", encoding="utf-8")
    assert tracker.result()["project_revision"] == after_remove


def test_missing_registered_file_creation_and_deletion_change_revision(
    tmp_path,
) -> None:
    initialize_project(tmp_path)
    missing = tmp_path / "missing.md"
    missing.write_text("initial", encoding="utf-8")
    add_node(tmp_path, "missing", ("missing.md",))
    tracker = _tracker(tmp_path)
    missing.unlink()
    before = tracker.result()["project_revision"]

    missing.write_text("created", encoding="utf-8")
    created = tracker.result()["project_revision"]
    missing.unlink()

    assert created != before
    assert tracker.result()["project_revision"] != created


def test_project_revision_is_independent_of_registered_path_order(tmp_path) -> None:
    initialize_project(tmp_path)
    for name in ("a.md", "b.md"):
        (tmp_path / name).write_text(name, encoding="utf-8")

    assert project_revision(tmp_path, ["b.md", "a.md"]) == project_revision(
        tmp_path, ["a.md", "b.md"]
    )


def test_metadata_revision_is_independent_of_directory_traversal_order(
    tmp_path, monkeypatch
) -> None:
    initialize_project(tmp_path)
    for name in ("z.json", "a.json"):
        (tmp_path / ".kflow" / "confirmations" / name).write_text(
            "{}", encoding="utf-8"
        )
    expected = metadata_revision(tmp_path)
    original_iterdir = Path.iterdir

    def reversed_iterdir(path: Path):
        return iter(reversed(list(original_iterdir(path))))

    monkeypatch.setattr(Path, "iterdir", reversed_iterdir)
    assert metadata_revision(tmp_path) == expected


def test_manifest_stat_change_updates_project_revision(tmp_path) -> None:
    initialize_project(tmp_path)
    tracker = _tracker(tmp_path)
    before = tracker.result()["project_revision"]

    (tmp_path / ".kflow" / "project.json").write_text(
        '{"kind":"kflow-project","schema_version":1}\n', encoding="utf-8"
    )

    assert tracker.result()["project_revision"] != before


def test_unsafe_outside_symlink_is_never_read(tmp_path, monkeypatch) -> None:
    outside = tmp_path.parent / f"{tmp_path.name}-outside.txt"
    outside.write_text("outside secret", encoding="utf-8")
    link = tmp_path / "outside-link.txt"
    try:
        os.symlink(outside, link)
    except OSError as error:
        pytest.skip(f"symlink creation is unavailable: {error}")
    initialize_project(tmp_path)
    monkeypatch.setattr(
        Path,
        "read_bytes",
        lambda _path: pytest.fail("revision probe must never read a symlink target"),
    )

    assert project_revision(tmp_path, ["outside-link.txt"])


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


def test_git_revision_is_stable_outside_git_and_covers_branch_identity(
    tmp_path,
) -> None:
    assert git_revision(tmp_path) == git_revision(tmp_path)

    _git(tmp_path, "init")
    _git(tmp_path, "config", "user.email", "kflow@example.com")
    _git(tmp_path, "config", "user.name", "KFlow Test")
    (tmp_path / "tracked.txt").write_text("tracked", encoding="utf-8")
    _git(tmp_path, "add", "tracked.txt")
    _git(tmp_path, "commit", "-m", "initial")
    first_branch = git_revision(tmp_path)
    _git(tmp_path, "checkout", "-b", "other-branch")

    assert git_revision(tmp_path) != first_branch
