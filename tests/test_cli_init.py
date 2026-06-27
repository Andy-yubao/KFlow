import json
import pytest
from kflow.commands.init import init_project
from kflow.errors import ProjectAlreadyInitError


def test_init_creates_structure(tmp_path):
    init_project(tmp_path)
    assert (tmp_path / ".kflow").is_dir()
    assert (tmp_path / ".kflow" / "nodes").is_dir()
    assert (tmp_path / ".kflow" / "derivations").is_dir()
    assert (tmp_path / "knowledge").is_dir()
    assert (tmp_path / ".kflow" / "index.json").exists()
    with open(tmp_path / ".kflow" / "index.json") as f:
        data = json.load(f)
    assert data == {"nodes": {}, "derivations": {}}


def test_init_twice_raises(tmp_path):
    init_project(tmp_path)
    with pytest.raises(ProjectAlreadyInitError):
        init_project(tmp_path)


def test_init_preserves_existing_knowledge_dir(tmp_path):
    knowledge = tmp_path / "knowledge"
    knowledge.mkdir()
    (knowledge / "existing.md").write_text("# content")
    init_project(tmp_path)
    assert (knowledge / "existing.md").exists()
