"""Shared fixtures for KFlow tests."""
import json
import pytest


@pytest.fixture
def tmp_kflow(tmp_path):
    """Create a temporary KFlow project directory with .kflow/ structure."""
    kflow_dir = tmp_path / ".kflow"
    nodes_dir = kflow_dir / "nodes"
    derivations_dir = kflow_dir / "derivations"
    knowledge_dir = tmp_path / "knowledge"

    kflow_dir.mkdir()
    nodes_dir.mkdir()
    derivations_dir.mkdir()
    knowledge_dir.mkdir()

    index = {"nodes": {}, "derivations": {}}
    (kflow_dir / "index.json").write_text(json.dumps(index))

    return tmp_path


@pytest.fixture
def sample_node_dict():
    return {
        "id": "nd_a1b2c3",
        "name": "architecture",
        "file": "knowledge/architecture.md",
        "status": "green",
        "derivations_as_input": [],
        "derivations_as_output": [],
    }


@pytest.fixture
def sample_derivation_dict():
    return {
        "id": "dv_d4e5f6",
        "summary": "构建事实库",
        "inputs": [
            {"node": "nd_a1b2c3", "role": "提供预测框架", "role_detail": "详细说明A"},
            {"node": "nd_j1k2l3", "role": "提供参数", "role_detail": "详细说明B"},
        ],
        "output": {"node": "nd_m3n4o5", "method": "依据模型组织数据", "method_detail": "详细说明C"},
    }
