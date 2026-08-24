"""Read-only project scan and single-Node confirmation for KFlow v2."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from kflow.v2.graph import GraphValidationError, KnowledgeGraph
from kflow.v2.models import Fingerprint, NodeConfirmation
from kflow.v2.status import NodeStatus, evaluate_statuses
from kflow.v2.storage import (
    StorageError,
    load_confirmations,
    load_graph,
    save_confirmation,
)
from kflow.v2.versioning import (
    build_confirmation,
    compute_effective_versions,
    fingerprint_file,
    fingerprint_files,
)


@dataclass(frozen=True, slots=True)
class ScanIssue:
    code: str
    message: str
    references: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class ScanResult:
    graph: KnowledgeGraph
    confirmations: dict[str, NodeConfirmation]
    statuses: dict[str, NodeStatus]
    file_fingerprints: dict[str, Fingerprint]
    effective_versions: dict[str, str]
    issues: tuple[ScanIssue, ...]


def scan(root: Path) -> ScanResult:
    """Load and validate metadata, then fingerprint files without returning content."""
    root = Path(root)
    graph = load_graph(root)
    confirmations = load_confirmations(root)
    issues: list[ScanIssue] = []

    for node_id in sorted(set(confirmations) - set(graph.nodes)):
        issues.append(
            ScanIssue(
                "missing_confirmation_node",
                f"confirmation references missing node: {node_id}",
                (node_id,),
            )
        )

    file_fingerprints: dict[str, Fingerprint] = {}
    aggregate_fingerprints: dict[str, Fingerprint] = {}
    for node_id in graph.topological_order():
        node = graph.nodes[node_id]
        node_files: dict[str, Fingerprint] = {}
        for relative_path in node.files:
            path = root / Path(relative_path)
            if not path.is_file():
                issues.append(
                    ScanIssue(
                        "missing_file",
                        f"node file is missing: {relative_path}",
                        (node_id, relative_path),
                    )
                )
                continue
            try:
                fingerprint = fingerprint_file(path.read_bytes())
            except OSError as error:
                issues.append(
                    ScanIssue(
                        "unreadable_file",
                        f"node file cannot be read: {relative_path}: {error}",
                        (node_id, relative_path),
                    )
                )
                continue
            file_fingerprints[relative_path] = fingerprint
            node_files[relative_path] = fingerprint
        if len(node_files) == len(node.files):
            aggregate_fingerprints[node_id] = fingerprint_files(node_files)

    if issues:
        return ScanResult(
            graph,
            confirmations,
            {},
            file_fingerprints,
            {},
            tuple(issues),
        )

    effective_versions = compute_effective_versions(graph, aggregate_fingerprints)
    statuses = evaluate_statuses(
        graph,
        confirmations,
        file_fingerprints,
        effective_versions,
    )
    return ScanResult(
        graph,
        confirmations,
        statuses,
        file_fingerprints,
        effective_versions,
        (),
    )


def validate(root: Path) -> tuple[ScanIssue, ...]:
    """Return metadata, graph, confirmation, and file issues without raising."""
    try:
        return scan(root).issues
    except GraphValidationError as error:
        return tuple(
            ScanIssue(issue.code, issue.message, issue.references)
            for issue in error.issues
        )
    except (KeyError, TypeError, ValueError, StorageError) as error:
        return (ScanIssue("invalid_metadata", str(error)),)


def confirm(root: Path, node_reference: str) -> tuple[NodeStatus, NodeStatus]:
    """Write the current baseline for one Node and return before/after status."""
    before_scan = scan(root)
    if before_scan.issues:
        raise ValueError("cannot confirm while validation issues exist")
    node_id = resolve_node_id(before_scan.graph, node_reference)
    before = before_scan.statuses[node_id]
    confirmation = build_confirmation(
        before_scan.graph,
        node_id,
        before_scan.file_fingerprints,
        before_scan.effective_versions,
    )
    save_confirmation(root, confirmation)
    after = scan(root).statuses[node_id]
    return before, after


def resolve_node_id(graph: KnowledgeGraph, reference: str) -> str:
    if reference in graph.nodes:
        return reference
    matches = [node.id for node in graph.nodes.values() if node.name == reference]
    if not matches:
        raise KeyError(f"unknown node: {reference}")
    return matches[0]
