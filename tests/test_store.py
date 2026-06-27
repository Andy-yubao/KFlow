import json
import pytest
from kflow.store import (
    load_index,
    save_index,
    save_node,
    load_node,
    save_derivation,
    load_derivation,
    reindex,
    write_atomic,
    project_root_has_kflow,
)
from kflow.models import Index, Node, IndexNode, Derivation, InputSpec, OutputSpec


class TestProjectRootCheck:
    def test_has_kflow_true(self, tmp_kflow):
        assert project_root_has_kflow(tmp_kflow) is True

    def test_has_kflow_false(self, tmp_path):
        assert project_root_has_kflow(tmp_path) is False


class TestSaveAndLoadNode:
    def test_save_and_load_roundtrip(self, tmp_kflow, sample_node_dict):
        from kflow.models import Node
        node = Node(**sample_node_dict)
        save_node(tmp_kflow, node)
        loaded = load_node(tmp_kflow, "nd_a1b2c3")
        assert loaded.id == "nd_a1b2c3"
        assert loaded.name == "architecture"
        assert loaded.status == "green"

    def test_load_nonexistent_node_raises(self, tmp_kflow):
        with pytest.raises(FileNotFoundError):
            load_node(tmp_kflow, "nd_nonexistent")


class TestSaveAndLoadDerivation:
    def test_save_and_load_derivation_roundtrip(self, tmp_kflow, sample_derivation_dict):
        inp_specs = [InputSpec(**i) for i in sample_derivation_dict["inputs"]]
        out_spec = OutputSpec(**sample_derivation_dict["output"])
        dv = Derivation(id=sample_derivation_dict["id"], summary=sample_derivation_dict["summary"],
                        inputs=inp_specs, output=out_spec)
        save_derivation(tmp_kflow, dv)
        loaded = load_derivation(tmp_kflow, "dv_d4e5f6")
        assert loaded.id == "dv_d4e5f6"
        assert loaded.summary == "构建事实库"
        assert len(loaded.inputs) == 2
        assert loaded.inputs[0].role == "提供预测框架"

    def test_load_nonexistent_derivation_raises(self, tmp_kflow):
        with pytest.raises(FileNotFoundError):
            load_derivation(tmp_kflow, "dv_nonexistent")


class TestLoadIndex:
    def test_load_empty_index(self, tmp_kflow):
        idx = load_index(tmp_kflow)
        assert len(idx.nodes) == 0
        assert len(idx.derivations) == 0

    def test_load_missing_index_triggers_reindex(self, tmp_kflow):
        (tmp_kflow / ".kflow" / "index.json").unlink()
        idx = load_index(tmp_kflow)
        assert len(idx.nodes) == 0  # empty because no node files exist

    def test_load_corrupt_index_triggers_reindex(self, tmp_kflow):
        (tmp_kflow / ".kflow" / "index.json").write_text("not valid json {{{")
        idx = load_index(tmp_kflow)
        assert len(idx.nodes) == 0


class TestSaveIndex:
    def test_save_index_writes_atomically(self, tmp_kflow):
        idx = Index(
            nodes={"nd_a": IndexNode(name="a", file=None, status="green",
                                      derivations_as_input=[], derivations_as_output=[])},
            derivations={},
        )
        save_index(tmp_kflow, idx)
        # Verify index.json exists and has correct content
        with open(tmp_kflow / ".kflow" / "index.json") as f:
            data = json.load(f)
        assert "nd_a" in data["nodes"]

    def test_save_index_no_tmp_leftover(self, tmp_kflow):
        idx = Index(nodes={}, derivations={})
        save_index(tmp_kflow, idx)
        assert not (tmp_kflow / ".kflow" / ".index.tmp").exists()


class TestReindex:
    def test_reindex_from_node_files(self, tmp_kflow, sample_node_dict):
        # Write a node file directly
        node = Node(**sample_node_dict)
        save_node(tmp_kflow, node)
        # Remove index.json
        (tmp_kflow / ".kflow" / "index.json").unlink()
        # Reindex
        result = reindex(tmp_kflow)
        assert result["node_count"] == 1
        assert result["derivation_count"] == 0
        # Verify index was rebuilt
        with open(tmp_kflow / ".kflow" / "index.json") as f:
            data = json.load(f)
        assert "nd_a1b2c3" in data["nodes"]

    def test_reindex_with_derivations(self, tmp_kflow, sample_node_dict, sample_derivation_dict):
        node = Node(**sample_node_dict)
        save_node(tmp_kflow, node)
        # Also save output node referenced by derivation
        out_node = Node(id="nd_m3n4o5", name="factbase", file="knowledge/factbase.md",
                        status="green", derivations_as_input=["dv_d4e5f6"], derivations_as_output=[])
        save_node(tmp_kflow, out_node)
        inp_specs = [InputSpec(**i) for i in sample_derivation_dict["inputs"]]
        out_spec = OutputSpec(**sample_derivation_dict["output"])
        dv = Derivation(id="dv_d4e5f6", summary="构建事实库", inputs=inp_specs, output=out_spec)
        save_derivation(tmp_kflow, dv)
        (tmp_kflow / ".kflow" / "index.json").unlink()
        result = reindex(tmp_kflow)
        assert result["node_count"] == 2
        assert result["derivation_count"] == 1


class TestAtomicWrite:
    def test_write_atomic_creates_file(self, tmp_path):
        dest = tmp_path / "test.json"
        write_atomic(dest, {"key": "value"})
        assert dest.exists()
        with open(dest) as f:
            data = json.load(f)
        assert data["key"] == "value"
