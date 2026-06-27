from kflow.commands.init import init_project
from kflow.commands.create import create_node
from kflow.commands.validate import validate_project


def test_validate_empty_project(tmp_path):
    init_project(tmp_path)
    result = validate_project(tmp_path)
    assert result["ok"] is True
    assert len(result["issues"]) == 0


def test_validate_orphan_warning(tmp_path):
    init_project(tmp_path)
    create_node(tmp_path, "lonely")
    result = validate_project(tmp_path)
    orphans = [i for i in result["issues"] if i["check"] == "orphan_node"]
    assert len(orphans) == 1


def test_validate_unregistered_md(tmp_path):
    init_project(tmp_path)
    (tmp_path / "knowledge" / "stray.md").write_text("# stray")
    result = validate_project(tmp_path)
    unreg = [i for i in result["issues"] if i["check"] == "unregistered_markdown"]
    assert len(unreg) == 1


def test_validate_missing_md(tmp_path):
    init_project(tmp_path)
    create_node(tmp_path, "ghost")
    (tmp_path / "knowledge" / "ghost.md").unlink()
    result = validate_project(tmp_path)
    missing = [i for i in result["issues"] if i["check"] == "missing_markdown"]
    assert len(missing) == 1
