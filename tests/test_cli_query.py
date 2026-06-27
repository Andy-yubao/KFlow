from kflow.commands.init import init_project
from kflow.commands.create import create_node
from kflow.commands.query import query_kflow


def test_query_no_match(tmp_path):
    init_project(tmp_path)
    result = query_kflow(tmp_path, "nonexistent")
    assert result["nodes"] == []
    assert result["derivations"] == []


def test_query_by_node_name(tmp_path):
    init_project(tmp_path)
    create_node(tmp_path, "architecture")
    create_node(tmp_path, "experiment")
    result = query_kflow(tmp_path, "arch")
    assert len(result["nodes"]) == 1
    assert result["nodes"][0]["name"] == "architecture"


def test_query_case_sensitive(tmp_path):
    init_project(tmp_path)
    create_node(tmp_path, "Architecture")
    result = query_kflow(tmp_path, "architecture")
    assert len(result["nodes"]) == 0
