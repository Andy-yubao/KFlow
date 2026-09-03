import ast
from pathlib import Path

import kflow.core.storage as storage
from kflow.core.schema_versions import (
    CONTEXT_SCHEMA_VERSION,
    IMPACT_SCHEMA_VERSION,
    METADATA_SCHEMA_VERSION,
    MUTATION_SCHEMA_VERSION,
    PROJECT_GRAPH_SCHEMA_VERSION,
    REVIEW_ORDER_SCHEMA_VERSION,
    TASK_QUERY_SCHEMA_VERSION,
)


def test_protocol_versions_are_explicit_independent_constants() -> None:
    assert METADATA_SCHEMA_VERSION == 3
    assert PROJECT_GRAPH_SCHEMA_VERSION == 3
    assert CONTEXT_SCHEMA_VERSION == 4
    assert IMPACT_SCHEMA_VERSION == 4
    assert MUTATION_SCHEMA_VERSION == 4
    assert REVIEW_ORDER_SCHEMA_VERSION == 3
    assert TASK_QUERY_SCHEMA_VERSION == 3
    assert not hasattr(storage, "SCHEMA_VERSION")

    source = Path("kflow/core/schema_versions.py").read_text(encoding="utf-8")
    assignments = {
        node.targets[0].id: node.value
        for node in ast.parse(source).body
        if isinstance(node, ast.Assign)
        and len(node.targets) == 1
        and isinstance(node.targets[0], ast.Name)
    }
    for name in (
        "METADATA_SCHEMA_VERSION",
        "PROJECT_GRAPH_SCHEMA_VERSION",
        "CONTEXT_SCHEMA_VERSION",
        "IMPACT_SCHEMA_VERSION",
        "MUTATION_SCHEMA_VERSION",
        "REVIEW_ORDER_SCHEMA_VERSION",
        "TASK_QUERY_SCHEMA_VERSION",
    ):
        assert isinstance(assignments[name], ast.Constant)
