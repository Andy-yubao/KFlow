"""Deterministic, Git-native persistence for KFlow facts."""

from __future__ import annotations

import json
import os
import uuid
from pathlib import Path

from kflow.core.graph import KnowledgeGraph
from kflow.core.models import (
    ConfirmationFile,
    ConfirmationInput,
    ConfirmationProducer,
    Derivation,
    DerivationInput,
    DerivationOutput,
    Fingerprint,
    KnowledgeNode,
    NodeConfirmation,
)


KFLOW_DIR = ".kflow"
SCHEMA_VERSION = 2


class StorageError(ValueError):
    """Raised when persisted KFlow metadata is missing or malformed."""


def initialize_project(root: Path) -> None:
    """Create an empty KFlow metadata tree without touching user files."""
    root = Path(root)
    metadata = root / KFLOW_DIR
    if metadata.exists():
        raise StorageError(f"KFlow metadata already exists: {metadata}")

    metadata.mkdir(parents=False)
    for name in ("nodes", "derivations", "confirmations", "runtime"):
        (metadata / name).mkdir()
    _write_json(
        metadata / "project.json",
        {"kind": "kflow-project", "schema_version": SCHEMA_VERSION},
    )
    (metadata / ".gitignore").write_text("/runtime/\n", encoding="utf-8", newline="\n")


def save_graph(root: Path, graph: KnowledgeGraph) -> None:
    """Persist every Node and Derivation in an already initialized project."""
    _require_project(root)
    for node in sorted(graph.nodes.values(), key=lambda item: item.id):
        save_node(root, node)
    for derivation in sorted(graph.derivations.values(), key=lambda item: item.id):
        save_derivation(root, derivation)


def save_node(root: Path, node: KnowledgeNode) -> None:
    _require_project(root)
    _write_json(
        Path(root) / KFLOW_DIR / "nodes" / f"{node.id}.json", _encode_node(node)
    )


def save_derivation(root: Path, derivation: Derivation) -> None:
    _require_project(root)
    _write_json(
        Path(root) / KFLOW_DIR / "derivations" / f"{derivation.id}.json",
        _encode_derivation(derivation),
    )


def save_confirmation(root: Path, confirmation: NodeConfirmation) -> None:
    """Atomically replace exactly one Node confirmation baseline."""
    _require_project(root)
    _write_json(
        Path(root) / KFLOW_DIR / "confirmations" / f"{confirmation.node}.json",
        _encode_confirmation(confirmation),
    )


def load_graph(root: Path) -> KnowledgeGraph:
    """Load canonical facts and rebuild all graph indexes."""
    metadata = _require_project(root)
    nodes = tuple(
        _decode_node(_read_json(path), expected_id=path.stem)
        for path in sorted((metadata / "nodes").glob("*.json"))
    )
    derivations = tuple(
        _decode_derivation(_read_json(path), expected_id=path.stem)
        for path in sorted((metadata / "derivations").glob("*.json"))
    )
    return KnowledgeGraph.build(nodes, derivations)


def load_confirmations(root: Path) -> dict[str, NodeConfirmation]:
    metadata = _require_project(root)
    confirmations: dict[str, NodeConfirmation] = {}
    for path in sorted((metadata / "confirmations").glob("*.json")):
        confirmation = _decode_confirmation(_read_json(path), expected_node=path.stem)
        if confirmation.node in confirmations:
            raise StorageError(f"duplicate confirmation: {confirmation.node}")
        confirmations[confirmation.node] = confirmation
    return confirmations


def _require_project(root: Path) -> Path:
    metadata = Path(root) / KFLOW_DIR
    manifest_path = metadata / "project.json"
    if not manifest_path.is_file():
        raise StorageError(f"KFlow project is not initialized: {Path(root)}")
    manifest = _read_json(manifest_path)
    _expect_header(manifest, "kflow-project")
    return metadata


def _write_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    try:
        with temporary.open("w", encoding="utf-8", newline="\n") as stream:
            json.dump(
                value,
                stream,
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
            )
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()


def _read_json(path: Path) -> dict:
    try:
        with path.open(encoding="utf-8") as stream:
            value = json.load(stream)
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise StorageError(f"cannot read KFlow metadata {path}: {error}") from error
    if not isinstance(value, dict):
        raise StorageError(f"KFlow metadata must be a JSON object: {path}")
    return value


def _expect_header(value: dict, kind: str) -> None:
    if value.get("kind") != kind:
        raise StorageError(f"expected kind {kind!r}, got {value.get('kind')!r}")
    if value.get("schema_version") != SCHEMA_VERSION:
        raise StorageError(
            f"unsupported schema version: {value.get('schema_version')!r}"
        )


def _encode_node(node: KnowledgeNode) -> dict:
    return {
        "kind": "node",
        "schema_version": SCHEMA_VERSION,
        "id": node.id,
        "name": node.name,
        "files": sorted(node.files),
    }


def _decode_node(value: dict, expected_id: str) -> KnowledgeNode:
    _expect_header(value, "node")
    node = KnowledgeNode(value["id"], value["name"], tuple(value["files"]))
    if node.id != expected_id:
        raise StorageError(
            f"node id {node.id!r} does not match metadata filename {expected_id!r}"
        )
    return node


def _encode_derivation(derivation: Derivation) -> dict:
    return {
        "kind": "derivation",
        "schema_version": SCHEMA_VERSION,
        "id": derivation.id,
        "short": derivation.short,
        "detail": derivation.detail,
        "inputs": [
            {"node": item.node, "short": item.short, "detail": item.detail}
            for item in sorted(derivation.inputs, key=lambda item: item.node)
        ],
        "outputs": [
            {"node": item.node, "short": item.short, "detail": item.detail}
            for item in sorted(derivation.outputs, key=lambda item: item.node)
        ],
    }


def _decode_derivation(value: dict, expected_id: str) -> Derivation:
    _expect_header(value, "derivation")
    derivation = Derivation(
        value["id"],
        value["short"],
        value["detail"],
        tuple(
            DerivationInput(item["node"], item["short"], item["detail"])
            for item in value["inputs"]
        ),
        tuple(
            DerivationOutput(item["node"], item["short"], item["detail"])
            for item in value["outputs"]
        ),
    )
    if derivation.id != expected_id:
        raise StorageError(
            "derivation id "
            f"{derivation.id!r} does not match metadata filename {expected_id!r}"
        )
    return derivation


def _encode_fingerprint(value: Fingerprint) -> dict[str, str]:
    return {"algorithm": value.algorithm, "value": value.value}


def _decode_fingerprint(value: dict) -> Fingerprint:
    return Fingerprint(value["algorithm"], value["value"])


def _encode_confirmation(confirmation: NodeConfirmation) -> dict:
    producer = confirmation.producing_derivation
    return {
        "kind": "confirmation",
        "schema_version": SCHEMA_VERSION,
        "node": confirmation.node,
        "files": [
            {"path": item.path, "fingerprint": _encode_fingerprint(item.fingerprint)}
            for item in sorted(confirmation.files, key=lambda item: item.path)
        ],
        "files_fingerprint": _encode_fingerprint(confirmation.files_fingerprint),
        "producing_derivation": (
            None
            if producer is None
            else {
                "id": producer.id,
                "fingerprint": _encode_fingerprint(producer.fingerprint),
            }
        ),
        "inputs": [
            {"node": item.node, "effective_version": item.effective_version}
            for item in sorted(confirmation.inputs, key=lambda item: item.node)
        ],
        "effective_version": confirmation.effective_version,
    }


def _decode_confirmation(value: dict, expected_node: str) -> NodeConfirmation:
    _expect_header(value, "confirmation")
    producer_value = value["producing_derivation"]
    producer = None
    if producer_value is not None:
        producer = ConfirmationProducer(
            producer_value["id"], _decode_fingerprint(producer_value["fingerprint"])
        )
    confirmation = NodeConfirmation(
        node=value["node"],
        files=tuple(
            ConfirmationFile(item["path"], _decode_fingerprint(item["fingerprint"]))
            for item in value["files"]
        ),
        files_fingerprint=_decode_fingerprint(value["files_fingerprint"]),
        producing_derivation=producer,
        inputs=tuple(
            ConfirmationInput(item["node"], item["effective_version"])
            for item in value["inputs"]
        ),
        effective_version=value["effective_version"],
    )
    if confirmation.node != expected_node:
        raise StorageError(
            "confirmation node "
            f"{confirmation.node!r} does not match metadata filename {expected_node!r}"
        )
    return confirmation
