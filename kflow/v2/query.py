"""Read-only context and impact explanations for KFlow v2."""

from __future__ import annotations

import heapq
from collections import deque
from pathlib import Path

from kflow.v2.graph import KnowledgeGraph
from kflow.v2.models import Derivation
from kflow.v2.scan import ScanIssue, ScanResult, resolve_node_id, scan


def query_context(root: Path, node_reference: str) -> dict:
    """Return one Node's status and relevant topology without file contents."""
    scanned = scan(root)
    graph = scanned.graph
    node_id = resolve_node_id(graph, node_reference)
    upstream_ids = tuple(
        candidate for candidate in graph.upstream(node_id) if candidate != node_id
    )
    downstream_depths = graph.downstream(node_id)
    downstream_ids = tuple(
        candidate
        for candidate in graph.topological_order()
        if candidate != node_id and candidate in downstream_depths
    )

    derivation_ids: set[str] = set()
    for candidate in (*upstream_ids, node_id, *downstream_ids):
        producer = graph.producer_of(candidate)
        if producer is not None:
            derivation_ids.add(producer.id)

    return {
        "ok": not scanned.issues,
        "schema_version": 2,
        "node": _status_node(scanned, node_id),
        "upstream": [_node_identity(graph, candidate) for candidate in upstream_ids],
        "downstream": [
            {
                **_node_identity(graph, candidate),
                "depth": downstream_depths[candidate],
            }
            for candidate in downstream_ids
        ],
        "derivations": [
            _derivation_result(graph, graph.derivations[derivation_id])
            for derivation_id in sorted(derivation_ids)
        ],
        "issues": [_issue_result(issue) for issue in scanned.issues],
    }


def query_impact(root: Path, node_reference: str | None = None) -> dict:
    """Explain explicit or currently detected downstream impact.

    When ``node_reference`` is omitted, file and producing-Derivation changes are
    used as roots. An explicit Node is always traversed, regardless of status.
    """
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

    impact: dict[str, dict] = {}
    for root_id in root_ids:
        paths = _shortest_paths(graph, root_id)
        for target_id, path in paths.items():
            if target_id == root_id:
                continue
            entry = impact.setdefault(
                target_id,
                {
                    "depth": len(path["derivations"]),
                    "roots": [],
                    "paths": [],
                },
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
                "status_reasons": [] if status is None else list(status.reasons),
                "changed_files": ([] if status is None else list(status.changed_files)),
                "depth": entry["depth"],
                "roots": entry["roots"],
                "impact_reason": (
                    "input_changed" if entry["depth"] == 1 else "upstream_changed"
                ),
                "paths": entry["paths"],
            }
        )

    return {
        "ok": not scanned.issues,
        "schema_version": 2,
        "changed_nodes": [_status_node(scanned, node_id) for node_id in root_ids],
        "affected_nodes": affected_nodes,
        "review_order": review_order,
        "issues": [_issue_result(issue) for issue in scanned.issues],
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
                "derivations": [
                    *paths[node_id]["derivations"],
                    derivation_id,
                ],
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


def _needs_review(scanned: ScanResult, node_id: str) -> bool:
    status = scanned.statuses.get(node_id)
    return status is not None and status.needs_review


def _node_identity(graph: KnowledgeGraph, node_id: str) -> dict:
    node = graph.nodes[node_id]
    return {"id": node.id, "name": node.name, "files": list(node.files)}


def _status_node(scanned: ScanResult, node_id: str) -> dict:
    status = scanned.statuses.get(node_id)
    return {
        **_node_identity(scanned.graph, node_id),
        "status": None if status is None else status.status,
        "reasons": [] if status is None else list(status.reasons),
        "changed_files": [] if status is None else list(status.changed_files),
    }


def _derivation_result(graph: KnowledgeGraph, derivation: Derivation) -> dict:
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
            for item in derivation.inputs
        ],
        "outputs": [
            {
                "node": item.node,
                "name": graph.nodes[item.node].name,
                "short": item.short,
                "detail": item.detail,
            }
            for item in derivation.outputs
        ],
    }


def _issue_result(issue: ScanIssue) -> dict:
    return {
        "code": issue.code,
        "message": issue.message,
        "references": list(issue.references),
    }
