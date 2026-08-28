"""Read the fixed Git HEAD snapshot and compare it with the live project graph."""

from __future__ import annotations

import io
import subprocess
import tarfile
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from tempfile import TemporaryDirectory

from kflow.core.query import ProjectGraphResult, query_project_graph
from kflow.human.graph_diff import (
    GRAPH_DIFF_SCHEMA_VERSION,
    GraphDiffBase,
    GraphDiffResult,
    compare_project_graphs,
    unavailable_graph_diff,
)


class GitSnapshotError(RuntimeError):
    """Expected inability to construct a valid graph from Git HEAD."""


@dataclass(frozen=True, slots=True)
class HeadSnapshot:
    base: SnapshotBase
    graph: ProjectGraphResult


@dataclass(frozen=True, slots=True)
class SnapshotBase:
    revision: str
    commit: str
    short_commit: str
    subject: str

    def as_result(self) -> GraphDiffBase:
        return {
            "revision": self.revision,
            "commit": self.commit,
            "short_commit": self.short_commit,
            "subject": self.subject,
        }


def graph_diff_against_head(root: Path) -> GraphDiffResult:
    """Compare the current public graph with a public graph rebuilt from HEAD."""
    live_graph = query_project_graph(root)
    if not live_graph["ok"]:
        return unavailable_graph_diff(
            "current_graph_invalid",
            "Graph Diff is unavailable because the current project graph has issues.",
        )
    try:
        snapshot = load_head_snapshot(root)
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
    """Archive HEAD into a disposable directory and query its public project graph."""
    project_root = Path(root).resolve()
    repository_root = _repository_root(project_root)
    try:
        project_relative = project_root.relative_to(repository_root)
    except ValueError as error:
        raise GitSnapshotError(
            "KFlow project is outside the Git repository."
        ) from error

    commit_result = _run_git(
        repository_root,
        "show",
        "-s",
        "--format=%H%x00%h%x00%s",
        "HEAD",
    )
    commit_output = _require_git_success(commit_result, "read HEAD commit")
    commit_fields = commit_output.rstrip(b"\r\n").split(b"\0", 2)
    if len(commit_fields) != 3:
        raise GitSnapshotError("Git returned invalid HEAD commit information.")
    base = SnapshotBase(
        revision="HEAD",
        commit=_decode_git(commit_fields[0]),
        short_commit=_decode_git(commit_fields[1]),
        subject=_decode_git(commit_fields[2]),
    )

    archive_result = _run_git(repository_root, "archive", "--format=tar", "HEAD")
    archive = _require_git_success(archive_result, "archive HEAD")
    with TemporaryDirectory(prefix="kflow-head-") as temporary:
        snapshot_root = Path(temporary)
        _extract_git_archive(archive, snapshot_root)
        snapshot_project = snapshot_root / project_relative
        graph = query_project_graph(snapshot_project)
        if not graph["ok"]:
            message = (
                graph["issues"][0]["message"] if graph["issues"] else "unknown issue"
            )
            raise GitSnapshotError(
                f"HEAD does not contain a valid KFlow project graph: {message}"
            )
    return HeadSnapshot(base=base, graph=graph)


def _repository_root(project_root: Path) -> Path:
    result = _run_git(project_root, "rev-parse", "--show-toplevel")
    output = _require_git_success(result, "locate the Git repository")
    value = _decode_git(output).strip()
    if not value:
        raise GitSnapshotError("Git did not report a repository root.")
    return Path(value).resolve()


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
        raise GitSnapshotError(
            f"Unable to extract the HEAD archive: {error}"
        ) from error
