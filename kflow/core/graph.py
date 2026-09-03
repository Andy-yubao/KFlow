"""Validated graph projection for KFlow derivations."""

from __future__ import annotations

import heapq
from collections import defaultdict, deque
from dataclasses import dataclass
from types import MappingProxyType
from typing import Iterable, Mapping

from kflow.core.models import Derivation, KnowledgeNode


@dataclass(frozen=True, slots=True)
class ValidationIssue:
    """One deterministic domain validation failure."""

    code: str
    message: str
    references: tuple[str, ...] = ()


class GraphValidationError(ValueError):
    """Raised when nodes and derivations do not form a valid KFlow graph."""

    def __init__(self, issues: Iterable[ValidationIssue]):
        self.issues = tuple(issues)
        summary = "; ".join(issue.message for issue in self.issues)
        super().__init__(summary)


class KnowledgeGraph:
    """An immutable, validated projection of Node and Derivation facts."""

    def __init__(
        self,
        nodes: dict[str, KnowledgeNode],
        derivations: dict[str, Derivation],
        producers: dict[str, str],
        consumers: dict[str, tuple[str, ...]],
        adjacency: dict[str, tuple[str, ...]],
        reverse_adjacency: dict[str, tuple[str, ...]],
        topological_order: tuple[str, ...],
    ) -> None:
        self._nodes = MappingProxyType(nodes)
        self._derivations = MappingProxyType(derivations)
        self._producers = MappingProxyType(producers)
        self._consumers = MappingProxyType(consumers)
        self._adjacency = MappingProxyType(adjacency)
        self._reverse_adjacency = MappingProxyType(reverse_adjacency)
        self._topological_order = topological_order

    @classmethod
    def build(
        cls,
        nodes: Iterable[KnowledgeNode],
        derivations: Iterable[Derivation],
    ) -> KnowledgeGraph:
        node_list = tuple(nodes)
        derivation_list = tuple(derivations)
        issues: list[ValidationIssue] = []

        node_map = _unique_by_id(node_list, "node", issues)
        derivation_map = _unique_by_id(derivation_list, "derivation", issues)

        _validate_unique_node_names(node_list, issues)
        _validate_unique_derivation_names(derivation_list, issues)
        _validate_unique_file_owners(node_list, issues)
        _validate_references(node_map, derivation_list, issues)

        producers = _collect_producers(node_map, derivation_list, issues)
        consumers = _collect_consumers(node_map, derivation_list)
        adjacency, reverse_adjacency = _project_adjacency(node_map, derivation_list)
        topological_order = _stable_topological_order(adjacency)
        if len(topological_order) != len(node_map):
            issues.append(
                ValidationIssue(
                    "cycle",
                    "derivation projection contains a cycle",
                    tuple(sorted(node_map)),
                )
            )

        if issues:
            raise GraphValidationError(issues)

        return cls(
            nodes=dict(node_map),
            derivations=dict(derivation_map),
            producers=producers,
            consumers=consumers,
            adjacency=adjacency,
            reverse_adjacency=reverse_adjacency,
            topological_order=topological_order,
        )

    @property
    def nodes(self) -> Mapping[str, KnowledgeNode]:
        return self._nodes

    @property
    def derivations(self) -> Mapping[str, Derivation]:
        return self._derivations

    def producer_of(self, node_id: str) -> Derivation | None:
        """Return the producing Derivation, or ``None`` for a source Node."""
        self._require_node(node_id)
        producer_id = self._producers.get(node_id)
        return self._derivations[producer_id] if producer_id is not None else None

    def consumer_derivations(self, node_id: str) -> tuple[Derivation, ...]:
        self._require_node(node_id)
        return tuple(self._derivations[item] for item in self._consumers[node_id])

    def topological_order(self) -> tuple[str, ...]:
        return self._topological_order

    def sibling_outputs(self, node_id: str) -> tuple[str, ...]:
        producer = self.producer_of(node_id)
        if producer is None:
            return ()
        return tuple(
            sorted(item.node for item in producer.outputs if item.node != node_id)
        )

    def downstream(self, node_id: str, max_depth: int | None = None) -> dict[str, int]:
        self._require_node(node_id)
        return _breadth_first_depths(self._adjacency, node_id, max_depth)

    def upstream(self, node_id: str, max_depth: int | None = None) -> tuple[str, ...]:
        self._require_node(node_id)
        depths = _breadth_first_depths(self._reverse_adjacency, node_id, max_depth)
        included = set(depths)
        return tuple(item for item in self._topological_order if item in included)

    def _require_node(self, node_id: str) -> None:
        if node_id not in self._nodes:
            raise KeyError(f"unknown node: {node_id}")


def _unique_by_id(items, kind: str, issues: list[ValidationIssue]):
    result = {}
    counts: dict[str, int] = defaultdict(int)
    for item in items:
        counts[item.id] += 1
        result.setdefault(item.id, item)
    for item_id in sorted(key for key, count in counts.items() if count > 1):
        issues.append(
            ValidationIssue(
                f"duplicate_{kind}_id",
                f"{kind} id appears more than once: {item_id}",
                (item_id,),
            )
        )
    return result


def _validate_unique_node_names(
    nodes: tuple[KnowledgeNode, ...], issues: list[ValidationIssue]
) -> None:
    owners: dict[str, list[str]] = defaultdict(list)
    for node in nodes:
        owners[node.name].append(node.id)
    for name, node_ids in sorted(owners.items()):
        if len(node_ids) > 1:
            issues.append(
                ValidationIssue(
                    "duplicate_node_name",
                    f"node name has multiple owners: {name}",
                    tuple(sorted(node_ids)),
                )
            )


def _validate_unique_derivation_names(
    derivations: tuple[Derivation, ...], issues: list[ValidationIssue]
) -> None:
    owners: dict[str, list[str]] = defaultdict(list)
    for derivation in derivations:
        owners[derivation.name].append(derivation.id)
    for name, derivation_ids in sorted(owners.items()):
        if len(derivation_ids) > 1:
            issues.append(
                ValidationIssue(
                    "duplicate_derivation_name",
                    f"derivation name has multiple owners: {name}",
                    tuple(sorted(derivation_ids)),
                )
            )


def _validate_unique_file_owners(
    nodes: tuple[KnowledgeNode, ...], issues: list[ValidationIssue]
) -> None:
    owners: dict[str, list[str]] = defaultdict(list)
    for node in nodes:
        for path in node.files:
            owners[path].append(node.id)
    for path, node_ids in sorted(owners.items()):
        if len(node_ids) > 1:
            issues.append(
                ValidationIssue(
                    "duplicate_file_owner",
                    f"file path has multiple node owners: {path}",
                    tuple(sorted(node_ids)),
                )
            )


def _validate_references(
    nodes: Mapping[str, KnowledgeNode],
    derivations: tuple[Derivation, ...],
    issues: list[ValidationIssue],
) -> None:
    for derivation in sorted(derivations, key=lambda item: item.id):
        for item in derivation.inputs:
            if item.node not in nodes:
                issues.append(
                    ValidationIssue(
                        "missing_input_node",
                        f"derivation {derivation.id} references missing input {item.node}",
                        (derivation.id, item.node),
                    )
                )
        for item in derivation.outputs:
            if item.node not in nodes:
                issues.append(
                    ValidationIssue(
                        "missing_output_node",
                        f"derivation {derivation.id} references missing output {item.node}",
                        (derivation.id, item.node),
                    )
                )


def _collect_producers(
    nodes: Mapping[str, KnowledgeNode],
    derivations: tuple[Derivation, ...],
    issues: list[ValidationIssue],
) -> dict[str, str]:
    producers: dict[str, list[str]] = {node_id: [] for node_id in nodes}
    for derivation in derivations:
        for output in derivation.outputs:
            if output.node in producers:
                producers[output.node].append(derivation.id)

    result = {}
    for node_id, derivation_ids in sorted(producers.items()):
        if len(derivation_ids) > 1:
            issues.append(
                ValidationIssue(
                    "multiple_producers",
                    f"node has multiple producing derivations: {node_id}",
                    (node_id, *sorted(derivation_ids)),
                )
            )
        elif derivation_ids:
            result[node_id] = derivation_ids[0]
    return result


def _collect_consumers(
    nodes: Mapping[str, KnowledgeNode], derivations: tuple[Derivation, ...]
) -> dict[str, tuple[str, ...]]:
    consumers: dict[str, list[str]] = {node_id: [] for node_id in nodes}
    for derivation in derivations:
        for item in derivation.inputs:
            if item.node in consumers:
                consumers[item.node].append(derivation.id)
    return {node_id: tuple(sorted(values)) for node_id, values in consumers.items()}


def _project_adjacency(
    nodes: Mapping[str, KnowledgeNode], derivations: tuple[Derivation, ...]
) -> tuple[dict[str, tuple[str, ...]], dict[str, tuple[str, ...]]]:
    adjacency: dict[str, set[str]] = {node_id: set() for node_id in nodes}
    reverse: dict[str, set[str]] = {node_id: set() for node_id in nodes}
    for derivation in derivations:
        for input_item in derivation.inputs:
            if input_item.node not in nodes:
                continue
            for output_item in derivation.outputs:
                if output_item.node not in nodes:
                    continue
                adjacency[input_item.node].add(output_item.node)
                reverse[output_item.node].add(input_item.node)
    return (
        {node_id: tuple(sorted(values)) for node_id, values in adjacency.items()},
        {node_id: tuple(sorted(values)) for node_id, values in reverse.items()},
    )


def _stable_topological_order(
    adjacency: Mapping[str, tuple[str, ...]],
) -> tuple[str, ...]:
    in_degree = {node_id: 0 for node_id in adjacency}
    for neighbors in adjacency.values():
        for neighbor in neighbors:
            in_degree[neighbor] += 1

    ready = [node_id for node_id, degree in in_degree.items() if degree == 0]
    heapq.heapify(ready)
    result = []
    while ready:
        node_id = heapq.heappop(ready)
        result.append(node_id)
        for neighbor in adjacency[node_id]:
            in_degree[neighbor] -= 1
            if in_degree[neighbor] == 0:
                heapq.heappush(ready, neighbor)
    return tuple(result)


def _breadth_first_depths(
    adjacency: Mapping[str, tuple[str, ...]],
    start: str,
    max_depth: int | None,
) -> dict[str, int]:
    depths = {start: 0}
    queue = deque([start])
    while queue:
        node_id = queue.popleft()
        depth = depths[node_id]
        if max_depth is not None and depth >= max_depth:
            continue
        for neighbor in adjacency[node_id]:
            if neighbor not in depths:
                depths[neighbor] = depth + 1
                queue.append(neighbor)
    return depths
