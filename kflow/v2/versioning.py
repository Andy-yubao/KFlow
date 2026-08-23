"""Deterministic KFlow v2 fingerprints, versions, and confirmation baselines."""

import hashlib
import json
from collections.abc import Mapping

from kflow.v2.graph import KnowledgeGraph
from kflow.v2.models import (
    ConfirmationFile,
    ConfirmationInput,
    ConfirmationProducer,
    Derivation,
    Fingerprint,
    NodeConfirmation,
    _validate_repository_path,
)


def _sha256_canonical(value) -> str:
    encoded = json.dumps(
        value,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _fingerprint_value(value: Fingerprint) -> dict[str, str]:
    if not isinstance(value, Fingerprint):
        raise ValueError("fingerprint value must be a Fingerprint")
    return {"algorithm": value.algorithm, "value": value.value}


def fingerprint_file(content: bytes) -> Fingerprint:
    """Fingerprint a file's exact raw bytes."""
    if not isinstance(content, bytes):
        raise TypeError("file content must be bytes")
    return Fingerprint("sha256", hashlib.sha256(content).hexdigest())


def fingerprint_files(files: Mapping[str, Fingerprint]) -> Fingerprint:
    """Fingerprint a non-empty path-to-file-fingerprint collection."""
    if not files:
        raise ValueError("files fingerprint requires at least one file")
    for path in files:
        _validate_repository_path(path)
    canonical = [
        [path, _fingerprint_value(fingerprint)]
        for path, fingerprint in sorted(files.items())
    ]
    return Fingerprint("sha256", _sha256_canonical(canonical))


def fingerprint_derivation(derivation: Derivation) -> Fingerprint:
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
    return Fingerprint("sha256", _sha256_canonical(canonical))


def compute_effective_versions(
    graph: KnowledgeGraph,
    files_fingerprints: Mapping[str, Fingerprint],
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
        files_fingerprint = _fingerprint_value(files_fingerprints[node_id])
        if producer is None:
            versions[node_id] = _sha256_canonical([node_id, files_fingerprint])
            continue
        inputs = [
            [item.node, versions[item.node]]
            for item in sorted(producer.inputs, key=lambda value: value.node)
        ]
        versions[node_id] = _sha256_canonical(
            [
                node_id,
                files_fingerprint,
                _fingerprint_value(fingerprint_derivation(producer)),
                inputs,
            ]
        )
    return versions


def build_confirmation(
    graph: KnowledgeGraph,
    node_id: str,
    file_fingerprints: Mapping[str, Fingerprint],
    effective_versions: Mapping[str, str],
) -> NodeConfirmation:
    """Build one Node's immutable baseline without mutating any other Node."""
    try:
        node = graph.nodes[node_id]
    except KeyError:
        raise KeyError(f"unknown node: {node_id}") from None

    missing_files = sorted(set(node.files) - set(file_fingerprints))
    if missing_files:
        raise ValueError(
            f"missing file fingerprint for paths: {', '.join(missing_files)}"
        )
    required_versions = {node_id}
    producer = graph.producer_of(node_id)
    if producer is not None:
        required_versions.update(item.node for item in producer.inputs)
    missing_versions = sorted(required_versions - set(effective_versions))
    if missing_versions:
        raise ValueError(
            f"missing effective version for nodes: {', '.join(missing_versions)}"
        )

    confirmed_files = tuple(
        ConfirmationFile(path, file_fingerprints[path]) for path in sorted(node.files)
    )
    aggregate = fingerprint_files(
        {item.path: item.fingerprint for item in confirmed_files}
    )
    confirmed_producer = None
    confirmed_inputs: tuple[ConfirmationInput, ...] = ()
    if producer is not None:
        confirmed_producer = ConfirmationProducer(
            producer.id, fingerprint_derivation(producer)
        )
        confirmed_inputs = tuple(
            ConfirmationInput(item.node, effective_versions[item.node])
            for item in sorted(producer.inputs, key=lambda value: value.node)
        )

    return NodeConfirmation(
        node=node_id,
        files=confirmed_files,
        files_fingerprint=aggregate,
        producing_derivation=confirmed_producer,
        inputs=confirmed_inputs,
        effective_version=effective_versions[node_id],
    )
