"""Tests for the developer fresh-clone helper using only local Git repos."""

from __future__ import annotations

import subprocess
from datetime import datetime
from pathlib import Path

import pytest

from scripts import clone_test_repo


def _git(root: Path, *arguments: str) -> str:
    return subprocess.run(
        ["git", "-C", str(root), *arguments],
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    ).stdout.strip()


@pytest.fixture
def pushed_repository(tmp_path: Path) -> tuple[Path, Path]:
    source = tmp_path / "source repo"
    origin = tmp_path / "origin remote.git"
    source.mkdir()
    subprocess.run(["git", "init", "--bare", str(origin)], check=True)
    subprocess.run(["git", "init", "-b", "main", str(source)], check=True)
    _git(source, "config", "user.name", "KFlow Test")
    _git(source, "config", "user.email", "kflow@example.invalid")
    (source / "tracked.txt").write_text("main\n", encoding="utf-8")
    _git(source, "add", "tracked.txt")
    _git(source, "commit", "-m", "main baseline")
    _git(source, "remote", "add", "origin", str(origin))
    _git(source, "push", "-u", "origin", "main")

    _git(source, "switch", "-c", "codex/fresh-clone")
    (source / "tracked.txt").write_text("feature\n", encoding="utf-8")
    _git(source, "commit", "-am", "feature branch")
    _git(source, "push", "-u", "origin", "codex/fresh-clone")
    return source, origin


def test_branch_slug_is_safe_and_readable() -> None:
    assert clone_test_repo.branch_slug("codex/ui shutdown+clone") == (
        "codex-ui-shutdown-clone"
    )
    assert clone_test_repo.branch_slug("///") == "branch"


def test_default_branch_clones_pushed_head_and_warns_about_dirty_source(
    pushed_repository: tuple[Path, Path], tmp_path: Path, capsys
) -> None:
    source, origin = pushed_repository
    destination_root = tmp_path / "test clones with spaces"
    (source / "local-only.txt").write_text("not pushed\n", encoding="utf-8")
    created_at = datetime(2026, 9, 2, 18, 15, 0)

    result = clone_test_repo.create_fresh_clone(
        source,
        destination_root=destination_root,
        timestamp=created_at,
    )

    assert result.branch == "codex/fresh-clone"
    assert result.target.name == "KFlow-test-codex-fresh-clone-20260902-181500"
    assert result.target.parent == destination_root.resolve()
    assert result.remote_sha == _git(source, "rev-parse", "origin/codex/fresh-clone")
    assert (
        result.head_sha == result.remote_sha == _git(result.target, "rev-parse", "HEAD")
    )
    assert _git(result.target, "branch", "--show-current") == result.branch
    assert _git(result.target, "status", "--porcelain") == ""
    assert _git(result.target, "remote", "get-url", "origin") == str(origin)
    assert (result.target / ".git").is_dir()
    assert not (result.target / "local-only.txt").exists()
    assert "Source working tree has local changes" in capsys.readouterr().err


def test_explicit_branch_override_and_existing_target_are_safe(
    pushed_repository: tuple[Path, Path], tmp_path: Path
) -> None:
    source, _origin = pushed_repository
    destination_root = tmp_path / "clones"
    created_at = datetime(2026, 9, 2, 19, 0, 0)

    result = clone_test_repo.create_fresh_clone(
        source,
        destination_root=destination_root,
        branch="main",
        timestamp=created_at,
    )

    assert result.branch == "main"
    assert result.head_sha == _git(source, "rev-parse", "origin/main")
    marker = result.target / "keep.txt"
    marker.write_text("keep\n", encoding="utf-8")
    with pytest.raises(clone_test_repo.CloneError, match="refusing to overwrite"):
        clone_test_repo.create_fresh_clone(
            source,
            destination_root=destination_root,
            branch="main",
            timestamp=created_at,
        )
    assert marker.read_text(encoding="utf-8") == "keep\n"


def test_missing_remote_branch_fails_before_creating_target(
    pushed_repository: tuple[Path, Path], tmp_path: Path
) -> None:
    source, _origin = pushed_repository
    destination_root = tmp_path / "empty clones"

    with pytest.raises(
        clone_test_repo.CloneError,
        match=(
            r"Branch local-only is not available on origin\.\n"
            r"Push it before creating a fresh test clone\."
        ),
    ):
        clone_test_repo.create_fresh_clone(
            source,
            destination_root=destination_root,
            branch="local-only",
        )

    assert not destination_root.exists()


def test_destination_root_environment_override(
    pushed_repository: tuple[Path, Path], tmp_path: Path, monkeypatch
) -> None:
    source, _origin = pushed_repository
    configured = tmp_path / "configured clones"
    monkeypatch.setenv(clone_test_repo.CLONE_ROOT_ENV, str(configured))

    assert clone_test_repo.default_destination_root(source) == configured.resolve()
