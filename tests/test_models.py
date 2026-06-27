import pytest
from dataclasses import asdict
from kflow.models import Node, InputSpec, OutputSpec, Derivation, IndexNode, IndexDerivation, Index


class TestNode:
    def test_create_node_with_defaults(self):
        n = Node(id="nd_a1b2c3", name="architecture", file="knowledge/architecture.md", status="green")
        assert n.id == "nd_a1b2c3"
        assert n.name == "architecture"
        assert n.file == "knowledge/architecture.md"
        assert n.status == "green"
        assert n.derivations_as_input == []
        assert n.derivations_as_output == []

    def test_create_node_no_file(self):
        n = Node(id="nd_abc123", name="concept", file=None, status="green")
        assert n.file is None

    def test_create_node_with_derivation_refs(self):
        n = Node(
            id="nd_x1y2z3", name="factbase", file="knowledge/factbase.md", status="yellow",
            derivations_as_input=["dv_d4e5f6"], derivations_as_output=["dv_m3n4o5"],
        )
        assert len(n.derivations_as_input) == 1
        assert "dv_d4e5f6" in n.derivations_as_input

    def test_node_asdict(self):
        n = Node(id="nd_a1b2c3", name="architecture", file="knowledge/architecture.md", status="green")
        d = asdict(n)
        assert d["id"] == "nd_a1b2c3"
        assert d["status"] == "green"
        assert d["derivations_as_input"] == []

    def test_node_from_dict(self):
        d = {"id": "nd_a1b2c3", "name": "arch", "file": "knowledge/arch.md", "status": "green",
             "derivations_as_input": [], "derivations_as_output": []}
        n = Node(**d)
        assert n.name == "arch"


class TestInputSpec:
    def test_create_input_spec(self):
        inp = InputSpec(node="nd_a1b2c3", role="提供框架", role_detail="详细框架说明")
        assert inp.node == "nd_a1b2c3"
        assert inp.role == "提供框架"
        assert inp.role_detail == "详细框架说明"


class TestOutputSpec:
    def test_create_output_spec(self):
        out = OutputSpec(node="nd_m3n4o5", method="组织数据", method_detail="详细组织说明")
        assert out.method == "组织数据"


class TestDerivation:
    def test_create_derivation(self):
        inp = InputSpec(node="nd_a1b2c3", role="提供框架", role_detail="详细说明")
        out = OutputSpec(node="nd_m3n4o5", method="组织数据", method_detail="详细方法说明")
        dv = Derivation(id="dv_d4e5f6", summary="构建事实库", inputs=[inp], output=out)
        assert dv.id == "dv_d4e5f6"
        assert len(dv.inputs) == 1
        assert dv.summary == "构建事实库"

    def test_derivation_asdict(self):
        inp = InputSpec(node="nd_a1b2c3", role="r", role_detail="rd")
        out = OutputSpec(node="nd_m3n4o5", method="m", method_detail="md")
        dv = Derivation(id="dv_d4e5f6", summary="s", inputs=[inp], output=out)
        d = asdict(dv)
        assert d["inputs"][0]["role"] == "r"
        assert d["output"]["method"] == "m"


class TestIndex:
    def test_empty_index(self):
        idx = Index(nodes={}, derivations={})
        assert len(idx.nodes) == 0
        assert len(idx.derivations) == 0

    def test_index_with_entries(self):
        nodes = {"nd_a": IndexNode(name="arch", file="knowledge/arch.md", status="green",
                                    derivations_as_input=[], derivations_as_output=[])}
        derivations = {"dv_x": IndexDerivation(summary="s", inputs=[], output={})}
        idx = Index(nodes=nodes, derivations=derivations)
        assert idx.nodes["nd_a"].name == "arch"
