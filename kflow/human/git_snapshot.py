"""Read-only Git history and revision snapshots for Human Interface diffs."""

from __future__ import annotations

import io
import re
import subprocess
import tarfile
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from tempfile import TemporaryDirectory
from typing import TypedDict

from kflow.core.query import ProjectGraphResult, QueryIssue, query_project_graph
from kflow.human.graph_diff import (
    GRAPH_DIFF_SCHEMA_VERSION,
    GraphDiffBase,
    GraphDiffResult,
    compare_project_graphs,
    unavailable_graph_diff,
)


GIT_HISTORY_SCHEMA_VERSION = 1
DEFAULT_HISTORY_LIMIT = 30
MAX_HISTORY_LIMIT = 100
_HEX_OBJECT_ID = re.compile(r"[0-9a-fA-F]+\Z")


class GitSnapshotError(RuntimeError):
    """Expected inability to construct a valid graph from Git history."""


class GitHistoryCommit(TypedDict):
    commit: str
    short_commit: str
    subject: str
    committed_at: str


class GitHistoryResult(TypedDict):
    ok: bool
    available: bool
    schema_version: int
    head: GitHistoryCommit | None
    commits: list[GitHistoryCommit]
    issues: list[QueryIssue]


@dataclass(frozen=True, slots=True)
class SnapshotBase:
    reference: str
    commit: str
    short_commit: str
    subject: str
    committed_at: str

    def as_result(self) -> GraphDiffBase:
        return {
            "reference": self.reference,
            "commit": self.commit,
            "short_commit": self.short_commit,
            "subject": self.subject,
            "committed_at": self.committed_at,
        }

    def as_history_commit(self) -> GitHistoryCommit:
        return {
            "commit": self.commit,
            "short_commit": self.short_commit,
            "subject": self.subject,
            "committed_at": self.committed_at,
        }


@dataclass(frozen=True, slots=True)
class RevisionSnapshot:
    base: SnapshotBase
    graph: ProjectGraphResult


HeadSnapshot = RevisionSnapshot


def graph_diff_against_head(root: Path) -> GraphDiffResult:
    """Compare the current public graph with a graph rebuilt from Git HEAD."""
    return graph_diff_against_revision(root)


def graph_diff_against_revision(
    root: Path, revision: str | None = None
) -> GraphDiffResult:
    """Compare the current public graph with HEAD or one full ancestor commit."""
    live_graph = query_project_graph(root)
    if not live_graph["ok"]:
        return unavailable_graph_diff(
            "current_graph_invalid",
            "Graph Diff is unavailable because the current project graph has issues.",
        )
    reference = "HEAD" if revision is None else revision
    try:
        snapshot = load_revision_snapshot(root, reference)
    except (GitSnapshotError, OSError, subprocess.SubprocessError) as error:
        return unavailable_graph_diff("git_history_unavailable", str(error))

    comparison = compare_project_graphs(snapshot.graph, live_graph)
    return {
        "ok": True,
        "available": True,
        "schema_version": GRAPH_DIFF_SCHEMA_VERSION,
        "base": snapshot.base.as_result(),
        **comparison,
        "issues": [],
    }


def load_head_snapshot(root: Path) -> HeadSnapshot:
    """Compatibility wrapper for the default HEAD snapshot."""
    return load_revision_snapshot(root, "HEAD")


def load_revision_snapshot(root: Path, revision: str) -> RevisionSnapshot:
    """Archive an allowed commit and query its public graph in a temporary tree."""
    project_root = Path(root).resolve()
    repository_root = _repository_root(project_root)
    project_relative = _project_relative_path(project_root, repository_root)
    base = _resolve_snapshot_base(repository_root, revision)

    archive_result = _run_git(repository_root, "archive", "--format=tar", base.commit)
    archive = _require_git_success(archive_result, f"archive {base.short_commit}")
    with TemporaryDirectory(prefix="kflow-revision-") as temporary:
        snapshot_root = Path(temporary)
        _extract_git_archive(archive, snapshot_root)
        snapshot_project = snapshot_root / project_relative
        graph = query_project_graph(snapshot_project)
        if not graph["ok"]:
            message = (
                graph["issues"][0]["message"] if graph["issues"] else "unknown issue"
            )
            raise GitSnapshotError(
                f"Commit {base.short_commit} does not contain a valid KFlow "
                f"project graph: {message}"
            )
    return RevisionSnapshot(base=base, graph=graph)


def query_git_history(
    root: Path, limit: int = DEFAULT_HISTORY_LIMIT
) -> GitHistoryResult:
    """List HEAD-reachable commits that modified public graph structure."""
    if (
        isinstance(limit, bool)
        or not isinstance(limit, int)
        or not 1 <= limit <= MAX_HISTORY_LIMIT
    ):
        raise ValueError(f"history limit must be between 1 and {MAX_HISTORY_LIMIT}")

    project_root = Path(root).resolve()
    try:
        repository_root = _repository_root(project_root)
        project_relative = _project_relative_path(project_root, repository_root)
        head = _resolve_snapshot_base(repository_root, "HEAD")
        pathspecs = _structural_pathspecs(project_relative)
        result = _run_git(
            repository_root,
            "log",
            "HEAD",
            f"--max-count={limit + 1}",
            "--format=%H%x00%h%x00%s%x00%cI%x1e",
            "--",
            *pathspecs,
        )
        output = _require_git_success(result, "read KFlow structural history")
        commits = _parse_history_commits(output)
        unique: list[GitHistoryCommit] = []
        seen = {head.commit}
        for commit in commits:
            if commit["commit"] in seen:
                continue
            seen.add(commit["commit"])
            unique.append(commit)
            if len(unique) == limit:
                break
    except (GitSnapshotError, OSError, subprocess.SubprocessError) as error:
        return unavailable_git_history(str(error))

    return {
        "ok": True,
        "available": True,
        "schema_version": GIT_HISTORY_SCHEMA_VERSION,
        "head": head.as_history_commit(),
        "commits": unique,
        "issues": [],
    }


def unavailable_git_history(message: str, *, ok: bool = True) -> GitHistoryResult:
    """Return the stable capability-degradation shape for Git history."""
    return {
        "ok": ok,
        "available": False,
        "schema_version": GIT_HISTORY_SCHEMA_VERSION,
        "head": None,
        "commits": [],
        "issues": [
            {
                "code": "git_history_unavailable" if ok else "invalid_argument",
                "message": message,
                "references": [],
            }
        ],
    }


def is_full_hex_commit_id(value: object) -> bool:
    """Return whether a request has the lexical shape of a commit object ID."""
    return (
        isinstance(value, str) and bool(value) and bool(_HEX_OBJECT_ID.fullmatch(value))
    )


def _resolve_snapshot_base(repository_root: Path, revision: str) -> SnapshotBase:
    if revision == "HEAD":
        resolved = "HEAD"
        reference = "HEAD"
    else:
        if not is_full_hex_commit_id(revision):
            raise GitSnapshotError("Revision must be a full commit object ID.")
        resolve_result = _run_git(
            repository_root, "rev-parse", "--verify", f"{revision}^{{commit}}"
        )
        resolved = _decode_git(
            _require_git_success(resolve_result, "resolve the requested commit")
        ).strip()
        if resolved.lower() != revision.lower():
            raise GitSnapshotError("Revision must be a full commit object ID.")
        ancestor = _run_git(
            repository_root, "merge-base", "--is-ancestor", resolved, "HEAD"
        )
        if ancestor.returncode == 1:
            raise GitSnapshotError(
                "Requested commit is not reachable from the current HEAD."
            )
        _require_git_success(ancestor, "check commit reachability from HEAD")
        reference = revision

    commit_result = _run_git(
        repository_root,
        "show",
        "-s",
        "--format=%H%x00%h%x00%s%x00%cI",
        resolved,
    )
    commit_output = _require_git_success(commit_result, "read commit information")
    fields = commit_output.rstrip(b"\r\n").split(b"\0", 3)
    if len(fields) != 4 or not all(fields[index] for index in (0, 1, 3)):
        raise GitSnapshotError("Git returned invalid commit information.")
    return SnapshotBase(
        reference=reference,
        commit=_decode_git(fields[0]),
        short_commit=_decode_git(fields[1]),
        subject=_decode_git(fields[2]),
        committed_at=_decode_git(fields[3]),
    )


def _parse_history_commits(output: bytes) -> list[GitHistoryCommit]:
    commits: list[GitHistoryCommit] = []
    for record in output.split(b"\x1e"):
        record = record.strip(b"\r\n")
        if not record:
            continue
        fields = record.split(b"\0", 3)
        if len(fields) != 4 or not all(fields[index] for index in (0, 1, 3)):
            raise GitSnapshotError("Git returned invalid structural history data.")
        commits.append(
            {
                "commit": _decode_git(fields[0]),
                "short_commit": _decode_git(fields[1]),
                "subject": _decode_git(fields[2]),
                "committed_at": _decode_git(fields[3]),
            }
        )
    return commits


def _repository_root(project_root: Path) -> Path:
    result = _run_git(project_root, "rev-parse", "--show-toplevel")
    output = _require_git_success(result, "locate the Git repository")
    value = _decode_git(output).strip()
    if not value:
        raise GitSnapshotError("Git did not report a repository root.")
    return Path(value).resolve()


def _project_relative_path(project_root: Path, repository_root: Path) -> Path:
    try:
        return project_root.relative_to(repository_root)
    except ValueError as error:
        raise GitSnapshotError(
            "KFlow project is outside the Git repository."
        ) from error


def _structural_pathspecs(project_relative: Path) -> tuple[str, ...]:
    prefix = "" if project_relative == Path(".") else f"{project_relative.as_posix()}/"
    metadata = f"{prefix}.kflow"
    return (
        f"{metadata}/project.json",
        f"{metadata}/nodes",
        f"{metadata}/derivations",
    )


def _run_git(root: Path, *arguments: str) -> subprocess.CompletedProcess[bytes]:
    try:
        return subprocess.run(
            ["git", "-C", str(root), *arguments],
            check=False,
            capture_output=True,
            shell=False,
        )
    except FileNotFoundError as error:
        raise GitSnapshotError("Git is not installed or is not available.") from error


def _require_git_success(
    result: subprocess.CompletedProcess[bytes], action: str
) -> bytes:
    if result.returncode == 0:
        return result.stdout
    detail = _decode_git(result.stderr).strip() or "unknown Git error"
    raise GitSnapshotError(f"Unable to {action}: {detail}")


def _decode_git(value: bytes) -> str:
    return value.decode("utf-8", errors="replace")


def _extract_git_archive(archive: bytes, destination: Path) -> None:
    try:
        with tarfile.open(fileobj=io.BytesIO(archive), mode="r:") as stream:
            for member in stream.getmembers():
                member_path = PurePosixPath(member.name)
                if member_path.is_absolute() or any(
                    part in {"", ".", ".."} for part in member_path.parts
                ):
                    raise GitSnapshotError("Git archive contains an unsafe path.")
            stream.extractall(destination, filter="data")
    except (tarfile.TarError, OSError) as error:
        raise GitSnapshotError(f"Unable to extract the Git archive: {error}") from error
