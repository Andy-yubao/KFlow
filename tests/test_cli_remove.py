import pytest
from kflow.commands.init import init_project
from kflow.commands.create import create_node
from kflow.commands.derive import derive_node
from kflow.commands.remove import remove_node
from kflow.store import load_index, load_node
from kflow.errors import DerivationBlockedError, NodeNotFoundError


def test_remove_source_node_no_downstream(tmp_path):
    init_project(tmp_path)
    r = create_node(tmp_path, "orphan")
    nid = r["node"]["id"]
    result = remove_node(tmp_path, "orphan")
    assert result["ok"] is True
    idx = load_index(tmp_path)
    assert nid not in idx.nodes
    assert not (tmp_path / ".kflow" / "nodes" / f"{nid}.json").exists()
    assert not (tmp_path / "knowledge" / "orphan.md").exists()


def test_remove_blocked_by_downstream(tmp_path):
    init_project(tmp_path)
    create_node(tmp_path, "source")
    derive_node(
        tmp_path,
        inputs=[{"node": "source", "role": "r", "role_detail": "rd"}],
        output={"name": "derived", "method": "m", "method_detail": "md"},
        summary="s",
    )
    with pytest.raises(DerivationBlockedError):
        remove_node(tmp_path, "source")


def test_remove_force_with_downstream(tmp_path):
    init_project(tmp_path)
    create_node(tmp_path, "source")
    r2 = derive_node(
        tmp_path,
        inputs=[{"node": "source", "role": "r", "role_detail": "rd"}],
        output={"name": "derived", "method": "m", "method_detail": "md"},
        summary="s",
    )
    result = remove_node(tmp_path, "source", force=True)
    assert result["ok"] is True
    d_node = load_node(tmp_path, r2["node"]["id"])
    assert d_node.status == "red"


def test_remove_keep_file(tmp_path):
    init_project(tmp_path)
    create_node(tmp_path, "keep_me")
    md_path = tmp_path / "knowledge" / "keep_me.md"
    assert md_path.exists()
    remove_node(tmp_path, "keep_me", keep_file=True)
    assert md_path.exists()


def test_remove_nonexistent(tmp_path):
    init_project(tmp_path)
    with pytest.raises(NodeNotFoundError):
        remove_node(tmp_path, "ghost")
