import json
from kflow.commands.init import init_project
from kflow.commands.create import create_node
from kflow.commands.list_cmd import list_nodes
from kflow.commands.query import query_kflow
from kflow.commands.validate import validate_project


def test_list_json_is_valid_json(tmp_path):
    init_project(tmp_path)
    create_node(tmp_path, "test")
    result = list_nodes(tmp_path)
    json_str = json.dumps(result)
    parsed = json.loads(json_str)
    assert len(parsed) == 1
    assert parsed[0]["name"] == "test"


def test_query_json_structure(tmp_path):
    init_project(tmp_path)
    create_node(tmp_path, "test")
    result = query_kflow(tmp_path, "test")
    assert "q" in result
    assert "nodes" in result
    assert "derivations" in result


def test_validate_json_structure(tmp_path):
    init_project(tmp_path)
    result = validate_project(tmp_path)
    assert result["ok"] is True
    assert isinstance(result["issues"], list)
