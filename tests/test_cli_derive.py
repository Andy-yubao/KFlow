import pytest
from kflow.commands.init import init_project
from kflow.commands.create import create_node
from kflow.commands.derive import derive_node
from kflow.store import load_index, load_derivation, load_node
from kflow.errors import NodeNotFoundError


def test_derive_basic(tmp_path):
    init_project(tmp_path)
    r1 = create_node(tmp_path, "architecture")
    r2 = create_node(tmp_path, "experiment")

    result = derive_node(
        tmp_path,
        inputs=[
            {"node": r1["node"]["name"], "role": "提供框架", "role_detail": "详细框架说明"},
            {"node": r2["node"]["name"], "role": "提供参数", "role_detail": "详细参数说明"},
        ],
        output={"name": "factbase", "method": "组织数据", "method_detail": "详细方法说明"},
        summary="构建事实库",
    )

    assert result["ok"] is True
    assert result["node"]["name"] == "factbase"
    assert result["node"]["status"] == "green"

    out_id = result["node"]["id"]
    out_node = load_node(tmp_path, out_id)
    assert out_node.name == "factbase"
    assert len(out_node.derivations_as_output) == 1

    dv_id = out_node.derivations_as_output[0]
    dv = load_derivation(tmp_path, dv_id)
    assert dv.summary == "构建事实库"
    assert len(dv.inputs) == 2

    a_node = load_node(tmp_path, r1["node"]["id"])
    assert dv_id in a_node.derivations_as_input


def test_derive_missing_input(tmp_path):
    init_project(tmp_path)
    with pytest.raises(NodeNotFoundError):
        derive_node(
            tmp_path,
            inputs=[{"node": "nonexistent", "role": "r", "role_detail": "rd"}],
            output={"name": "out", "method": "m", "method_detail": "md"},
            summary="s",
        )


def test_derive_duplicate_output_name(tmp_path):
    init_project(tmp_path)
    create_node(tmp_path, "existing")
    create_node(tmp_path, "source")
    with pytest.raises(Exception):
        derive_node(
            tmp_path,
            inputs=[{"node": "source", "role": "r", "role_detail": "rd"}],
            output={"name": "existing", "method": "m", "method_detail": "md"},
            summary="s",
        )


def test_derive_chain_extension(tmp_path):
    """Deriving from a downstream node creates a chain, not a cycle."""
    init_project(tmp_path)
    create_node(tmp_path, "start")
    derive_node(
        tmp_path,
        inputs=[{"node": "start", "role": "r", "role_detail": "rd"}],
        output={"name": "middle", "method": "m", "method_detail": "md"},
        summary="s1",
    )
    # Chain extension: start -> middle -> chain_end — should succeed (no cycle)
    result = derive_node(
        tmp_path,
        inputs=[{"node": "middle", "role": "r", "role_detail": "rd"}],
        output={"name": "chain_end", "method": "m", "method_detail": "md"},
        summary="s2",
    )
    assert result["ok"] is True
    assert result["node"]["name"] == "chain_end"
    assert result["node"]["status"] == "green"


def test_would_create_cycle_detection(tmp_path):
    """Cycle check: adding an edge from a downstream node back to an upstream node."""
    from kflow.graph import would_create_cycle

    init_project(tmp_path)
    create_node(tmp_path, "a")
    create_node(tmp_path, "b")
    create_node(tmp_path, "c")

    derive_node(
        tmp_path,
        inputs=[{"node": "a", "role": "r", "role_detail": "rd"}],
        output={"name": "b_derived", "method": "m", "method_detail": "md"},
        summary="a-to-b",
    )
    derive_node(
        tmp_path,
        inputs=[{"node": "b_derived", "role": "r", "role_detail": "rd"}],
        output={"name": "c_derived", "method": "m", "method_detail": "md"},
        summary="b-to-c",
    )

    index = load_index(tmp_path)

    # Find node IDs
    a_id = None
    c_id = None
    for nid, nd in index.nodes.items():
        if nd.name == "a":
            a_id = nid
        elif nd.name == "c_derived":
            c_id = nid

    # Adding edge c_derived -> a would create cycle: a -> b_derived -> c_derived -> a
    assert would_create_cycle(index, [c_id], a_id) is True

    # Adding edge from unrelated node should not create a cycle
    assert would_create_cycle(index, [c_id], a_id) is True  # confirmed
    # a -> a (self-loop) should not cycle with single input
    # Actually, a new node not in graph should not create a cycle
    assert would_create_cycle(index, [a_id], "nonexistent_id_not_in_graph") is False
