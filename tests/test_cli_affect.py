from kflow.commands.init import init_project
from kflow.commands.create import create_node
from kflow.commands.derive import derive_node
from kflow.commands.affect import affect_node


def test_affect_leaf_node(tmp_path):
    init_project(tmp_path)
    create_node(tmp_path, "leaf")
    result = affect_node(tmp_path, "leaf")
    assert len(result["nodes"]) == 1
    assert result["nodes"][0]["depth"] == 0


def test_affect_chain(tmp_path):
    init_project(tmp_path)
    create_node(tmp_path, "a")
    derive_node(tmp_path,
        inputs=[{"node": "a", "role": "r", "role_detail": "rd"}],
        output={"name": "b", "method": "m", "method_detail": "md"}, summary="s1")
    derive_node(tmp_path,
        inputs=[{"node": "b", "role": "r", "role_detail": "rd"}],
        output={"name": "c", "method": "m", "method_detail": "md"}, summary="s2")
    result = affect_node(tmp_path, "a")
    assert len(result["nodes"]) == 3
    depths = {n["name"]: n["depth"] for n in result["nodes"]}
    assert depths["a"] == 0
    assert depths["b"] == 1
    assert depths["c"] == 2


def test_affect_with_depth(tmp_path):
    init_project(tmp_path)
    create_node(tmp_path, "a")
    derive_node(tmp_path,
        inputs=[{"node": "a", "role": "r", "role_detail": "rd"}],
        output={"name": "b", "method": "m", "method_detail": "md"}, summary="s1")
    derive_node(tmp_path,
        inputs=[{"node": "b", "role": "r", "role_detail": "rd"}],
        output={"name": "c", "method": "m", "method_detail": "md"}, summary="s2")
    result = affect_node(tmp_path, "a", depth=1)
    names = {n["name"] for n in result["nodes"]}
    assert "a" in names
    assert "b" in names
    assert "c" not in names
