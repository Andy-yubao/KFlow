"""Real Git integration tests for the HEAD project snapshot."""

import subprocess
from pathlib import Path

from kflow.core.models import Derivation, DerivationInput, DerivationOutput
from kflow.core.operations import add_node
from kflow.core.query import query_project_graph
from kflow.core.scan import confirm
from kflow.core.storage import initialize_project, load_graph, save_derivation
from kflow.human import git_snapshot
from kflow.human.git_snapshot import graph_diff_against_head, load_head_snapshot


def _git(root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-C", str(root), *args],
        check=True,
        capture_output=True,
        text=True,
    )


def _committed_project(root: Path, project_relative: str = "."):
    root.mkdir(parents=True, exist_ok=True)
    _git(root, "init")
    _git(root, "config", "user.name", "KFlow Tests")
    _git(root, "config", "user.email", "kflow@example.invalid")
    project = root if project_relative == "." else root / project_relative
    project.mkdir(parents=True, exist_ok=True)
    docs = project / "docs"
    docs.mkdir()
    (docs / "a.md").write_text("A", encoding="utf-8")
    (docs / "b.md").write_text("B", encoding="utf-8")
    initialize_project(project)
    node_a = add_node(project, "A", ("docs/a.md",))
    node_b = add_node(project, "B", ("docs/b.md",))
    derivation = Derivation(
        "dv_design",
        "A creates B",
        "Initial detail.",
        (DerivationInput(node_a.id, "Use A", ""),),
        (DerivationOutput(node_b.id, "Create B", ""),),
    )
    save_derivation(project, derivation)
    confirm(project, node_a.id)
    confirm(project, node_b.id)
    _git(root, "add", ".")
    _git(root, "commit", "-m", "baseline graph")
    return project, node_a, node_b


def test_head_snapshot_reports_commit_and_cleans_temporary_tree(tmp_path, monkeypatch):
    project, _node_a, _node_b = _committed_project(tmp_path / "repo")
    captured_roots: list[Path] = []
    real_query = query_project_graph

    def capture_query(root):
        captured_roots.append(Path(root))
        return real_query(root)

    monkeypatch.setattr(git_snapshot, "query_project_graph", capture_query)

    snapshot = load_head_snapshot(project)

    assert snapshot.base.revision == "HEAD"
    assert len(snapshot.base.commit) == 40
    assert snapshot.base.short_commit == snapshot.base.commit[:7]
    assert snapshot.base.subject == "baseline graph"
    assert snapshot.graph["ok"] is True
    assert captured_roots
    assert not captured_roots[0].exists()


def test_diff_against_head_detects_added_node_changed_derivation_and_topology(tmp_path):
    project, node_a, _node_b = _committed_project(tmp_path / "repo")
    (project / "docs/c.md").write_text("C", encoding="utf-8")
    node_c = add_node(project, "C", ("docs/c.md",))
    current = load_graph(project)
    original = current.derivations["dv_design"]
    save_derivation(
        project,
        Derivation(
            original.id,
            "A creates B and C",
            "Changed in the working tree.",
            original.inputs,
            (
                *original.outputs,
                DerivationOutput(node_c.id, "Create C", "New role."),
            ),
        ),
    )
    before_status = _git(project, "status", "--porcelain").stdout

    result = graph_diff_against_head(project)

    assert result["available"] is True
    assert result["base"]["subject"] == "baseline graph"
    assert result["summary"]["added_nodes"] == 1
    assert result["nodes"]["added"][0]["id"] == node_c.id
    assert result["summary"]["changed_derivations"] == 1
    assert result["derivations"]["changed"][0]["id"] == "dv_design"
    assert result["summary"]["topology_changed"] is True
    assert _git(project, "status", "--porcelain").stdout == before_status
    assert node_a.id in result["before_topological_order"]


def test_snapshot_supports_kflow_project_inside_git_repository(tmp_path):
    project, node_a, _node_b = _committed_project(tmp_path / "repo", "packages/docs")

    snapshot = load_head_snapshot(project)

    assert snapshot.graph["ok"] is True
    assert snapshot.graph["nodes"][0]["id"] == node_a.id


def test_non_git_no_head_and_git_failure_are_structured_unavailable(
    tmp_path, monkeypatch
):
    non_git = tmp_path / "non-git"
    non_git.mkdir()
    initialize_project(non_git)
    result = graph_diff_against_head(non_git)
    assert result["available"] is False
    assert result["issues"][0]["code"] == "git_history_unavailable"

    empty_repo = tmp_path / "empty-repo"
    empty_repo.mkdir()
    _git(empty_repo, "init")
    initialize_project(empty_repo)
    result = graph_diff_against_head(empty_repo)
    assert result["available"] is False
    assert result["issues"][0]["code"] == "git_history_unavailable"

    project, _node_a, _node_b = _committed_project(tmp_path / "failing-repo")

    def fail_git(*_args, **_kwargs):
        return subprocess.CompletedProcess([], 128, b"", b"simulated git failure")

    monkeypatch.setattr(git_snapshot, "_run_git", fail_git)
    result = graph_diff_against_head(project)
    assert result["available"] is False
    assert result["issues"][0]["code"] == "git_history_unavailable"
    assert "simulated git failure" in result["issues"][0]["message"]
