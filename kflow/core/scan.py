"""Read-only project scan and single-Node confirmation for KFlow."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

from kflow.core.graph import GraphValidationError, KnowledgeGraph
from kflow.core.models import Fingerprint, NodeConfirmation
from kflow.core.status import NodeStatus, evaluate_statuses
from kflow.core.storage import (
    StorageError,
    load_confirmations,
    load_graph,
    save_confirmation,
)
from kflow.core.versioning import (
    build_confirmation,
    compute_effective_versions,
    fingerprint_file,
    fingerprint_files,
)


_WINDOWS_DRIVE = re.compile(r"^[A-Za-z]:")


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
    """Resolve an exact Node ID, name, or registered repository path."""
    if reference in graph.nodes:
        return reference
    matches = [node.id for node in graph.nodes.values() if node.name == reference]
    if matches:
        return matches[0]

    path_reference = _normalize_path_reference(reference)
    if path_reference is not None:
        for node in graph.nodes.values():
            if path_reference in node.files:
                return node.id

    raise KeyError(f"unknown node: {reference}")


def _normalize_path_reference(reference: str) -> str | None:
    """Accept limited path spelling variants without weakening stored-path rules."""
    candidate = reference.replace("\\", "/")
    if candidate.startswith("./"):
        candidate = candidate[2:]
    if candidate.startswith("/") or _WINDOWS_DRIVE.match(candidate):
        return None

    path = PurePosixPath(candidate)
    if (
        not candidate
        or path.is_absolute()
        or candidate != path.as_posix()
        or candidate == "."
        or any(part in {"", ".", ".."} for part in path.parts)
    ):
        return None
    return candidate


@dataclass(frozen=True, slots=True)
class DownstreamConfirmationResult:
    """Outcome of one explicit downstream batch confirmation."""

    root: str
    confirmed: tuple[str, ...]
    skipped_current: tuple[str, ...]
    remaining: tuple[str, ...]


class DownstreamConfirmationError(ValueError):
    """Raised when a downstream confirmation cannot start or stops early.

    Already-written baselines are retained; this operation is deliberately not
    an atomic transaction over the whole downstream scope.
    """

    def __init__(
        self,
        *,
        root: str | None,
        confirmed: tuple[str, ...],
        failed_node: str | None,
        issues: tuple[ScanIssue, ...],
    ) -> None:
        self.root = root
        self.confirmed = confirmed
        self.failed_node = failed_node
        self.issues = issues
        detail = (
            f"downstream confirmation stopped at {failed_node}"
            if failed_node is not None
            else "downstream confirmation could not start"
        )
        super().__init__(detail)


def confirm_downstream(root: Path, node_reference: str) -> DownstreamConfirmationResult:
    """Confirm the target and its reachable review debt in stable topological order.

    The caller explicitly asserts that every needs-review Node reachable from the
    target has been judged reviewable. KFlow performs no semantic inference: it
    only writes each current baseline, re-scanning project facts before every
    write so each decision reflects the latest state. Nodes that are already
    current are skipped and never rewritten.

    Any selector or project failure is reported as DownstreamConfirmationError, so
    callers never see a generic task-query error for a downstream invocation: an
    unknown reference raises ``unknown_node``, unreadable or invalid metadata
    raises ``invalid_project``, invalid graphs raise their graph issues, and
    pre-existing scan issues refuse the batch before any write. A blocking issue
    discovered by the final verification scan after writes is also a
    DownstreamConfirmationError that keeps ``confirmed`` and leaves
    ``failed_node`` as ``None``; earlier writes are retained.
    """
    root = Path(root)
    try:
        initial = scan(root)
    except GraphValidationError as error:
        issues = tuple(
            ScanIssue(issue.code, issue.message, issue.references)
            for issue in error.issues
        )
        raise DownstreamConfirmationError(
            root=None, confirmed=(), failed_node=None, issues=issues
        ) from error
    except StorageError as error:
        raise DownstreamConfirmationError(
            root=None,
            confirmed=(),
            failed_node=None,
            issues=(ScanIssue("invalid_project", str(error).strip("'")),),
        ) from error

    try:
        root_id = resolve_node_id(initial.graph, node_reference)
    except KeyError as error:
        raise DownstreamConfirmationError(
            root=None,
            confirmed=(),
            failed_node=None,
            issues=(
                ScanIssue("unknown_node", str(error).strip("'"), (node_reference,)),
            ),
        ) from error
    if initial.issues:
        raise DownstreamConfirmationError(
            root=root_id,
            confirmed=(),
            failed_node=None,
            issues=initial.issues,
        )

    scope = set(initial.graph.downstream(root_id))

    confirmed: list[str] = []
    skipped: list[str] = []
    for node_id in initial.graph.topological_order():
        if node_id not in scope:
            continue
        current = scan(root)
        if current.issues:
            raise DownstreamConfirmationError(
                root=root_id,
                confirmed=tuple(confirmed),
                failed_node=node_id,
                issues=current.issues,
            )
        status = current.statuses.get(node_id)
        if status is None or not status.needs_review:
            skipped.append(node_id)
            continue
        try:
            confirm(root, node_id)
        except Exception as error:
            name = current.graph.nodes[node_id].name
            raise DownstreamConfirmationError(
                root=root_id,
                confirmed=tuple(confirmed),
                failed_node=node_id,
                issues=(_confirmation_failure_issue(error, node_id, name),),
            ) from error
        confirmed.append(node_id)

    final = scan(root)
    if final.issues:
        # Post-write verification found blocking issues. Earlier writes stay; this
        # is a partial failure with no single failed Node to blame.
        raise DownstreamConfirmationError(
            root=root_id,
            confirmed=tuple(confirmed),
            failed_node=None,
            issues=final.issues,
        )
    remaining: list[str] = []
    for node_id in final.graph.topological_order():
        if node_id not in scope:
            continue
        final_status = final.statuses.get(node_id)
        if final_status is not None and final_status.needs_review:
            remaining.append(node_id)
    return DownstreamConfirmationResult(
        root=root_id,
        confirmed=tuple(confirmed),
        skipped_current=tuple(skipped),
        remaining=tuple(remaining),
    )


def _confirmation_failure_issue(error: Exception, node_id: str, name: str) -> ScanIssue:
    if isinstance(error, StorageError):
        code = "invalid_project"
    elif isinstance(error, OSError):
        code = "io_error"
    elif isinstance(error, KeyError):
        code = "unknown_node"
    else:
        code = "invalid_argument"
    detail = str(error).strip("'")
    return ScanIssue(code, f"cannot confirm node {name}: {detail}", (node_id,))
