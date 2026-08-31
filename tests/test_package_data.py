"""Distribution package-data smoke tests."""

import shutil
import subprocess
import sys
import tarfile
import zipfile
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_wheel_contains_human_interface_static_assets(tmp_path) -> None:
    source = tmp_path / "source"
    wheelhouse = tmp_path / "wheelhouse"
    source.mkdir()
    wheelhouse.mkdir()
    shutil.copy2(PROJECT_ROOT / "pyproject.toml", source / "pyproject.toml")
    shutil.copytree(PROJECT_ROOT / "kflow", source / "kflow")

    subprocess.run(
        [
            sys.executable,
            "-m",
            "pip",
            "wheel",
            ".",
            "--no-index",
            "--no-deps",
            "--no-build-isolation",
            "--wheel-dir",
            str(wheelhouse),
        ],
        cwd=source,
        check=True,
    )

    wheels = list(wheelhouse.glob("*.whl"))
    assert len(wheels) == 1
    with zipfile.ZipFile(wheels[0]) as archive:
        names = set(archive.namelist())

    asset_prefix = "kflow/human/static/assets/"
    assert "kflow/human/static/index.html" in names
    assert any(name.startswith(asset_prefix) and name.endswith(".js") for name in names)
    assert any(
        name.startswith(asset_prefix) and name.endswith(".css") for name in names
    )


def test_sdist_contains_human_interface_static_assets(tmp_path) -> None:
    source = tmp_path / "source"
    dist = source / "dist"
    source.mkdir()
    dist.mkdir()
    shutil.copy2(PROJECT_ROOT / "pyproject.toml", source / "pyproject.toml")
    shutil.copytree(PROJECT_ROOT / "kflow", source / "kflow")

    subprocess.run(
        [
            sys.executable,
            "-c",
            ("from setuptools.build_meta import build_sdist; build_sdist('dist')"),
        ],
        cwd=source,
        check=True,
    )

    archives = list(dist.glob("*.tar.gz"))
    assert len(archives) == 1
    with tarfile.open(archives[0], "r:gz") as archive:
        names = {Path(name).as_posix() for name in archive.getnames()}

    static_suffix = "/kflow/human/static/"
    assert any(name.endswith(f"{static_suffix}index.html") for name in names)
    assert any(
        static_suffix in name and "/assets/" in name and name.endswith(".js")
        for name in names
    )
    assert any(
        static_suffix in name and "/assets/" in name and name.endswith(".css")
        for name in names
    )
