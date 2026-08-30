"""Real Git integration tests for revision snapshots and structural history."""

import string
import subprocess
from pathlib import Path

import pytest

from kflow.core.models import Derivation, DerivationInput, DerivationOutput
from kflow.core.operations import add_node
from kflow.core.query import query_project_graph
from kflow.core.scan import confirm
from kflow.core.storage import initialize_project, load_graph, save_derivation
from kflow.human import git_snapshot
from kflow.human.git_snapshot import (
    GitSnapshotError,
    graph_diff_against_head,
    graph_diff_against_revision,
    load_head_snapshot,
    load_revision_snapshot,
    query_git_history,
)


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
    expected = _git(project, "rev-parse", "HEAD").stdout.strip()

    assert snapshot.base.reference == "HEAD"
    assert snapshot.base.commit == expected
    assert snapshot.base.commit
    assert all(character in string.hexdigits for character in snapshot.base.commit)
    assert snapshot.base.short_commit == snapshot.base.commit[:7]
    assert snapshot.base.subject == "baseline graph"
    assert snapshot.base.committed_at
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


def test_history_lists_only_kflow_structure_commits_newest_first_and_honors_limit(
    tmp_path,
):
    project, node_a, _node_b = _committed_project(tmp_path / "repo")
    baseline = _git(project, "rev-parse", "HEAD").stdout.strip()

    node_a_file = project / "docs/a.md"
    node_a_file.write_text("A changed for confirmation", encoding="utf-8")
    confirm(project, node_a.id)
    _git(project, "add", f".kflow/confirmations/{node_a.id}.json")
    _git(project, "commit", "-m", "confirm A only")
    confirmation_only = _git(project, "rev-parse", "HEAD").stdout.strip()
    node_a_file.write_text("A", encoding="utf-8")

    (project / "docs/c.md").write_text("C", encoding="utf-8")
    add_node(project, "C", ("docs/c.md",))
    _git(project, "add", ".kflow", "docs/c.md")
    _git(project, "commit", "-m", "add structural node")
    structural = _git(project, "rev-parse", "HEAD").stdout.strip()

    (project / "docs/a.md").write_text("docs only", encoding="utf-8")
    _git(project, "add", "docs/a.md")
    _git(project, "commit", "-m", "docs only change")
    docs_only = _git(project, "rev-parse", "HEAD").stdout.strip()

    result = query_git_history(project)

    assert result["available"] is True
    assert result["head"]["commit"] == docs_only
    assert [commit["commit"] for commit in result["commits"]] == [
        structural,
        baseline,
    ]
    assert all(commit["subject"] != "docs only change" for commit in result["commits"])
    assert all(commit["commit"] != confirmation_only for commit in result["commits"])
    assert query_git_history(project, limit=1)["commits"] == result["commits"][:1]


def test_history_deduplicates_structural_head_and_supports_subdirectory_projects(
    tmp_path,
):
    project, _node_a, _node_b = _committed_project(tmp_path / "repo", "packages/docs")
    head = _git(project, "rev-parse", "HEAD").stdout.strip()

    result = query_git_history(project)

    assert result["available"] is True
    assert result["head"]["commit"] == head
    assert result["commits"] == []


def test_history_uses_literal_pathspecs_for_special_character_project_paths(
    tmp_path,
):
    repository = tmp_path / "repo"
    project_relative = "packages/[draft] 项目/KFlow 示例"
    project, node_a, _node_b = _committed_project(repository, project_relative)
    baseline = _git(repository, "rev-parse", "HEAD").stdout.strip()

    node_a_file = project / "docs/a.md"
    node_a_file.write_text("A changed for confirmation", encoding="utf-8")
    confirm(project, node_a.id)
    confirmation = project / ".kflow/confirmations" / f"{node_a.id}.json"
    _git(
        repository,
        "add",
        f":(literal){confirmation.relative_to(repository).as_posix()}",
    )
    _git(repository, "commit", "-m", "confirm target only")
    confirmation_only = _git(repository, "rev-parse", "HEAD").stdout.strip()
    node_a_file.write_text("A", encoding="utf-8")

    (project / "docs/c.md").write_text("C", encoding="utf-8")
    add_node(project, "C", ("docs/c.md",))
    _git(repository, "add", f":(literal){project_relative}/.kflow/nodes")
    _git(repository, "add", f":(literal){project_relative}/docs/c.md")
    _git(repository, "commit", "-m", "change target structure")
    target_structural = _git(repository, "rev-parse", "HEAD").stdout.strip()

    decoy_relative = "packages/d 项目/KFlow 示例"
    decoy = repository / Path(decoy_relative)
    (decoy / "docs").mkdir(parents=True)
    (decoy / "docs/decoy.md").write_text("decoy", encoding="utf-8")
    initialize_project(decoy)
    add_node(decoy, "Decoy", ("docs/decoy.md",))
    _git(repository, "add", decoy_relative)
    _git(repository, "commit", "-m", "change pattern-matching decoy structure")
    decoy_structural = _git(repository, "rev-parse", "HEAD").stdout.strip()

    node_a_file.write_text("docs only", encoding="utf-8")
    _git(repository, "add", f":(literal){project_relative}/docs/a.md")
    _git(repository, "commit", "-m", "target docs only")
    docs_only = _git(repository, "rev-parse", "HEAD").stdout.strip()

    result = query_git_history(project)

    assert result["available"] is True
    assert result["head"]["commit"] == docs_only
    assert [commit["commit"] for commit in result["commits"]] == [
        target_structural,
        baseline,
    ]
    excluded = {confirmation_only, decoy_structural, docs_only}
    assert not excluded.intersection(commit["commit"] for commit in result["commits"])


def test_revision_snapshot_and_diff_accept_an_earlier_full_ancestor_commit(tmp_path):
    project, _node_a, _node_b = _committed_project(tmp_path / "repo")
    baseline = _git(project, "rev-parse", "HEAD").stdout.strip()
    (project / "docs/c.md").write_text("C", encoding="utf-8")
    node_c = add_node(project, "C", ("docs/c.md",))
    _git(project, "add", ".kflow", "docs/c.md")
    _git(project, "commit", "-m", "add C")
    before_status = _git(project, "status", "--porcelain").stdout

    snapshot = load_revision_snapshot(project, baseline)
    result = graph_diff_against_revision(project, baseline)

    assert snapshot.base.reference == baseline
    assert snapshot.base.commit == baseline
    assert all(node["id"] != node_c.id for node in snapshot.graph["nodes"])
    assert result["available"] is True
    assert result["base"]["reference"] == baseline
    assert [node["id"] for node in result["nodes"]["added"]] == [node_c.id]
    assert _git(project, "status", "--porcelain").stdout == before_status


def test_revision_snapshot_rejects_abbreviations_missing_commits_and_non_ancestors(
    tmp_path,
):
    project, _node_a, _node_b = _committed_project(tmp_path / "repo")
    head = _git(project, "rev-parse", "HEAD").stdout.strip()

    with pytest.raises(GitSnapshotError, match="full commit object ID"):
        load_revision_snapshot(project, head[:12])

    missing = "f" * len(head)
    assert graph_diff_against_revision(project, missing)["available"] is False

    tree = _git(project, "write-tree").stdout.strip()
    unrelated = _git(project, "commit-tree", tree, "-m", "unrelated").stdout.strip()
    result = graph_diff_against_revision(project, unrelated)
    assert result["available"] is False
    assert "not reachable" in result["issues"][0]["message"]


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
    assert query_git_history(non_git)["available"] is False

    empty_repo = tmp_path / "empty-repo"
    empty_repo.mkdir()
    _git(empty_repo, "init")
    initialize_project(empty_repo)
    result = graph_diff_against_head(empty_repo)
    assert result["available"] is False
    assert result["issues"][0]["code"] == "git_history_unavailable"
    assert query_git_history(empty_repo)["available"] is False

    project, _node_a, _node_b = _committed_project(tmp_path / "failing-repo")

    def fail_git(*_args, **_kwargs):
        return subprocess.CompletedProcess([], 128, b"", b"simulated git failure")

    monkeypatch.setattr(git_snapshot, "_run_git", fail_git)
    result = graph_diff_against_head(project)
    assert result["available"] is False
    assert result["issues"][0]["code"] == "git_history_unavailable"
    assert "simulated git failure" in result["issues"][0]["message"]

    history = query_git_history(project)
    assert history["available"] is False
    assert history["head"] is None
    assert history["commits"] == []
