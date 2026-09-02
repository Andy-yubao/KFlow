"""Create a clean test clone of the current repository's pushed branch.

This is repository developer tooling, not part of the public KFlow CLI.
"""

from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path


CLONE_ROOT_ENV = "KFLOW_TEST_CLONE_ROOT"


class CloneError(RuntimeError):
    """A safe, user-facing fresh-clone failure."""


@dataclass(frozen=True, slots=True)
class CloneResult:
    source_repo: Path
    branch: str
    origin_url: str
    remote_sha: str
    head_sha: str
    target: Path


def branch_slug(branch: str) -> str:
    """Return a readable branch component that is safe in a directory name."""
    slug = re.sub(r"[^A-Za-z0-9._-]+", "-", branch).strip("._-")
    slug = re.sub(r"-+", "-", slug)
    return slug or "branch"


def default_destination_root(source_repo: Path) -> Path:
    configured = os.environ.get(CLONE_ROOT_ENV)
    if configured:
        return Path(configured).expanduser().resolve()
    windows_project_root = Path("E:/project")
    if os.name == "nt" and windows_project_root.is_dir():
        return windows_project_root.resolve()
    return source_repo.resolve().parent


def create_fresh_clone(
    source_repo: Path,
    *,
    destination_root: Path | None = None,
    branch: str | None = None,
    timestamp: datetime | None = None,
) -> CloneResult:
    """Clone one verified remote branch into a new timestamped directory."""
    source_repo = Path(source_repo).resolve()
    _ensure_source_repository(source_repo)
    selected_branch = branch or _current_branch(source_repo)
    origin_url = _git_output(source_repo, "remote", "get-url", "origin")
    remote_sha = _remote_branch_sha(source_repo, selected_branch)

    if _git_output(source_repo, "status", "--porcelain"):
        print(
            "Warning: Source working tree has local changes.\n"
            "Fresh clone will contain only the pushed remote branch.",
            file=sys.stderr,
        )

    clone_root = (
        Path(destination_root).expanduser().resolve()
        if destination_root is not None
        else default_destination_root(source_repo)
    )
    if clone_root.exists() and not clone_root.is_dir():
        raise CloneError(f"Destination root is not a directory: {clone_root}")
    clone_root.mkdir(parents=True, exist_ok=True)

    created_at = timestamp or datetime.now()
    target = clone_root / (
        f"KFlow-test-{branch_slug(selected_branch)}-"
        f"{created_at.strftime('%Y%m%d-%H%M%S')}"
    )
    if target.exists():
        raise CloneError(
            f"Clone target already exists; refusing to overwrite: {target}"
        )

    print(f"Source repo: {source_repo}")
    print(f"Branch: {selected_branch}")
    print("Remote: origin")
    print(f"Remote URL: {origin_url}")
    print(f"Remote SHA: {remote_sha}")
    print(f"Cloning to: {target}")
    _run(
        [
            "git",
            "clone",
            "--branch",
            selected_branch,
            "--single-branch",
            origin_url,
            str(target),
        ],
        cwd=source_repo,
    )

    head_sha = _git_output(target, "rev-parse", "HEAD")
    cloned_origin = _git_output(target, "remote", "get-url", "origin")
    if head_sha != remote_sha:
        raise CloneError(
            "Fresh clone HEAD does not match the verified remote branch. "
            f"Expected {remote_sha}, got {head_sha}. Clone left at: {target}"
        )
    if cloned_origin != origin_url:
        raise CloneError(
            "Fresh clone origin URL differs from the source repository. "
            f"Expected {origin_url!r}, got {cloned_origin!r}. "
            f"Clone left at: {target}"
        )

    print("Clone complete.")
    print(f"HEAD: {head_sha}")
    print(f"Target: {target}")
    print(f'Next: cd "{target}"')
    return CloneResult(
        source_repo=source_repo,
        branch=selected_branch,
        origin_url=origin_url,
        remote_sha=remote_sha,
        head_sha=head_sha,
        target=target,
    )


def _ensure_source_repository(source_repo: Path) -> None:
    if not source_repo.is_dir():
        raise CloneError(f"Source repository does not exist: {source_repo}")
    result = _run(
        ["git", "-C", str(source_repo), "rev-parse", "--show-toplevel"],
        check=False,
    )
    if result.returncode != 0:
        raise CloneError(f"Source is not a Git repository: {source_repo}")
    try:
        discovered = Path(result.stdout.strip()).resolve()
    except OSError as error:
        raise CloneError(f"Unable to resolve source repository: {error}") from error
    if discovered != source_repo:
        raise CloneError(f"Source must be the Git repository root: {source_repo}")


def _current_branch(source_repo: Path) -> str:
    branch = _git_output(source_repo, "branch", "--show-current")
    if not branch:
        raise CloneError(
            "Source repository has a detached HEAD. Pass --branch explicitly."
        )
    return branch


def _remote_branch_sha(source_repo: Path, branch: str) -> str:
    if not branch:
        raise CloneError("Branch must not be empty.")
    reference = f"refs/heads/{branch}"
    result = _run(
        ["git", "-C", str(source_repo), "ls-remote", "--heads", "origin", reference],
        check=False,
    )
    if result.returncode != 0:
        detail = result.stderr.strip() or result.stdout.strip()
        suffix = f" ({detail})" if detail else ""
        raise CloneError(f"Unable to query origin for branch {branch}.{suffix}")
    for line in result.stdout.splitlines():
        fields = line.split()
        if len(fields) == 2 and fields[1] == reference:
            return fields[0]
    raise CloneError(
        f"Branch {branch} is not available on origin.\n"
        "Push it before creating a fresh test clone."
    )


def _git_output(root: Path, *arguments: str) -> str:
    result = _run(["git", "-C", str(root), *arguments])
    return result.stdout.strip()


def _run(
    command: list[str],
    *,
    cwd: Path | None = None,
    check: bool = True,
) -> subprocess.CompletedProcess[str]:
    try:
        result = subprocess.run(
            command,
            cwd=cwd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=False,
        )
    except OSError as error:
        raise CloneError(f"Unable to run Git: {error}") from error
    if check and result.returncode != 0:
        detail = result.stderr.strip() or result.stdout.strip()
        raise CloneError(f"Git command failed: {detail or result.returncode}")
    return result


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Clone the current pushed KFlow branch for clean manual testing."
    )
    parser.add_argument(
        "--root",
        "--destination-root",
        dest="destination_root",
        type=Path,
        help="parent directory for the new timestamped clone",
    )
    parser.add_argument(
        "--branch",
        help="remote branch to clone (defaults to the current local branch)",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    source_repo = Path(__file__).resolve().parents[1]
    try:
        create_fresh_clone(
            source_repo,
            destination_root=args.destination_root,
            branch=args.branch,
        )
    except CloneError as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
