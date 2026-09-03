"""Small application operations used by the KFlow CLI."""

from __future__ import annotations

import uuid
from pathlib import Path

from kflow.core.graph import KnowledgeGraph
from kflow.core.models import (
    Derivation,
    DerivationInput,
    DerivationOutput,
    KnowledgeNode,
)
from kflow.core.scan import resolve_node_id
from kflow.core.storage import (
    delete_derivation,
    delete_node_and_confirmation,
    load_graph,
    save_derivation,
    save_node,
)


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
    name: str,
    short: str,
    detail: str,
    inputs: tuple[tuple[str, str, str], ...],
    outputs: tuple[tuple[str, str, str], ...],
) -> Derivation:
    """Connect existing Nodes with one many-input, many-output Derivation."""
    graph = load_graph(root)
    derivation = Derivation(
        _new_id("dv", graph.derivations),
        name,
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


def edit_node(
    root: Path, old_name: str, *, name: str, files: tuple[str, ...]
) -> KnowledgeNode:
    """Replace one Node definition by exact old name while preserving its ID."""
    graph = load_graph(root)
    current = _node_by_name(graph, old_name)
    normalized = tuple(_normalize_existing_file(root, path) for path in files)
    replacement = KnowledgeNode(current.id, name, normalized)
    candidate_nodes = tuple(
        replacement if node.id == current.id else node for node in graph.nodes.values()
    )
    KnowledgeGraph.build(candidate_nodes, graph.derivations.values())
    save_node(root, replacement)
    return replacement


def edit_derivation(
    root: Path,
    old_name: str,
    *,
    name: str,
    short: str,
    detail: str,
    inputs: tuple[tuple[str, str, str], ...],
    outputs: tuple[tuple[str, str, str], ...],
) -> Derivation:
    """Replace one Derivation definition by exact old name, preserving its ID."""
    graph = load_graph(root)
    current = _derivation_by_name(graph, old_name)
    replacement = Derivation(
        current.id,
        name,
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
    candidate_derivations = tuple(
        replacement if item.id == current.id else item
        for item in graph.derivations.values()
    )
    KnowledgeGraph.build(graph.nodes.values(), candidate_derivations)
    save_derivation(root, replacement)
    return replacement


def remove_derivation(root: Path, name: str) -> Derivation:
    """Remove exactly one Derivation selected by its unique name."""
    graph = load_graph(root)
    current = _derivation_by_name(graph, name)
    candidate_derivations = tuple(
        item for item in graph.derivations.values() if item.id != current.id
    )
    KnowledgeGraph.build(graph.nodes.values(), candidate_derivations)
    delete_derivation(root, current.id)
    return current


def remove_node(root: Path, name: str) -> KnowledgeNode:
    """Remove an unreferenced Node and its optional Confirmation without cascade."""
    graph = load_graph(root)
    current = _node_by_name(graph, name)
    blockers = sorted(
        {
            derivation.name
            for derivation in graph.derivations.values()
            if any(role.node == current.id for role in derivation.inputs)
            or any(role.node == current.id for role in derivation.outputs)
        }
    )
    if blockers:
        listed = "\n".join(f"- {item}" for item in blockers)
        raise ValueError(
            f"Cannot remove Node {name}.\n\nReferenced by:\n{listed}\n\n"
            "Edit or remove those Derivations first."
        )
    candidate_nodes = tuple(
        node for node in graph.nodes.values() if node.id != current.id
    )
    KnowledgeGraph.build(candidate_nodes, graph.derivations.values())
    delete_node_and_confirmation(root, current.id)
    return current


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


def _node_by_name(graph: KnowledgeGraph, name: str) -> KnowledgeNode:
    matches = [node for node in graph.nodes.values() if node.name == name]
    if not matches:
        raise ValueError(f"unknown Node name: {name}")
    return matches[0]


def _derivation_by_name(graph: KnowledgeGraph, name: str) -> Derivation:
    matches = [item for item in graph.derivations.values() if item.name == name]
    if not matches:
        raise ValueError(f"unknown Derivation name: {name}")
    return matches[0]


def _new_id(prefix: str, existing) -> str:
    while True:
        candidate = f"{prefix}_{uuid.uuid4().hex[:12]}"
        if candidate not in existing:
            return candidate
