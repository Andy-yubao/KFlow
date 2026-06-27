from kflow.commands.init import init_project
from kflow.commands.create import create_node
from kflow.commands.reindex import reindex_project


def test_reindex_empty(tmp_path):
    init_project(tmp_path)
    result = reindex_project(tmp_path)
    assert result["ok"] is True
    assert result["node_count"] == 0
    assert result["derivation_count"] == 0


def test_reindex_with_nodes(tmp_path):
    init_project(tmp_path)
    create_node(tmp_path, "a")
    create_node(tmp_path, "b")
    result = reindex_project(tmp_path)
    assert result["node_count"] == 2
