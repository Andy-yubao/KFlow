"""Deterministic, lightweight change tokens for the Human Interface."""

from __future__ import annotations

import hashlib
import json
import stat
import subprocess
import threading
from pathlib import Path, PurePosixPath
from typing import Iterable

from kflow.core.query import query_project_graph
from kflow.human.processes import hidden_subprocess_kwargs


class RevisionTracker:
    """Track registered file scope without caching a second project graph."""

    def __init__(self, root: Path) -> None:
        self.root = Path(root).resolve()
        self._registered_files: tuple[str, ...] = ()
        self._metadata_revision: str | None = None
        self._observed = False
        self._lock = threading.RLock()

    def observe_project_graph(self, result: dict) -> None:
        """Remember only registered paths returned by the public graph query."""
        with self._lock:
            self._observe_project_graph(result, metadata_revision(self.root))

    def _observe_project_graph(self, result: dict, revision: str) -> None:
        registered = {
            path
            for node in result.get("nodes", ())
            if isinstance(node, dict)
            for path in node.get("files", ())
            if isinstance(path, str)
        }
        self._registered_files = tuple(sorted(registered))
        self._metadata_revision = revision
        self._observed = True

    @property
    def observed(self) -> bool:
        with self._lock:
            return self._observed

    def result(self) -> dict[str, str | bool]:
        with self._lock:
            current_metadata_revision = metadata_revision(self.root)
            if (
                not self._observed
                or current_metadata_revision != self._metadata_revision
            ):
                self._observe_project_graph(
                    query_project_graph(self.root), current_metadata_revision
                )
            registered_files = self._registered_files
            project_token = project_revision(
                self.root,
                registered_files,
                _metadata_revision=current_metadata_revision,
            )
        return {
            "ok": True,
            "project_revision": project_token,
            "git_revision": git_revision(self.root),
        }


def project_revision(
    root: Path,
    registered_files: Iterable[str],
    *,
    _metadata_revision: str | None = None,
) -> str:
    """Hash metadata and registered-path stat probes in a stable order."""
    project_root = Path(root).resolve()
    value = {
        "metadata": _metadata_revision or metadata_revision(project_root),
        "registered": [
            _registered_probe(project_root, registered)
            for registered in sorted(set(registered_files))
        ],
    }
    return _hash_json(value)


def metadata_revision(root: Path) -> str:
    """Hash the stat surface that can change the public graph's path scope."""
    project_root = Path(root).resolve()
    metadata = project_root / ".kflow"
    probes = [
        _path_probe(project_root, ".kflow/project.json", metadata / "project.json")
    ]
    for directory in ("nodes", "derivations", "confirmations"):
        base = metadata / directory
        probes.extend(_metadata_tree_probes(project_root, base))
    return _hash_json(probes)


def git_revision(root: Path) -> str:
    """Hash only lightweight current branch identity and HEAD information."""
    project_root = Path(root).resolve()
    return _hash_json(
        {
            "branch": _git_text(project_root, "symbolic-ref", "--quiet", "HEAD"),
            "head": _git_text(project_root, "rev-parse", "--verify", "HEAD"),
        }
    )


def _metadata_tree_probes(root: Path, base: Path) -> list[dict[str, object]]:
    probes: list[dict[str, object]] = []

    def visit(path: Path) -> None:
        label = path.relative_to(root).as_posix()
        probe = _path_probe(root, label, path)
        probes.append(probe)
        if probe["type"] != "directory":
            return
        try:
            children = sorted(path.iterdir(), key=lambda child: child.name)
        except OSError:
            probes.append({"path": f"{label}/", "type": "unreadable-directory"})
            return
        for child in children:
            visit(child)

    visit(base)
    return probes


def _registered_probe(root: Path, value: str) -> dict[str, object]:
    relative = _safe_relative_path(value)
    if relative is None:
        return {"path": value, "type": "invalid-registered-path"}
    normalized = relative.as_posix()
    return _path_probe(root, normalized, root.joinpath(*relative.parts))


def _path_probe(root: Path, label: str, path: Path) -> dict[str, object]:
    probe: dict[str, object] = {"path": label}
    try:
        link_stat = path.lstat()
    except FileNotFoundError:
        probe["type"] = "missing"
        return probe
    except OSError:
        probe["type"] = "unreadable"
        return probe

    probe.update({"size": link_stat.st_size, "mtime_ns": link_stat.st_mtime_ns})
    is_symlink = stat.S_ISLNK(link_stat.st_mode)
    try:
        resolved = path.resolve(strict=True)
        resolved.relative_to(root)
    except (OSError, ValueError):
        probe["type"] = "unsafe-symlink" if is_symlink else "unsafe"
        return probe

    try:
        target_stat = resolved.stat()
    except OSError:
        probe["type"] = "unreadable-target" if is_symlink else "unreadable"
        return probe

    target_type = _file_type(target_stat.st_mode)
    if is_symlink:
        probe.update(
            {
                "type": f"symlink-{target_type}",
                "target_size": target_stat.st_size,
                "target_mtime_ns": target_stat.st_mtime_ns,
            }
        )
    else:
        probe["type"] = target_type
    return probe


def _file_type(mode: int) -> str:
    if stat.S_ISREG(mode):
        return "file"
    if stat.S_ISDIR(mode):
        return "directory"
    return "other"


def _safe_relative_path(value: str) -> PurePosixPath | None:
    relative = PurePosixPath(value)
    if (
        not relative.parts
        or relative.is_absolute()
        or "\\" in value
        or any(part in {"", ".", ".."} for part in relative.parts)
    ):
        return None
    return relative


def _hash_json(value: object) -> str:
    encoded = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _git_text(root: Path, *arguments: str) -> str | None:
    try:
        result = subprocess.run(
            ["git", *arguments],
            cwd=root,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            check=False,
            text=True,
            encoding="utf-8",
            errors="replace",
            **hidden_subprocess_kwargs(),
        )
    except (OSError, subprocess.SubprocessError):
        return None
    return result.stdout.strip() if result.returncode == 0 else None
