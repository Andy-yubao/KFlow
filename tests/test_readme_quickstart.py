import json
from pathlib import Path

import pytest

from kflow.cli import main as kflow_main
from scripts import create_readme_quickstart as quickstart


CORE_FILES = (
    "docs/requirements.md",
    "docs/constraints.md",
    "docs/architecture.md",
    "docs/api-design.md",
    "docs/testing-plan.md",
    "docs/deployment-plan.md",
)


def run_json(capsys, *arguments):
    kflow_main([*arguments, "--json"])
    return json.loads(capsys.readouterr().out)


def assert_quickstart_files(root: Path) -> None:
    assert sorted(
        path.relative_to(root).as_posix() for path in root.rglob("*") if path.is_file()
    ) == sorted(CORE_FILES)


def test_default_target_creates_only_the_six_quickstart_files(
    tmp_path, monkeypatch, capsys
):
    monkeypatch.chdir(tmp_path)

    assert quickstart.main([]) == 0

    root = tmp_path / "kflow-quickstart"
    assert_quickstart_files(root)
    assert capsys.readouterr().out == (
        f"Quickstart files created at: {root.resolve()}\n"
        "\n"
        "No KFlow metadata has been created.\n"
        "Follow README.md to run:\n"
        "  kflow init\n"
        "  kflow add-node ...\n"
        "  kflow derive ...\n"
    )
    forbidden_names = {".kflow", ".git", "node_modules", "cache", "runtime"}
    assert not any(forbidden_names.intersection(path.parts) for path in root.rglob("*"))


@pytest.mark.parametrize("absolute", [False, True])
def test_custom_target_supports_relative_absolute_space_and_unicode_paths(
    tmp_path, monkeypatch, absolute
):
    monkeypatch.chdir(tmp_path)
    target = tmp_path / "中文 quickstart" if absolute else Path("中文 quickstart")

    created = quickstart.create_quickstart(target)

    assert created == (tmp_path / "中文 quickstart").resolve()
    assert_quickstart_files(created)


@pytest.mark.parametrize("with_file", [False, True])
def test_existing_target_is_never_overwritten_or_deleted(tmp_path, with_file):
    target = tmp_path / "existing"
    target.mkdir()
    marker = target / "keep.txt"
    if with_file:
        marker.write_text("keep", encoding="utf-8")

    with pytest.raises(FileExistsError, match="already exists"):
        quickstart.create_quickstart(target)

    assert target.is_dir()
    if with_file:
        assert marker.read_text(encoding="utf-8") == "keep"


def test_cli_failure_uses_stderr_and_nonzero_result(tmp_path, capsys):
    target = tmp_path / "existing"
    target.mkdir()

    assert quickstart.main([str(target)]) == 1

    output = capsys.readouterr()
    assert output.out == ""
    assert "already exists" in output.err
    assert "Quickstart files created" not in output.err


def test_generated_content_is_distinct_substantial_and_supports_the_story(tmp_path):
    root = quickstart.create_quickstart(tmp_path / "example")
    contents = {
        relative: (root / relative).read_text(encoding="utf-8")
        for relative in CORE_FILES
    }

    assert len(set(contents.values())) == len(CORE_FILES)
    assert all(len(content.splitlines()) >= 7 for content in contents.values())
    expected_terms = {
        "docs/requirements.md": ("human", "Agent", "read-only"),
        "docs/constraints.md": ("localhost", "third-party", "arbitrary"),
        "docs/architecture.md": ("Core query layer", "HTTP adapter", "Git-backed"),
        "docs/api-design.md": ("/api/project", "/api/review-order", "read-only"),
        "docs/testing-plan.md": ("Core", "frontend", "stale-response"),
        "docs/deployment-plan.md": ("Python package", "static assets", "Node.js"),
    }
    for relative, terms in expected_terms.items():
        assert all(term in contents[relative] for term in terms)


def test_partial_target_is_cleaned_up_after_a_write_failure(tmp_path, monkeypatch):
    target = tmp_path / "partial"
    outside = tmp_path / "outside.txt"
    outside.write_text("keep", encoding="utf-8")
    real_write = quickstart._write_file
    writes = 0

    def fail_during_second_write(path, content):
        nonlocal writes
        writes += 1
        if writes == 2:
            raise OSError("simulated write failure")
        real_write(path, content)

    monkeypatch.setattr(quickstart, "_write_file", fail_during_second_write)

    with pytest.raises(OSError, match="simulated write failure"):
        quickstart.create_quickstart(target)

    assert not target.exists()
    assert outside.read_text(encoding="utf-8") == "keep"


def test_readme_quickstart_builds_the_documented_graph_through_the_real_cli(
    tmp_path, monkeypatch, capsys
):
    root = quickstart.create_quickstart(tmp_path / "guided example")
    unregistered = root / "notes.txt"
    unregistered.write_text(
        "This ordinary file stays outside KFlow.\n", encoding="utf-8"
    )
    assert not (root / ".kflow").exists()
    monkeypatch.chdir(root)

    run_json(capsys, "init")
    nodes = {
        name: run_json(capsys, "add-node", name, "--file", f"docs/{name}.md")["node"]
        for name in (
            "requirements",
            "constraints",
            "architecture",
            "api-design",
            "testing-plan",
            "deployment-plan",
        )
    }
    run_json(
        capsys,
        "derive",
        "--short",
        "需求与约束形成架构",
        "--input",
        "requirements",
        "提供产品目标",
        "--input",
        "constraints",
        "提供运行边界",
        "--output",
        "architecture",
        "形成系统结构",
    )
    run_json(
        capsys,
        "derive",
        "--short",
        "架构形成接口与测试方案",
        "--input",
        "architecture",
        "提供组件边界",
        "--output",
        "api-design",
        "形成接口设计",
        "--output",
        "testing-plan",
        "形成测试方案",
    )
    run_json(
        capsys,
        "derive",
        "--short",
        "接口设计形成部署方案",
        "--input",
        "api-design",
        "提供运行接口",
        "--output",
        "deployment-plan",
        "形成部署计划",
    )

    overview = run_json(capsys, "overview")
    assert overview["project"]["node_count"] == 6
    assert overview["project"]["derivation_count"] == 3
    assert {
        (len(item["inputs"]), len(item["outputs"])) for item in overview["derivations"]
    } == {(2, 1), (1, 2), (1, 1)}
    assert "notes.txt" not in {
        path for node in overview["nodes"] for path in node["files"]
    }

    for name in nodes:
        run_json(capsys, "confirm", name)

    requirements = root / "docs" / "requirements.md"
    with requirements.open("a", encoding="utf-8", newline="\n") as stream:
        stream.write(
            "\n- The interface must support exporting a read-only project summary.\n"
        )

    status = run_json(capsys, "overview", "--status")
    impact = run_json(capsys, "impact", "requirements")
    review_order = run_json(capsys, "review-order")

    by_name = {item["name"]: item for item in status["nodes"]}
    assert by_name["requirements"]["reasons"] == ["files_changed"]
    for name in (
        "architecture",
        "api-design",
        "testing-plan",
        "deployment-plan",
    ):
        assert by_name[name]["reasons"] == ["input_changed"]
    assert by_name["constraints"]["reasons"] == []

    expected_order = [
        node_id
        for node_id in status["topological_order"]
        if {item["id"]: item for item in status["nodes"]}[node_id]["reasons"]
    ]
    assert review_order["review_order"] == expected_order
    assert [item["name"] for item in impact["direct_outputs"]] == ["architecture"]

    for node_id in expected_order:
        run_json(capsys, "confirm", node_id)
    assert run_json(capsys, "review-order")["review_order"] == []
    assert run_json(capsys, "validate") == {
        "ok": True,
        "schema_version": 3,
        "issues": [],
    }


def test_readme_contains_the_real_guided_quickstart_commands():
    readme = (Path(__file__).parents[1] / "README.md").read_text(encoding="utf-8")
    required_commands = (
        "python scripts/create_readme_quickstart.py",
        "kflow init",
        "kflow add-node",
        "kflow derive",
        "kflow confirm",
        "kflow overview --status",
        "kflow context",
        "kflow impact",
        "kflow review-order",
        "kflow ui start",
    )

    assert all(command in readme for command in required_commands)


def test_readme_keeps_basic_quickstart_first_and_git_demo_optional():
    readme = (Path(__file__).parents[1] / "README.md").read_text(encoding="utf-8")

    part_one = readme.index("### Part 1 — Basic Project Graph")
    part_two = readme.index("### Part 2 — Git-backed History Demo（可选）")
    public_commands = readme.index("## 公开命令")

    assert part_one < part_two < public_commands
    assert "不要求当前目录是 Git 仓库" in readme[part_one:part_two]
    assert "python scripts/setup_git_quickstart_demo.py" in readme[part_two:]
    assert "HEAD~1" in readme[part_two:]
    assert "HEAD~2" in readme[part_two:]
    assert "kflow ui start" in readme[part_two:]
    assert "bulk-create" in readme[part_two:]
