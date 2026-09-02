"""Acceptance coverage for the optional Git-backed Quickstart demo."""

import subprocess

import pytest

from kflow.core.query import query_project_graph, query_review_order
from kflow.core.scan import validate
from scripts.setup_git_quickstart_demo import create_demo


def _git(root, *arguments):
    return subprocess.run(
        ["git", "-C", str(root), *arguments],
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    ).stdout.strip()


def test_git_quickstart_builds_real_history_diff_and_review_state(tmp_path):
    root = tmp_path / "git quickstart"

    result = create_demo(root)

    assert (root / ".git").is_dir()
    assert len(_git(root, "rev-list", "--all").splitlines()) == 3
    assert _git(root, "rev-parse", "HEAD") == result["head"]
    assert _git(root, "rev-parse", "HEAD~1") == result["refs"]["HEAD~1"]
    assert _git(root, "rev-parse", "HEAD~2") == result["refs"]["HEAD~2"]
    assert _git(root, "log", "--format=%s").splitlines() == [
        "demo: derive deployment and release plans",
        "demo: derive design and testing plans",
        "demo: add project requirements",
    ]
    assert not validate(root)
    assert _git(root, "status", "--short") == result["git_status"]
    assert "docs/requirements.md" in result["git_status"]
    assert "nd_research_notes.json" in result["git_status"]

    graph = query_project_graph(root)
    assert graph["ok"] is True
    assert graph["project"]["node_count"] == 7
    assert graph["project"]["derivation_count"] == 3
    assert graph["project"]["needs_review_count"] == 6
    assert {
        (len(item["inputs"]), len(item["outputs"])) for item in graph["derivations"]
    } == {(1, 1), (1, 2), (2, 1)}

    reasons = {item["name"]: item["reasons"] for item in graph["nodes"]}
    assert reasons == {
        "requirements": ["files_changed"],
        "security-constraints": [],
        "api-design": ["input_changed"],
        "testing-plan": ["input_changed"],
        "deployment-plan": ["input_changed"],
        "release-checklist": ["input_changed"],
        "research-notes": ["unconfirmed"],
    }
    assert query_review_order(root) == result["review_order"]
    assert result["review_order"]["review_order"]

    assert result["history"]["available"] is True
    assert len(result["history"]["commits"]) >= 2
    assert result["head_diff"]["available"] is True
    assert result["head_diff"]["issues"] == []
    assert result["head_diff"]["summary"] == {
        "added_nodes": 1,
        "removed_nodes": 0,
        "changed_nodes": 0,
        "added_derivations": 0,
        "removed_derivations": 0,
        "changed_derivations": 0,
        "topology_changed": True,
    }
    assert {item["id"] for item in result["head_diff"]["nodes"]["added"]} == {
        "nd_research_notes"
    }
    assert all(item["available"] for item in result["historical_diffs"].values())


def test_git_quickstart_is_deterministic(tmp_path):
    first = create_demo(tmp_path / "first")
    second = create_demo(tmp_path / "second")

    assert first["commits"] == second["commits"]
    assert first["head_diff"]["summary"] == second["head_diff"]["summary"]
    assert first["review_order"] == second["review_order"]


def test_git_quickstart_refuses_to_overwrite_existing_content(tmp_path):
    root = tmp_path / "existing"
    root.mkdir()
    marker = root / "keep.txt"
    marker.write_text("keep", encoding="utf-8")

    with pytest.raises(RuntimeError, match="already exists"):
        create_demo(root)

    assert marker.read_text(encoding="utf-8") == "keep"
