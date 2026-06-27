import pytest
from kflow.status import propagate_yellow, propagate_red, propagate_green_cascade
from kflow.models import Index, IndexNode, IndexDerivation


def make_chain_index(n_nodes: int):
    """Build a linear chain: nd_0 → dv_0 → nd_1 → dv_1 → nd_2 ...

    Returns (index, node_ids).
    """
    node_ids = [f"nd_{i}" for i in range(n_nodes)]
    nodes = {}
    derivations = {}

    for i, nid in enumerate(node_ids):
        d_as_in = [f"dv_{i}"] if i < n_nodes - 1 else []
        d_as_out = [f"dv_{i-1}"] if i > 0 else []
        nodes[nid] = IndexNode(name=f"n{i}", file=None, status="green",
                               derivations_as_input=d_as_in, derivations_as_output=d_as_out)

    for i in range(n_nodes - 1):
        did = f"dv_{i}"
        derivations[did] = IndexDerivation(
            summary=f"derive {i}",
            inputs=[{"node": node_ids[i], "role": f"role_{i}"}],
            output={"node": node_ids[i+1], "method": f"method_{i}"},
        )

    return Index(nodes=nodes, derivations=derivations), node_ids


class TestPropagateYellow:
    def test_simple_chain(self):
        idx, nids = make_chain_index(3)
        idx.nodes[nids[0]].status = "green"  # modify sets target green
        affected = propagate_yellow(idx, nids[0])
        assert nids[1] in affected
        assert nids[2] in affected
        assert nids[0] not in affected  # target itself not affected
        assert idx.nodes[nids[1]].status == "yellow"
        assert idx.nodes[nids[2]].status == "yellow"

    def test_no_downstream(self):
        idx, nids = make_chain_index(1)
        affected = propagate_yellow(idx, nids[0])
        assert len(affected) == 0


class TestPropagateRed:
    def test_full_chain_goes_red(self):
        idx, nids = make_chain_index(4)
        affected = propagate_red(idx, nids[1])  # start red propagation from nd_1
        assert nids[1] in affected
        assert nids[2] in affected
        assert nids[3] in affected
        assert all(idx.nodes[n].status == "red" for n in affected)

    def test_single_node(self):
        idx, nids = make_chain_index(1)
        affected = propagate_red(idx, nids[0])
        assert affected == {nids[0]}


class TestPropagateGreenCascade:
    def test_full_chain_goes_green(self):
        idx, nids = make_chain_index(4)
        idx.nodes[nids[1]].status = "yellow"
        idx.nodes[nids[2]].status = "red"
        idx.nodes[nids[3]].status = "yellow"
        affected = propagate_green_cascade(idx, nids[0])
        assert nids[0] in affected
        assert nids[1] in affected
        assert nids[2] in affected
        assert nids[3] in affected
        assert all(idx.nodes[n].status == "green" for n in nids)

    def test_cascade_ignores_red_upstream(self):
        """confirm --cascade does not check other upstreams."""
        nodes = {
            "nd_a": IndexNode(name="a", file=None, status="green",
                               derivations_as_input=["dv_0"], derivations_as_output=[]),
            "nd_b": IndexNode(name="b", file=None, status="yellow",
                               derivations_as_input=[], derivations_as_output=["dv_0", "dv_1"]),
            "nd_x": IndexNode(name="x", file=None, status="red",
                               derivations_as_input=["dv_1"], derivations_as_output=[]),
        }
        derivations = {
            "dv_0": IndexDerivation(summary="s0", inputs=[{"node": "nd_a", "role": "r"}],
                                    output={"node": "nd_b", "method": "m"}),
            "dv_1": IndexDerivation(summary="s1", inputs=[{"node": "nd_x", "role": "r"}],
                                    output={"node": "nd_b", "method": "m"}),
        }
        idx = Index(nodes=nodes, derivations=derivations)
        affected = propagate_green_cascade(idx, "nd_a")
        assert "nd_b" in affected
        assert idx.nodes["nd_b"].status == "green"
        assert idx.nodes["nd_x"].status == "red"
