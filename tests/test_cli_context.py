from kflow.commands.init import init_project
from kflow.commands.create import create_node
from kflow.commands.derive import derive_node
from kflow.commands.context import context_node


def test_context_source_node(tmp_path):
    init_project(tmp_path)
    r = create_node(tmp_path, "source")
    result = context_node(tmp_path, "source")
    assert result["target"] == r["node"]["id"]
    assert len(result["nodes"]) == 1
    assert result["nodes"][0]["source"] is None


def test_context_with_upstream(tmp_path):
    init_project(tmp_path)
    create_node(tmp_path, "a")
    create_node(tmp_path, "b")
    _ = derive_node(
        tmp_path,
        inputs=[{"node": "a", "role": "r1", "role_detail": "d1"},
                {"node": "b", "role": "r2", "role_detail": "d2"}],
        output={"name": "c", "method": "m", "method_detail": "md"},
        summary="combine",
    )
    result = context_node(tmp_path, "c")
    assert len(result["nodes"]) >= 3
    names = [n["name"] for n in result["nodes"]]
    assert names[-1] == "c"


def test_context_with_depth(tmp_path):
    init_project(tmp_path)
    create_node(tmp_path, "a")
    derive_node(tmp_path,
        inputs=[{"node": "a", "role": "r", "role_detail": "rd"}],
        output={"name": "b", "method": "m", "method_detail": "md"}, summary="s1")
    derive_node(tmp_path,
        inputs=[{"node": "b", "role": "r", "role_detail": "rd"}],
        output={"name": "c", "method": "m", "method_detail": "md"}, summary="s2")
    result = context_node(tmp_path, "c", depth=1)
    names = [n["name"] for n in result["nodes"]]
    assert "a" not in names
