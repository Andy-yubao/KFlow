"""Pure structural comparison for two public KFlow project graphs."""

from __future__ import annotations

from typing import TypedDict

from kflow.core.query import DerivationResult, ProjectGraphResult, QueryIssue


class StructuralNode(TypedDict):
    id: str
    name: str
    files: list[str]


class ChangedNode(TypedDict):
    id: str
    changed_fields: list[str]
    before: StructuralNode
    after: StructuralNode


class ChangedDerivation(TypedDict):
    id: str
    changed_fields: list[str]
    before: DerivationResult
    after: DerivationResult


class DiffSummary(TypedDict):
    added_nodes: int
    removed_nodes: int
    changed_nodes: int
    added_derivations: int
    removed_derivations: int
    changed_derivations: int
    topology_changed: bool


class NodeDiff(TypedDict):
    added: list[StructuralNode]
    removed: list[StructuralNode]
    changed: list[ChangedNode]


class DerivationDiff(TypedDict):
    added: list[DerivationResult]
    removed: list[DerivationResult]
    changed: list[ChangedDerivation]


class GraphComparison(TypedDict):
    summary: DiffSummary
    nodes: NodeDiff
    derivations: DerivationDiff
    before_topological_order: list[str]
    after_topological_order: list[str]


class GraphDiffBase(TypedDict):
    reference: str
    commit: str
    short_commit: str
    subject: str
    committed_at: str


class GraphDiffResult(TypedDict):
    ok: bool
    available: bool
    schema_version: int
    base: GraphDiffBase | None
    summary: DiffSummary | None
    nodes: NodeDiff
    derivations: DerivationDiff
    before_topological_order: list[str]
    after_topological_order: list[str]
    issues: list[QueryIssue]


GRAPH_DIFF_SCHEMA_VERSION = 2
NODE_FIELDS = ("name", "files")
DERIVATION_FIELDS = ("short", "detail", "inputs", "outputs")


def compare_project_graphs(
    before: ProjectGraphResult, after: ProjectGraphResult
) -> GraphComparison:
    """Compare public structure only; review status is intentionally ignored."""
    before_nodes = {node["id"]: _structural_node(node) for node in before["nodes"]}
    after_nodes = {node["id"]: _structural_node(node) for node in after["nodes"]}
    node_added = [
        after_nodes[node_id] for node_id in sorted(after_nodes.keys() - before_nodes)
    ]
    node_removed = [
        before_nodes[node_id] for node_id in sorted(before_nodes.keys() - after_nodes)
    ]
    node_changed: list[ChangedNode] = []
    for node_id in sorted(before_nodes.keys() & after_nodes):
        old = before_nodes[node_id]
        new = after_nodes[node_id]
        changed_fields = [field for field in NODE_FIELDS if old[field] != new[field]]
        if changed_fields:
            node_changed.append(
                {
                    "id": node_id,
                    "changed_fields": changed_fields,
                    "before": old,
                    "after": new,
                }
            )

    before_derivations = {
        item["id"]: _structural_derivation(item) for item in before["derivations"]
    }
    after_derivations = {
        item["id"]: _structural_derivation(item) for item in after["derivations"]
    }
    derivation_added = [
        after_derivations[item_id]
        for item_id in sorted(after_derivations.keys() - before_derivations)
    ]
    derivation_removed = [
        before_derivations[item_id]
        for item_id in sorted(before_derivations.keys() - after_derivations)
    ]
    derivation_changed: list[ChangedDerivation] = []
    for item_id in sorted(before_derivations.keys() & after_derivations):
        old = before_derivations[item_id]
        new = after_derivations[item_id]
        changed_fields = [
            field for field in DERIVATION_FIELDS if old[field] != new[field]
        ]
        if changed_fields:
            derivation_changed.append(
                {
                    "id": item_id,
                    "changed_fields": changed_fields,
                    "before": old,
                    "after": new,
                }
            )

    before_order = list(before["topological_order"])
    after_order = list(after["topological_order"])
    topology_changed = before_order != after_order
    return {
        "summary": {
            "added_nodes": len(node_added),
            "removed_nodes": len(node_removed),
            "changed_nodes": len(node_changed),
            "added_derivations": len(derivation_added),
            "removed_derivations": len(derivation_removed),
            "changed_derivations": len(derivation_changed),
            "topology_changed": topology_changed,
        },
        "nodes": {
            "added": node_added,
            "removed": node_removed,
            "changed": node_changed,
        },
        "derivations": {
            "added": derivation_added,
            "removed": derivation_removed,
            "changed": derivation_changed,
        },
        "before_topological_order": before_order,
        "after_topological_order": after_order,
    }


def unavailable_graph_diff(code: str, message: str) -> GraphDiffResult:
    """Return the stable, expected capability-degradation shape."""
    return {
        "ok": True,
        "available": False,
        "schema_version": GRAPH_DIFF_SCHEMA_VERSION,
        "base": None,
        "summary": None,
        "nodes": {"added": [], "removed": [], "changed": []},
        "derivations": {"added": [], "removed": [], "changed": []},
        "before_topological_order": [],
        "after_topological_order": [],
        "issues": [{"code": code, "message": message, "references": []}],
    }


def _structural_node(node: dict) -> StructuralNode:
    return {
        "id": node["id"],
        "name": node["name"],
        "files": sorted(node["files"]),
    }


def _structural_derivation(derivation: DerivationResult) -> DerivationResult:
    return {
        "id": derivation["id"],
        "short": derivation["short"],
        "detail": derivation["detail"],
        "inputs": _structural_roles(derivation["inputs"]),
        "outputs": _structural_roles(derivation["outputs"]),
    }


def _structural_roles(roles: list[dict]) -> list[dict]:
    return [
        {
            "node": role["node"],
            "name": role["name"],
            "short": role["short"],
            "detail": role["detail"],
        }
        for role in sorted(roles, key=lambda item: item["node"])
    ]
