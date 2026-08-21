"""Deterministic KFlow v2 derivation and effective-version fingerprints."""

import hashlib
import json
from collections.abc import Mapping

from kflow.v2.graph import KnowledgeGraph
from kflow.v2.models import Derivation


def _sha256_canonical(value) -> str:
    encoded = json.dumps(
        value,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def fingerprint_derivation(derivation: Derivation) -> str:
    """Fingerprint all topology and semantic facts in one derivation."""
    canonical = {
        "kind": "derivation",
        "schema_version": 2,
        "id": derivation.id,
        "short": derivation.short,
        "detail": derivation.detail,
        "inputs": [
            {"node": item.node, "short": item.short, "detail": item.detail}
            for item in sorted(derivation.inputs, key=lambda value: value.node)
        ],
        "outputs": [
            {"node": item.node, "short": item.short, "detail": item.detail}
            for item in sorted(derivation.outputs, key=lambda value: value.node)
        ],
    }
    return _sha256_canonical(canonical)


def compute_effective_versions(
    graph: KnowledgeGraph,
    files_fingerprints: Mapping[str, str],
) -> dict[str, str]:
    """Compute every Node version once in stable topological order.

    ``files_fingerprints`` contains the already-aggregated current fingerprint
    for each Node's normalized file collection. Confirmations are deliberately
    absent: confirmation records observe effective versions but never alter them.
    """
    missing = sorted(set(graph.nodes) - set(files_fingerprints))
    if missing:
        raise ValueError(f"missing files fingerprint for nodes: {', '.join(missing)}")

    versions: dict[str, str] = {}
    for node_id in graph.topological_order():
        producer = graph.producer_of(node_id)
        inputs = [
            [item.node, versions[item.node]]
            for item in sorted(producer.inputs, key=lambda value: value.node)
        ]
        versions[node_id] = _sha256_canonical(
            [
                node_id,
                files_fingerprints[node_id],
                fingerprint_derivation(producer),
                inputs,
            ]
        )
    return versions
