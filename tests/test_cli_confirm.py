from kflow.commands.init import init_project
from kflow.commands.create import create_node
from kflow.commands.derive import derive_node
from kflow.commands.modify import modify_node
from kflow.commands.confirm import confirm_node
from kflow.store import load_node, load_index, save_node, save_index


def test_confirm_single_node(tmp_path):
    init_project(tmp_path)
    create_node(tmp_path, "source")
    derive_node(
        tmp_path,
        inputs=[{"node": "source", "role": "r", "role_detail": "rd"}],
        output={"name": "middle", "method": "m", "method_detail": "md"},
        summary="s",
    )
    modify_node(tmp_path, "source")
    result = confirm_node(tmp_path, "middle")
    mid_id = result["node"]["id"]
    assert load_node(tmp_path, mid_id).status == "green"


def test_confirm_cascade(tmp_path):
    init_project(tmp_path)
    create_node(tmp_path, "source")
    r1 = derive_node(tmp_path,
        inputs=[{"node": "source", "role": "r", "role_detail": "rd"}],
        output={"name": "a", "method": "m", "method_detail": "md"}, summary="s1")
    r2 = derive_node(tmp_path,
        inputs=[{"node": "a", "role": "r", "role_detail": "rd"}],
        output={"name": "b", "method": "m", "method_detail": "md"}, summary="s2")
    modify_node(tmp_path, "source")
    _ = confirm_node(tmp_path, "source", cascade=True)
    assert load_node(tmp_path, r1["node"]["id"]).status == "green"
    assert load_node(tmp_path, r2["node"]["id"]).status == "green"


def test_confirm_red_node(tmp_path):
    init_project(tmp_path)
    create_node(tmp_path, "source")
    r = derive_node(tmp_path,
        inputs=[{"node": "source", "role": "r", "role_detail": "rd"}],
        output={"name": "derived", "method": "m", "method_detail": "md"}, summary="s")
    n = load_node(tmp_path, r["node"]["id"])
    n.status = "red"
    save_node(tmp_path, n)
    idx = load_index(tmp_path)
    idx.nodes[r["node"]["id"]].status = "red"
    save_index(tmp_path, idx)
    _ = confirm_node(tmp_path, "derived")
    assert load_node(tmp_path, r["node"]["id"]).status == "green"
