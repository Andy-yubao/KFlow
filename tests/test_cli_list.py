from kflow.commands.init import init_project
from kflow.commands.create import create_node
from kflow.commands.list_cmd import list_nodes


def test_list_empty(tmp_path):
    init_project(tmp_path)
    result = list_nodes(tmp_path)
    assert result == []


def test_list_with_nodes(tmp_path):
    init_project(tmp_path)
    create_node(tmp_path, "architecture")
    create_node(tmp_path, "experiment")
    result = list_nodes(tmp_path)
    assert len(result) == 2
    names = {n["name"] for n in result}
    assert names == {"architecture", "experiment"}


def test_list_json_output(tmp_path):
    init_project(tmp_path)
    create_node(tmp_path, "architecture")
    result = list_nodes(tmp_path)
    assert result[0]["status"] == "green"
