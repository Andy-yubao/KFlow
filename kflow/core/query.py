"""Stable read-only context and impact queries for KFlow."""

from __future__ import annotations

import heapq
from collections import deque
from pathlib import Path
from typing import Final, TypedDict

from kflow.core.graph import GraphValidationError, KnowledgeGraph
from kflow.core.models import Derivation
from kflow.core.scan import ScanIssue, ScanResult, resolve_node_id, scan
from kflow.core.storage import SCHEMA_VERSION, StorageError


class QueryIssue(TypedDict):
    """One machine-readable query or validation problem."""

    code: str
    message: str
    references: list[str]


class NodeIdentity(TypedDict):
    """Stable Node identity exposed by the query API."""

    id: str
    name: str
    files: list[str]


class NodeResult(NodeIdentity):
    """A queried Node plus changed paths detected by the current scan."""

    changed_files: list[str]


class StatusNode(NodeResult):
    """A Node annotated with its current review state."""

    status: str | None
    reasons: list[str]


class ImpactPath(TypedDict):
    """One explicit downstream path from a change root."""

    root: str
    nodes: list[str]
    derivations: list[str]


class AffectedNode(StatusNode):
    """A downstream Node annotated with impact provenance."""

    depth: int
    roots: list[str]
    impact_reason: str
    paths: list[ImpactPath]


class DerivationRole(TypedDict):
    """One input or output role in an exposed Derivation."""

    node: str
    name: str
    short: str
    detail: str


class DerivationResult(TypedDict):
    """Explicit Derivation facts safe for Agent consumption."""

    id: str
    short: str
    detail: str
    inputs: list[DerivationRole]
    outputs: list[DerivationRole]


class RelationsResult(TypedDict):
    """Topology related to the query target."""

    upstream: list[NodeIdentity]
    downstream: list[NodeIdentity]
    derivations: list[DerivationResult]


class ImpactResult(TypedDict):
    """Change roots and the downstream Nodes they may affect."""

    changed_nodes: list[StatusNode]
    affected_nodes: list[AffectedNode]


class QueryResult(TypedDict):
    """Frozen machine-contract result shared by all public query functions."""

    ok: bool
    schema_version: int
    node: NodeResult | None
    status: str | None
    reasons: list[str]
    relations: RelationsResult
    impact: ImpactResult
    review_order: list[str]
    issues: list[QueryIssue]


class ProjectSummary(TypedDict):
    """Stable project-level counts and health state."""

    status: str
    node_count: int
    derivation_count: int
    needs_review_count: int
    issue_count: int


class ProjectGraphResult(TypedDict):
    """Complete read-only project graph shared by every interface."""

    ok: bool
    schema_version: int
    project: ProjectSummary
    nodes: list[StatusNode]
    derivations: list[DerivationResult]
    topological_order: list[str]
    issues: list[QueryIssue]


QUERY_SCHEMA_FIELDS: Final[frozenset[str]] = frozenset(
    {
        "ok",
        "schema_version",
        "node",
        "status",
        "reasons",
        "relations",
        "impact",
        "review_order",
        "issues",
    }
)

__all__ = [
    "QUERY_SCHEMA_FIELDS",
    "ProjectGraphResult",
    "QueryResult",
    "present_derivation",
    "query_affected_context",
    "query_context",
    "query_impact",
    "query_project_graph",
]


def query_project_graph(root: Path) -> ProjectGraphResult:
    """Return every Node and Derivation with current status and stable ordering."""
    try:
        scanned = scan(root)
    except (
        GraphValidationError,
        KeyError,
        StorageError,
        TypeError,
        ValueError,
    ) as error:
        return _project_graph_error(error)

    graph = scanned.graph
    topological_order = list(graph.topological_order())
    nodes = [_status_node(scanned, node_id) for node_id in topological_order]
    derivations = [
        present_derivation(graph, graph.derivations[derivation_id])
        for derivation_id in sorted(graph.derivations)
    ]
    issues = [_issue_result(issue) for issue in scanned.issues]
    needs_review_count = sum(bool(node["reasons"]) for node in nodes)
    status = (
        "invalid"
        if issues
        else "attention_required"
        if needs_review_count
        else "current"
    )
    return {
        "ok": not issues,
        "schema_version": SCHEMA_VERSION,
        "project": {
            "status": status,
            "node_count": len(nodes),
            "derivation_count": len(derivations),
            "needs_review_count": needs_review_count,
            "issue_count": len(issues),
        },
        "nodes": nodes,
        "derivations": derivations,
        "topological_order": topological_order,
        "issues": issues,
    }


def query_context(root: Path, node_reference: str) -> QueryResult:
    """Return one Node's stable status and topology contract.

    ``node_reference`` accepts a stable Node ID, unique Node name, or registered
    repository-relative file path. Failures are returned in the same
    :class:`QueryResult` shape with ``ok=False``; registered file contents are
    never included.
    """
    try:
        scanned = scan(root)
        graph = scanned.graph
        node_id = resolve_node_id(graph, node_reference)
    except (
        GraphValidationError,
        KeyError,
        StorageError,
        TypeError,
        ValueError,
    ) as error:
        return _error_result(error, node_reference)

    upstream_ids = tuple(
        candidate for candidate in graph.upstream(node_id) if candidate != node_id
    )
    impact = _build_impact(scanned, (node_id,))
    downstream_ids = tuple(item["id"] for item in impact["affected_nodes"])

    derivation_ids: set[str] = set()
    for candidate in (*upstream_ids, node_id, *downstream_ids):
        producer = graph.producer_of(candidate)
        if producer is not None:
            derivation_ids.add(producer.id)

    status = scanned.statuses.get(node_id)
    return _query_result(
        scanned,
        node=_node_result(scanned, node_id),
        status=None if status is None else status.status,
        reasons=[] if status is None else list(status.reasons),
        upstream=[_node_identity(graph, candidate) for candidate in upstream_ids],
        downstream=[_node_identity(graph, candidate) for candidate in downstream_ids],
        derivations=[
            present_derivation(graph, graph.derivations[derivation_id])
            for derivation_id in sorted(derivation_ids)
        ],
        impact=impact,
        review_order=[
            candidate for candidate in impact["review_order"] if candidate != node_id
        ],
    )


def query_affected_context(root: Path) -> QueryResult:
    """Return current change roots and the remaining affected review scope.

    A valid project with no active change roots returns a successful, empty
    result. Invalid or uninitialized projects retain the same result shape and
    report a machine-readable issue.
    """
    try:
        scanned = scan(root)
    except (
        GraphValidationError,
        KeyError,
        StorageError,
        TypeError,
        ValueError,
    ) as error:
        return _error_result(error, None)

    graph = scanned.graph
    changed_root_ids = tuple(
        node_id
        for node_id in graph.topological_order()
        if _is_change_root(scanned, node_id)
    )
    traversal_roots = _remaining_change_roots(scanned, changed_root_ids)
    project_impact = _build_impact(scanned, traversal_roots)
    review_ids = tuple(project_impact["review_order"])
    affected_nodes = [
        item for item in project_impact["affected_nodes"] if item["id"] in review_ids
    ]
    changed_nodes = [
        _status_node(scanned, node_id)
        for node_id in changed_root_ids
        if node_id in review_ids
    ]
    derivation_ids = {
        derivation_id
        for item in affected_nodes
        for path in item["paths"]
        for derivation_id in path["derivations"]
    }
    impact = {
        "changed_nodes": changed_nodes,
        "affected_nodes": affected_nodes,
        "review_order": review_ids,
    }
    reasons = sorted(
        {
            reason
            for node_id in review_ids
            for reason in scanned.statuses[node_id].reasons
        }
    )
    return _query_result(
        scanned,
        node=None,
        status="affected" if review_ids else "confirmed",
        reasons=reasons,
        upstream=[],
        downstream=[_node_identity(graph, node_id) for node_id in review_ids],
        derivations=[
            present_derivation(graph, graph.derivations[derivation_id])
            for derivation_id in sorted(derivation_ids)
        ],
        impact=impact,
        review_order=list(review_ids),
    )


def query_impact(root: Path, node_reference: str | None = None) -> QueryResult:
    """Explain explicit or currently detected downstream impact.

    When ``node_reference`` is omitted, file and producing-Derivation changes are
    used as roots. An explicit reference is always traversed, regardless of
    status, and accepts a Node ID, unique name, or registered repository-relative
    file path. Errors use the same stable :class:`QueryResult` envelope.
    """
    try:
        scanned = scan(root)
        graph = scanned.graph
        if node_reference is None:
            root_ids = tuple(
                node_id
                for node_id in graph.topological_order()
                if _is_change_root(scanned, node_id)
            )
        else:
            root_ids = (resolve_node_id(graph, node_reference),)
    except (
        GraphValidationError,
        KeyError,
        StorageError,
        TypeError,
        ValueError,
    ) as error:
        return _error_result(error, node_reference)

    impact = _build_impact(scanned, root_ids)
    target_id = root_ids[0] if node_reference is not None else None
    target_status = None if target_id is None else scanned.statuses.get(target_id)
    affected_ids = tuple(item["id"] for item in impact["affected_nodes"])
    derivation_ids = {
        derivation_id
        for item in impact["affected_nodes"]
        for path in item["paths"]
        for derivation_id in path["derivations"]
    }
    project_reasons = sorted(
        {reason for item in impact["changed_nodes"] for reason in item["reasons"]}
    )
    return _query_result(
        scanned,
        node=None if target_id is None else _node_result(scanned, target_id),
        status=(
            ("affected" if impact["review_order"] else "confirmed")
            if target_id is None
            else (None if target_status is None else target_status.status)
        ),
        reasons=(
            project_reasons
            if target_id is None
            else ([] if target_status is None else list(target_status.reasons))
        ),
        upstream=[],
        downstream=[_node_identity(graph, candidate) for candidate in affected_ids],
        derivations=[
            present_derivation(graph, graph.derivations[derivation_id])
            for derivation_id in sorted(derivation_ids)
        ],
        impact=impact,
        review_order=impact["review_order"],
    )


def _query_result(
    scanned: ScanResult,
    *,
    node: NodeResult | None,
    status: str | None,
    reasons: list[str],
    upstream: list[NodeIdentity],
    downstream: list[NodeIdentity],
    derivations: list[DerivationResult],
    impact: ImpactResult,
    review_order: list[str],
) -> QueryResult:
    result: QueryResult = {
        "ok": not scanned.issues,
        "schema_version": SCHEMA_VERSION,
        "node": node,
        "status": status,
        "reasons": reasons,
        "relations": {
            "upstream": upstream,
            "downstream": downstream,
            "derivations": derivations,
        },
        "impact": {
            "changed_nodes": impact["changed_nodes"],
            "affected_nodes": impact["affected_nodes"],
        },
        "review_order": review_order,
        "issues": [_issue_result(issue) for issue in scanned.issues],
    }
    assert set(result) == QUERY_SCHEMA_FIELDS
    return result


def _error_result(error: Exception, reference: str | None) -> QueryResult:
    if isinstance(error, GraphValidationError):
        issues: list[QueryIssue] = [
            {
                "code": issue.code,
                "message": issue.message,
                "references": list(issue.references),
            }
            for issue in error.issues
        ]
    else:
        code = "unknown_node" if isinstance(error, KeyError) else "invalid_project"
        issues = [
            {
                "code": code,
                "message": str(error).strip("'"),
                "references": [] if reference is None else [reference],
            }
        ]
    return {
        "ok": False,
        "schema_version": SCHEMA_VERSION,
        "node": None,
        "status": "error",
        "reasons": [],
        "relations": {"upstream": [], "downstream": [], "derivations": []},
        "impact": {"changed_nodes": [], "affected_nodes": []},
        "review_order": [],
        "issues": issues,
    }


def _project_graph_error(error: Exception) -> ProjectGraphResult:
    if isinstance(error, GraphValidationError):
        issues = [
            {
                "code": issue.code,
                "message": issue.message,
                "references": list(issue.references),
            }
            for issue in error.issues
        ]
    else:
        issues = [
            {
                "code": "invalid_project",
                "message": str(error).strip("'"),
                "references": [],
            }
        ]
    return {
        "ok": False,
        "schema_version": SCHEMA_VERSION,
        "project": {
            "status": "invalid",
            "node_count": 0,
            "derivation_count": 0,
            "needs_review_count": 0,
            "issue_count": len(issues),
        },
        "nodes": [],
        "derivations": [],
        "topological_order": [],
        "issues": issues,
    }


def _build_impact(scanned: ScanResult, root_ids: tuple[str, ...]) -> dict:
    graph = scanned.graph
    impact: dict[str, dict] = {}
    for root_id in root_ids:
        paths = _shortest_paths(graph, root_id)
        for target_id, path in paths.items():
            if target_id == root_id:
                continue
            entry = impact.setdefault(
                target_id,
                {"depth": len(path["derivations"]), "roots": [], "paths": []},
            )
            entry["depth"] = min(entry["depth"], len(path["derivations"]))
            entry["roots"].append(root_id)
            entry["paths"].append({"root": root_id, **path})

    affected_ids = tuple(
        node_id for node_id in graph.topological_order() if node_id in impact
    )
    related_ids = set(root_ids) | set(affected_ids)
    distances = {node_id: 0 for node_id in root_ids}
    for node_id, entry in impact.items():
        distances.setdefault(node_id, entry["depth"])
    review_order = _review_order(scanned, related_ids, distances)

    affected_nodes = []
    for node_id in affected_ids:
        status = scanned.statuses.get(node_id)
        entry = impact[node_id]
        affected_nodes.append(
            {
                **_node_identity(graph, node_id),
                "status": None if status is None else status.status,
                "reasons": [] if status is None else list(status.reasons),
                "changed_files": [] if status is None else list(status.changed_files),
                "depth": entry["depth"],
                "roots": entry["roots"],
                "impact_reason": (
                    "input_changed" if entry["depth"] == 1 else "upstream_changed"
                ),
                "paths": entry["paths"],
            }
        )

    return {
        "changed_nodes": [_status_node(scanned, node_id) for node_id in root_ids],
        "affected_nodes": affected_nodes,
        "review_order": review_order,
    }


def _shortest_paths(graph: KnowledgeGraph, root_id: str) -> dict[str, dict]:
    paths = {root_id: {"nodes": [root_id], "derivations": []}}
    queue = deque([root_id])
    while queue:
        node_id = queue.popleft()
        for target_id, derivation_id in _outgoing_edges(graph, node_id):
            if target_id in paths:
                continue
            paths[target_id] = {
                "nodes": [*paths[node_id]["nodes"], target_id],
                "derivations": [*paths[node_id]["derivations"], derivation_id],
            }
            queue.append(target_id)
    return paths


def _outgoing_edges(graph: KnowledgeGraph, node_id: str) -> tuple[tuple[str, str], ...]:
    edges = (
        (output.node, derivation.id)
        for derivation in graph.consumer_derivations(node_id)
        for output in derivation.outputs
    )
    return tuple(sorted(edges))


def _review_order(
    scanned: ScanResult, related_ids: set[str], distances: dict[str, int]
) -> list[str]:
    relevant = {node_id for node_id in related_ids if _needs_review(scanned, node_id)}
    adjacency = {node_id: set() for node_id in relevant}
    in_degree = {node_id: 0 for node_id in relevant}
    for node_id in relevant:
        for target_id, _derivation_id in _outgoing_edges(scanned.graph, node_id):
            if target_id not in relevant or target_id in adjacency[node_id]:
                continue
            adjacency[node_id].add(target_id)
            in_degree[target_id] += 1

    ready = [
        (distances[node_id], node_id)
        for node_id, degree in in_degree.items()
        if degree == 0
    ]
    heapq.heapify(ready)
    result = []
    while ready:
        _distance, node_id = heapq.heappop(ready)
        result.append(node_id)
        for target_id in sorted(adjacency[node_id]):
            in_degree[target_id] -= 1
            if in_degree[target_id] == 0:
                heapq.heappush(ready, (distances[target_id], target_id))
    return result


def _is_change_root(scanned: ScanResult, node_id: str) -> bool:
    status = scanned.statuses.get(node_id)
    if status is None:
        return False
    return bool({"files_changed", "derivation_changed"} & set(status.reasons))


def _remaining_change_roots(
    scanned: ScanResult, changed_root_ids: tuple[str, ...]
) -> tuple[str, ...]:
    """Recover reviewed roots still visible in downstream input baselines."""
    candidates = set(changed_root_ids)
    for node_id, status in scanned.statuses.items():
        if "input_changed" not in status.reasons:
            continue
        producer = scanned.graph.producer_of(node_id)
        confirmation = scanned.confirmations.get(node_id)
        if producer is None or confirmation is None:
            continue
        confirmed_inputs = {
            item.node: item.effective_version for item in confirmation.inputs
        }
        candidates.update(
            item.node
            for item in producer.inputs
            if confirmed_inputs.get(item.node)
            != scanned.effective_versions.get(item.node)
        )

    topmost = {
        candidate
        for candidate in candidates
        if not any(
            candidate in scanned.graph.downstream(other)
            for other in candidates
            if other != candidate
        )
    }
    return tuple(
        node_id for node_id in scanned.graph.topological_order() if node_id in topmost
    )


def _needs_review(scanned: ScanResult, node_id: str) -> bool:
    status = scanned.statuses.get(node_id)
    return status is not None and status.needs_review


def _node_identity(graph: KnowledgeGraph, node_id: str) -> NodeIdentity:
    node = graph.nodes[node_id]
    return {"id": node.id, "name": node.name, "files": list(node.files)}


def _node_result(scanned: ScanResult, node_id: str) -> NodeResult:
    status = scanned.statuses.get(node_id)
    return {
        **_node_identity(scanned.graph, node_id),
        "changed_files": [] if status is None else list(status.changed_files),
    }


def _status_node(scanned: ScanResult, node_id: str) -> StatusNode:
    status = scanned.statuses.get(node_id)
    return {
        **_node_result(scanned, node_id),
        "status": None if status is None else status.status,
        "reasons": [] if status is None else list(status.reasons),
    }


def present_derivation(
    graph: KnowledgeGraph, derivation: Derivation
) -> DerivationResult:
    """Present one complete Derivation using the stable machine contract."""
    return {
        "id": derivation.id,
        "short": derivation.short,
        "detail": derivation.detail,
        "inputs": [
            {
                "node": item.node,
                "name": graph.nodes[item.node].name,
                "short": item.short,
                "detail": item.detail,
            }
            for item in sorted(derivation.inputs, key=lambda role: role.node)
        ],
        "outputs": [
            {
                "node": item.node,
                "name": graph.nodes[item.node].name,
                "short": item.short,
                "detail": item.detail,
            }
            for item in sorted(derivation.outputs, key=lambda role: role.node)
        ],
    }


def _issue_result(issue: ScanIssue) -> QueryIssue:
    return {
        "code": issue.code,
        "message": issue.message,
        "references": list(issue.references),
    }
