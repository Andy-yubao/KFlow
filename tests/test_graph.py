import pytest
from kflow.graph import bfs_upstream, bfs_downstream, has_cycle, would_create_cycle, toposort_nodes
from kflow.models import Index, IndexNode, IndexDerivation


def make_index(nodes_spec, derivations_spec):
    """Helper to build an Index from concise specs.

    nodes_spec: list of (id, name, derivations_as_input, derivations_as_output)
    derivations_spec: list of (id, summary, [(input_node_id, role)], output_node_id, method)
    """
    nodes = {}
    derivations = {}
    for (nid, name, d_as_in, d_as_out) in nodes_spec:
        nodes[nid] = IndexNode(name=name, file=f"knowledge/{name}.md", status="green",
                               derivations_as_input=d_as_in, derivations_as_output=d_as_out)
    for (did, summary, inputs, output_id, method) in derivations_spec:
        derivations[did] = IndexDerivation(
            summary=summary,
            inputs=[{"node": nid, "role": role} for (nid, role) in inputs],
            output={"node": output_id, "method": method},
        )
    return Index(nodes=nodes, derivations=derivations)


class TestBfsUpstream:
    def test_source_node_returns_self(self):
        idx = make_index(
            [("nd_a", "arch", [], [])],
            [],
        )
        result = bfs_upstream(idx, "nd_a")
        assert result == ["nd_a"]

    def test_single_derivation_chain(self):
        idx = make_index(
            [("nd_a", "arch", [], []),
             ("nd_b", "plan", [], ["dv_x"])],
            [("dv_x", "derive plan", [("nd_a", "base")], "nd_b", "method")],
        )
        result = bfs_upstream(idx, "nd_b")
        assert result[0] == "nd_a"
        assert result[-1] == "nd_b"
        assert len(result) == 2

    def test_two_sources_one_derivation(self):
        idx = make_index(
            [("nd_a", "a", [], []),
             ("nd_b", "b", [], []),
             ("nd_c", "c", [], ["dv_x"])],
            [("dv_x", "combine", [("nd_a", "r1"), ("nd_b", "r2")], "nd_c", "m")],
        )
        result = bfs_upstream(idx, "nd_c")
        assert set(result[:2]) == {"nd_a", "nd_b"}
        assert result[2] == "nd_c"


class TestBfsDownstream:
    def test_leaf_node_returns_self(self):
        idx = make_index(
            [("nd_a", "arch", [], [])],
            [],
        )
        result = bfs_downstream(idx, "nd_a")
        assert result == {"nd_a": 0}

    def test_chain_downstream(self):
        idx = make_index(
            [("nd_a", "a", ["dv_x"], []),
             ("nd_b", "b", ["dv_y"], ["dv_x"]),
             ("nd_c", "c", [], ["dv_y"])],
            [("dv_x", "x", [("nd_a", "r")], "nd_b", "m"),
             ("dv_y", "y", [("nd_b", "r")], "nd_c", "m")],
        )
        result = bfs_downstream(idx, "nd_a")
        assert result["nd_a"] == 0
        assert result["nd_b"] == 1
        assert result["nd_c"] == 2


class TestHasCycle:
    def test_dag_no_cycle(self):
        idx = make_index(
            [("nd_a", "a", ["dv_x"], []),
             ("nd_b", "b", [], ["dv_x"])],
            [("dv_x", "x", [("nd_a", "r")], "nd_b", "m")],
        )
        assert has_cycle(idx) is False

    def test_cycle_detected(self):
        idx = make_index(
            [("nd_a", "a", [], ["dv_y"]),
             ("nd_b", "b", [], ["dv_x"])],
            [("dv_x", "x", [("nd_a", "r")], "nd_b", "m"),
             ("dv_y", "y", [("nd_b", "r")], "nd_a", "m")],
        )
        assert has_cycle(idx) is True


class TestWouldCreateCycle:
    def test_no_cycle_new_edge(self):
        idx = make_index(
            [("nd_a", "a", [], []),
             ("nd_b", "b", [], [])],
            [],
        )
        assert would_create_cycle(idx, ["nd_a"], "nd_b") is False

    def test_cycle_detected_new_edge(self):
        # nd_a → dv_x → nd_b. Adding nd_b → nd_a would create cycle
        idx = make_index(
            [("nd_a", "a", [], []),
             ("nd_b", "b", [], ["dv_x"])],
            [("dv_x", "x", [("nd_a", "r")], "nd_b", "m")],
        )
        assert would_create_cycle(idx, ["nd_b"], "nd_a") is True


class TestToposortNodes:
    def test_simple_chain(self):
        idx = make_index(
            [("nd_a", "a", [], []),
             ("nd_b", "b", [], ["dv_x"]),
             ("nd_c", "c", [], ["dv_y"])],
            [("dv_x", "x", [("nd_a", "r")], "nd_b", "m"),
             ("dv_y", "y", [("nd_b", "r")], "nd_c", "m")],
        )
        result = toposort_nodes(idx, ["nd_a", "nd_b", "nd_c"])
        assert result[0] == "nd_a"
        assert result[1] == "nd_b"
        assert result[2] == "nd_c"
