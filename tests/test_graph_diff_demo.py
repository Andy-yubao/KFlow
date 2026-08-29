"""Automated acceptance coverage for the external Graph Diff demo builder."""

import subprocess

import pytest

from kflow.core.query import query_project_graph
from kflow.core.scan import validate
from scripts.setup_graph_diff_demo import create_demo


def _git(root, *arguments):
    return subprocess.run(
        ["git", "-C", str(root), *arguments],
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    ).stdout.strip()


def test_demo_builder_creates_two_structural_commits_and_exact_worktree_diff(
    tmp_path,
):
    root = tmp_path / "demo"

    result = create_demo(root)

    assert (root / ".git").is_dir()
    assert _git(root, "rev-parse", "HEAD") == result["head"]
    assert len(result["history"]["commits"]) >= 1
    assert len(_git(root, "log", "--format=%H", "--", ".kflow").splitlines()) >= 2
    assert not validate(root)
    assert _git(root, "status", "--porcelain")

    graph = query_project_graph(root)
    assert graph["ok"] is True
    registered = {path for node in graph["nodes"] for path in node["files"]}
    assert "notes/personal-note.md" not in registered

    head_diff = result["head_diff"]
    assert head_diff["summary"] == {
        "added_nodes": 2,
        "removed_nodes": 2,
        "changed_nodes": 1,
        "added_derivations": 1,
        "removed_derivations": 1,
        "changed_derivations": 3,
        "topology_changed": True,
    }
    assert {node["id"] for node in head_diff["nodes"]["added"]} == {
        "nd_api_release_notes",
        "nd_operations_guide",
    }
    assert {node["id"] for node in head_diff["nodes"]["removed"]} == {
        "nd_api_legacy_notes",
        "nd_legacy_reference",
    }
    assert {node["id"] for node in head_diff["nodes"]["changed"]} == {"nd_architecture"}
    assert {item["id"] for item in head_diff["derivations"]["added"]} == {
        "dv_operations"
    }
    assert {item["id"] for item in head_diff["derivations"]["removed"]} == {
        "dv_legacy_reference"
    }
    assert {item["id"] for item in head_diff["derivations"]["changed"]} == {
        "dv_api_design",
        "dv_architecture",
        "dv_delivery",
    }

    assert result["earlier_diff"]["available"] is True
    assert result["earlier_diff"]["base"]["commit"] != result["head"]
    assert result["earlier_diff"]["summary"] != head_diff["summary"]
    assert result["git_status"]


def test_demo_builder_refuses_to_overwrite_an_existing_directory(tmp_path):
    root = tmp_path / "demo"
    root.mkdir()
    marker = root / "keep.txt"
    marker.write_text("keep", encoding="utf-8")

    with pytest.raises(RuntimeError, match="already exists"):
        create_demo(root)

    assert marker.read_text(encoding="utf-8") == "keep"
