"""Pure comparison of current KFlow facts with confirmation baselines."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from kflow.core.graph import KnowledgeGraph
from kflow.core.models import Fingerprint, NodeConfirmation
from kflow.core.versioning import fingerprint_derivation, fingerprint_files


@dataclass(frozen=True, slots=True)
class NodeStatus:
    """One Node's coarse status plus its canonical review reasons."""

    node: str
    status: str
    reasons: tuple[str, ...]
    changed_files: tuple[str, ...]
    effective_version: str

    @property
    def needs_review(self) -> bool:
        return bool(self.reasons)


def evaluate_statuses(
    graph: KnowledgeGraph,
    confirmations: Mapping[str, NodeConfirmation],
    file_fingerprints: Mapping[str, Fingerprint],
    effective_versions: Mapping[str, str],
) -> dict[str, NodeStatus]:
    """Compare every current Node fact with its optional baseline."""
    return {
        node_id: _evaluate_node(
            graph,
            node_id,
            confirmations.get(node_id),
            file_fingerprints,
            effective_versions,
        )
        for node_id in graph.topological_order()
    }


def _evaluate_node(
    graph: KnowledgeGraph,
    node_id: str,
    confirmation: NodeConfirmation | None,
    file_fingerprints: Mapping[str, Fingerprint],
    effective_versions: Mapping[str, str],
) -> NodeStatus:
    node = graph.nodes[node_id]
    if confirmation is None:
        return NodeStatus(
            node=node_id,
            status="valid",
            reasons=("unconfirmed",),
            changed_files=(),
            effective_version=effective_versions[node_id],
        )

    reasons: list[str] = []
    confirmed_files = {item.path: item.fingerprint for item in confirmation.files}
    current_files = {path: file_fingerprints[path] for path in node.files}
    changed_files = tuple(
        sorted(
            path
            for path in set(confirmed_files) | set(current_files)
            if confirmed_files.get(path) != current_files.get(path)
        )
    )
    if changed_files or confirmation.files_fingerprint != fingerprint_files(
        current_files
    ):
        reasons.append("files_changed")

    producer = graph.producer_of(node_id)
    confirmed_producer = confirmation.producing_derivation
    if producer is None:
        producer_changed = confirmed_producer is not None
    elif confirmed_producer is None:
        producer_changed = True
    else:
        producer_changed = (
            producer.id != confirmed_producer.id
            or fingerprint_derivation(producer) != confirmed_producer.fingerprint
        )
    if producer_changed:
        reasons.append("derivation_changed")

    current_inputs = (
        {}
        if producer is None
        else {item.node: effective_versions[item.node] for item in producer.inputs}
    )
    confirmed_inputs = {
        item.node: item.effective_version for item in confirmation.inputs
    }
    if (
        producer is not None
        and confirmed_producer is not None
        and current_inputs != confirmed_inputs
    ):
        reasons.append("input_changed")

    return NodeStatus(
        node=node_id,
        status="affected" if reasons else "confirmed",
        reasons=tuple(reasons),
        changed_files=changed_files,
        effective_version=effective_versions[node_id],
    )
