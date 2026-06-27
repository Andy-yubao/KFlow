"""Core data models for KFlow — Node, Derivation, and Index."""
from dataclasses import dataclass, field


@dataclass
class Node:
    """A knowledge node — usually corresponds to a Markdown file."""
    id: str
    name: str
    file: str | None
    status: str  # "green" | "yellow" | "red"
    derivations_as_input: list[str] = field(default_factory=list)
    derivations_as_output: list[str] = field(default_factory=list)


@dataclass
class InputSpec:
    """Describes one input to a Derivation."""
    node: str
    role: str
    role_detail: str


@dataclass
class OutputSpec:
    """Describes the output of a Derivation."""
    node: str
    method: str
    method_detail: str


@dataclass
class Derivation:
    """A derivation that produces one output node from one or more input nodes."""
    id: str
    summary: str
    inputs: list[InputSpec]
    output: OutputSpec


@dataclass
class IndexNode:
    """Compact node entry in index.json."""
    name: str
    file: str | None
    status: str
    derivations_as_input: list[str]
    derivations_as_output: list[str]


@dataclass
class IndexDerivation:
    """Compact derivation entry in index.json (no detail fields)."""
    summary: str
    inputs: list[dict]
    output: dict


@dataclass
class Index:
    """Aggregated index — cache rebuilt from individual files."""
    nodes: dict[str, IndexNode]
    derivations: dict[str, IndexDerivation]
