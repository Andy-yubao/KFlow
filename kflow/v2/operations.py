"""Small application operations used by the KFlow v2 CLI."""

from __future__ import annotations

import uuid
from pathlib import Path

from kflow.v2.graph import KnowledgeGraph
from kflow.v2.models import (
    Derivation,
    DerivationInput,
    DerivationOutput,
    KnowledgeNode,
)
from kflow.v2.scan import resolve_node_id
from kflow.v2.storage import load_graph, save_derivation, save_node


def add_node(root: Path, name: str, files: tuple[str, ...]) -> KnowledgeNode:
    """Register existing project files as one source Node."""
    graph = load_graph(root)
    normalized = tuple(_normalize_existing_file(root, path) for path in files)
    node = KnowledgeNode(_new_id("nd", graph.nodes), name, normalized)
    KnowledgeGraph.build((*graph.nodes.values(), node), graph.derivations.values())
    save_node(root, node)
    return node


def add_derivation(
    root: Path,
    short: str,
    detail: str,
    inputs: tuple[tuple[str, str, str], ...],
    outputs: tuple[tuple[str, str, str], ...],
) -> Derivation:
    """Connect existing Nodes with one many-input, many-output Derivation."""
    graph = load_graph(root)
    derivation = Derivation(
        _new_id("dv", graph.derivations),
        short,
        detail,
        tuple(
            DerivationInput(resolve_node_id(graph, reference), role_short, role_detail)
            for reference, role_short, role_detail in inputs
        ),
        tuple(
            DerivationOutput(resolve_node_id(graph, reference), role_short, role_detail)
            for reference, role_short, role_detail in outputs
        ),
    )
    KnowledgeGraph.build(
        graph.nodes.values(), (*graph.derivations.values(), derivation)
    )
    save_derivation(root, derivation)
    return derivation


def _normalize_existing_file(root: Path, value: str) -> str:
    root = Path(root).resolve()
    relative = Path(value)
    if relative.is_absolute():
        raise ValueError(f"node file must be repository-relative: {value}")
    candidate = (root / relative).resolve()
    try:
        normalized = candidate.relative_to(root).as_posix()
    except ValueError:
        raise ValueError(f"node file escapes project root: {value}") from None
    if not candidate.is_file():
        raise ValueError(f"node file does not exist: {normalized}")
    return normalized


def _new_id(prefix: str, existing) -> str:
    while True:
        candidate = f"{prefix}_{uuid.uuid4().hex[:12]}"
        if candidate not in existing:
            return candidate
