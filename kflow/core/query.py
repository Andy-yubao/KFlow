"""Stable read-only project, context, impact, and review queries."""

from __future__ import annotations

from pathlib import Path
from typing import TypedDict

from kflow.core.graph import GraphValidationError, KnowledgeGraph
from kflow.core.models import Derivation
from kflow.core.scan import ScanIssue, ScanResult, resolve_node_id, scan
from kflow.core.schema_versions import (
    PROJECT_GRAPH_SCHEMA_VERSION,
    TASK_QUERY_SCHEMA_VERSION,
)
from kflow.core.storage import StorageError


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


class StatusNode(NodeIdentity):
    """A Node annotated with its current review state."""

    changed_files: list[str]
    status: str | None
    reasons: list[str]


class DerivationRole(TypedDict):
    """One input or output role in an exposed Derivation."""

    node: str
    name: str
    short: str
    detail: str


class DerivationResult(TypedDict):
    """One complete, atomic Derivation safe for Agent consumption."""

    id: str
    short: str
    detail: str
    inputs: list[DerivationRole]
    outputs: list[DerivationRole]


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


class ContextResult(TypedDict):
    """One Node and its direct producing and consuming Derivations."""

    ok: bool
    schema_version: int
    node: StatusNode | None
    nodes: list[StatusNode]
    producing_derivation: DerivationResult | None
    consumer_derivations: list[DerivationResult]
    issues: list[QueryIssue]


class ImpactResult(TypedDict):
    """One Node's direct Derivations and more distant downstream Nodes."""

    ok: bool
    schema_version: int
    node: StatusNode | None
    direct_derivations: list[DerivationResult]
    direct_outputs: list[NodeIdentity]
    further_downstream: list[NodeIdentity]
    issues: list[QueryIssue]


class ReviewOrderResult(TypedDict):
    """Current needs-review Nodes in a project or downstream scope."""

    ok: bool
    schema_version: int
    scope: NodeIdentity | None
    nodes: list[StatusNode]
    review_order: list[str]
    issues: list[QueryIssue]


__all__ = [
    "ContextResult",
    "ImpactResult",
    "PROJECT_GRAPH_SCHEMA_VERSION",
    "ProjectGraphResult",
    "TASK_QUERY_SCHEMA_VERSION",
    "ReviewOrderResult",
    "present_derivation",
    "query_context",
    "query_impact",
    "query_project_graph",
    "query_review_order",
    "sorted_derivations",
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
    nodes = [_status_node(scanned, node_id) for node_id in graph.topological_order()]
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
        "schema_version": PROJECT_GRAPH_SCHEMA_VERSION,
        "project": {
            "status": status,
            "node_count": len(nodes),
            "derivation_count": len(derivations),
            "needs_review_count": needs_review_count,
            "issue_count": len(issues),
        },
        "nodes": nodes,
        "derivations": derivations,
        "topological_order": list(graph.topological_order()),
        "issues": issues,
    }


def query_context(root: Path, node_reference: str) -> ContextResult:
    """Return only one Node's direct producing and consuming relationships."""
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
        return _context_error(error, node_reference)

    producer = graph.producer_of(node_id)
    consumers = sorted_derivations(graph, graph.consumer_derivations(node_id))
    related_ids = {node_id}
    relationships = (*(() if producer is None else (producer,)), *consumers)
    for derivation in relationships:
        related_ids.update(item.node for item in derivation.inputs)
        related_ids.update(item.node for item in derivation.outputs)
    nodes = [
        _status_node(scanned, candidate)
        for candidate in graph.topological_order()
        if candidate in related_ids
    ]
    return {
        "ok": not scanned.issues,
        "schema_version": TASK_QUERY_SCHEMA_VERSION,
        "node": _status_node(scanned, node_id),
        "nodes": nodes,
        "producing_derivation": (
            None if producer is None else present_derivation(graph, producer)
        ),
        "consumer_derivations": [
            present_derivation(graph, derivation) for derivation in consumers
        ],
        "issues": [_issue_result(issue) for issue in scanned.issues],
    }


def query_impact(root: Path, node_reference: str) -> ImpactResult:
    """Return direct consumer Derivations and the Nodes beyond direct outputs."""
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
        return _impact_error(error, node_reference)

    direct_derivations = sorted_derivations(graph, graph.consumer_derivations(node_id))
    direct_output_ids = {
        output.node
        for derivation in direct_derivations
        for output in derivation.outputs
    }
    reachable = set(graph.downstream(node_id))
    further_ids = reachable - direct_output_ids - {node_id}
    return {
        "ok": not scanned.issues,
        "schema_version": TASK_QUERY_SCHEMA_VERSION,
        "node": _status_node(scanned, node_id),
        "direct_derivations": [
            present_derivation(graph, derivation) for derivation in direct_derivations
        ],
        "direct_outputs": [
            _node_identity(graph, candidate)
            for candidate in graph.topological_order()
            if candidate in direct_output_ids
        ],
        "further_downstream": [
            _node_identity(graph, candidate)
            for candidate in graph.topological_order()
            if candidate in further_ids
        ],
        "issues": [_issue_result(issue) for issue in scanned.issues],
    }


def query_review_order(
    root: Path, node_reference: str | None = None
) -> ReviewOrderResult:
    """Return current needs-review Nodes in project or inclusive downstream scope."""
    try:
        scanned = scan(root)
        graph = scanned.graph
        if node_reference is None:
            scope_id = None
            included = set(graph.nodes)
        else:
            scope_id = resolve_node_id(graph, node_reference)
            included = set(graph.downstream(scope_id))
    except (
        GraphValidationError,
        KeyError,
        StorageError,
        TypeError,
        ValueError,
    ) as error:
        return _review_order_error(error, node_reference)

    review_ids = [
        node_id
        for node_id in graph.topological_order()
        if node_id in included and _needs_review(scanned, node_id)
    ]
    return {
        "ok": not scanned.issues,
        "schema_version": TASK_QUERY_SCHEMA_VERSION,
        "scope": None if scope_id is None else _node_identity(graph, scope_id),
        "nodes": [_status_node(scanned, node_id) for node_id in review_ids],
        "review_order": review_ids,
        "issues": [_issue_result(issue) for issue in scanned.issues],
    }


def sorted_derivations(
    graph: KnowledgeGraph, derivations: tuple[Derivation, ...] | None = None
) -> tuple[Derivation, ...]:
    """Sort Derivations by output topology, then by stable internal ID."""
    candidates = (
        tuple(graph.derivations.values()) if derivations is None else derivations
    )
    positions = {
        node_id: position for position, node_id in enumerate(graph.topological_order())
    }

    def key(derivation: Derivation) -> tuple[tuple[int, ...], str]:
        outputs = tuple(sorted(positions[item.node] for item in derivation.outputs))
        return outputs, derivation.id

    return tuple(sorted(candidates, key=key))


def present_derivation(
    graph: KnowledgeGraph, derivation: Derivation
) -> DerivationResult:
    """Present one complete Derivation using canonical Node ID role ordering."""
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


def _needs_review(scanned: ScanResult, node_id: str) -> bool:
    status = scanned.statuses.get(node_id)
    return status is not None and status.needs_review


def _node_identity(graph: KnowledgeGraph, node_id: str) -> NodeIdentity:
    node = graph.nodes[node_id]
    return {"id": node.id, "name": node.name, "files": list(node.files)}


def _status_node(scanned: ScanResult, node_id: str) -> StatusNode:
    status = scanned.statuses.get(node_id)
    return {
        **_node_identity(scanned.graph, node_id),
        "changed_files": [] if status is None else list(status.changed_files),
        "status": None if status is None else status.status,
        "reasons": [] if status is None else list(status.reasons),
    }


def _issues_from_error(error: Exception, reference: str | None) -> list[QueryIssue]:
    if isinstance(error, GraphValidationError):
        return [
            {
                "code": issue.code,
                "message": issue.message,
                "references": list(issue.references),
            }
            for issue in error.issues
        ]
    code = "unknown_node" if isinstance(error, KeyError) else "invalid_project"
    return [
        {
            "code": code,
            "message": str(error).strip("'"),
            "references": [] if reference is None else [reference],
        }
    ]


def _context_error(error: Exception, reference: str) -> ContextResult:
    return {
        "ok": False,
        "schema_version": TASK_QUERY_SCHEMA_VERSION,
        "node": None,
        "nodes": [],
        "producing_derivation": None,
        "consumer_derivations": [],
        "issues": _issues_from_error(error, reference),
    }


def _impact_error(error: Exception, reference: str) -> ImpactResult:
    return {
        "ok": False,
        "schema_version": TASK_QUERY_SCHEMA_VERSION,
        "node": None,
        "direct_derivations": [],
        "direct_outputs": [],
        "further_downstream": [],
        "issues": _issues_from_error(error, reference),
    }


def _review_order_error(error: Exception, reference: str | None) -> ReviewOrderResult:
    return {
        "ok": False,
        "schema_version": TASK_QUERY_SCHEMA_VERSION,
        "scope": None,
        "nodes": [],
        "review_order": [],
        "issues": _issues_from_error(error, reference),
    }


def _project_graph_error(error: Exception) -> ProjectGraphResult:
    issues = _issues_from_error(error, None)
    return {
        "ok": False,
        "schema_version": PROJECT_GRAPH_SCHEMA_VERSION,
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


def _issue_result(issue: ScanIssue) -> QueryIssue:
    return {
        "code": issue.code,
        "message": issue.message,
        "references": list(issue.references),
    }
