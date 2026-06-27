import pytest
from kflow.commands.init import init_project
from kflow.commands.create import create_node
from kflow.commands.derive import derive_node
from kflow.commands.modify import modify_node
from kflow.store import load_node
from kflow.errors import NodeNotFoundError


def test_modify_sets_self_green_downstream_yellow(tmp_path):
    init_project(tmp_path)
    create_node(tmp_path, "source")
    r = derive_node(
        tmp_path,
        inputs=[{"node": "source", "role": "r", "role_detail": "rd"}],
        output={"name": "middle", "method": "m", "method_detail": "md"},
        summary="s1",
    )
    r2 = derive_node(
        tmp_path,
        inputs=[{"node": "middle", "role": "r", "role_detail": "rd"}],
        output={"name": "end", "method": "m", "method_detail": "md"},
        summary="s2",
    )
    result = modify_node(tmp_path, "source")
    assert result["ok"] is True
    src_node = load_node(tmp_path, result["node"]["id"])
    assert src_node.status == "green"
    mid_id = r["node"]["id"]
    end_id = r2["node"]["id"]
    assert load_node(tmp_path, mid_id).status == "yellow"
    assert load_node(tmp_path, end_id).status == "yellow"


def test_modify_nonexistent(tmp_path):
    init_project(tmp_path)
    with pytest.raises(NodeNotFoundError):
        modify_node(tmp_path, "ghost")
