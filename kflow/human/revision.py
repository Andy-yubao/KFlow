"""Deterministic, lightweight change tokens for the Human Interface."""

from __future__ import annotations

import hashlib
import json
import subprocess
import threading
from pathlib import Path, PurePosixPath
from typing import Iterable

from kflow.human.git_snapshot import query_git_history


class RevisionTracker:
    """Track the public graph's registered file scope without caching graph facts."""

    def __init__(self, root: Path) -> None:
        self.root = Path(root).resolve()
        self._registered_files: tuple[str, ...] = ()
        self._observed = False
        self._lock = threading.Lock()

    def observe_project_graph(self, result: dict) -> None:
        """Remember only registered paths returned by the public graph query."""
        registered = {
            path
            for node in result.get("nodes", ())
            if isinstance(node, dict)
            for path in node.get("files", ())
            if isinstance(path, str)
        }
        with self._lock:
            self._registered_files = tuple(sorted(registered))
            self._observed = True

    @property
    def observed(self) -> bool:
        with self._lock:
            return self._observed

    def result(self) -> dict[str, str | bool]:
        with self._lock:
            registered_files = self._registered_files
        return {
            "ok": True,
            "project_revision": project_revision(self.root, registered_files),
            "git_revision": git_revision(self.root),
        }


def project_revision(root: Path, registered_files: Iterable[str]) -> str:
    """Hash KFlow facts plus registered file bytes in a stable order."""
    project_root = Path(root).resolve()
    hasher = hashlib.sha256()
    metadata = project_root / ".kflow"
    paths: list[tuple[str, Path]] = [(".kflow/project.json", metadata / "project.json")]
    for directory in ("nodes", "derivations", "confirmations"):
        base = metadata / directory
        if base.is_dir():
            paths.extend(
                (path.relative_to(project_root).as_posix(), path)
                for path in base.rglob("*")
                if path.is_file()
            )
        else:
            paths.append((f".kflow/{directory}", base))

    for value in registered_files:
        relative = _safe_relative_path(value)
        if relative is None:
            paths.append((f"registered-invalid:{value}", project_root / "."))
            continue
        paths.append((relative.as_posix(), project_root.joinpath(*relative.parts)))

    for label, path in sorted(paths, key=lambda item: item[0]):
        _update_file_hash(hasher, project_root, label, path)
    return hasher.hexdigest()


def git_revision(root: Path) -> str:
    """Hash current branch identity, HEAD, and the structural history listing."""
    project_root = Path(root).resolve()
    branch = _git_text(project_root, "symbolic-ref", "--quiet", "HEAD")
    head = _git_text(project_root, "rev-parse", "--verify", "HEAD")
    history = query_git_history(project_root)
    value = {
        "branch": branch,
        "head": head,
        "history": history,
    }
    encoded = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


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


def _update_file_hash(
    hasher: "hashlib._Hash", root: Path, label: str, path: Path
) -> None:
    hasher.update(label.encode("utf-8", errors="surrogatepass"))
    hasher.update(b"\0")
    try:
        resolved = path.resolve(strict=True)
        resolved.relative_to(root)
        if not resolved.is_file():
            raise OSError("not a regular file")
        content = resolved.read_bytes()
    except (OSError, ValueError):
        hasher.update(b"missing-or-unsafe\0")
        return
    hasher.update(str(len(content)).encode("ascii"))
    hasher.update(b"\0")
    hasher.update(content)
    hasher.update(b"\0")


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
        )
    except (OSError, subprocess.SubprocessError):
        return None
    return result.stdout.strip() if result.returncode == 0 else None
