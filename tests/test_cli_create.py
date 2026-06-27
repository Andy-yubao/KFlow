import json
import pytest
from pathlib import Path
from kflow.store import load_index, load_node
from kflow.commands.create import create_node
from kflow.commands.init import init_project
from kflow.errors import NodeExistsError


def test_create_node_basic(tmp_path):
    init_project(tmp_path)
    result = create_node(tmp_path, "architecture")
    assert result["node"]["name"] == "architecture"
    assert result["node"]["status"] == "green"
    assert result["node"]["file"] == "knowledge/architecture.md"
    assert (tmp_path / "knowledge" / "architecture.md").exists()
    nid = result["node"]["id"]
    node = load_node(tmp_path, nid)
    assert node.name == "architecture"
    assert node.status == "green"
    idx = load_index(tmp_path)
    assert nid in idx.nodes


def test_create_node_duplicate_name_raises(tmp_path):
    init_project(tmp_path)
    create_node(tmp_path, "architecture")
    with pytest.raises(NodeExistsError):
        create_node(tmp_path, "architecture")


def test_create_node_no_file(tmp_path):
    init_project(tmp_path)
    result = create_node(tmp_path, "concept", no_file=True)
    assert result["node"]["file"] is None
    assert not (tmp_path / "knowledge" / "concept.md").exists()


def test_create_node_existing_md_file(tmp_path):
    init_project(tmp_path)
    (tmp_path / "knowledge" / "existing.md").write_text("# Already here")
    result = create_node(tmp_path, "existing")
    content = (tmp_path / "knowledge" / "existing.md").read_text()
    assert content == "# Already here"
