"""Immutable KFlow v2 domain values."""

import re
from dataclasses import dataclass
from pathlib import PurePosixPath


_WINDOWS_DRIVE = re.compile(r"^[A-Za-z]:")


def _require_text(value: str, field_name: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} must be non-empty text")


def _validate_repository_path(value: str) -> None:
    _require_text(value, "file path")
    if "\\" in value:
        raise ValueError(f"file path must use '/': {value!r}")
    if value.startswith("/") or _WINDOWS_DRIVE.match(value):
        raise ValueError(f"file path must be repository-relative: {value!r}")

    path = PurePosixPath(value)
    if path.is_absolute() or value != path.as_posix():
        raise ValueError(f"file path is not normalized: {value!r}")
    if value == "." or any(part in {"", ".", ".."} for part in path.parts):
        raise ValueError(f"file path escapes or does not identify a file: {value!r}")


@dataclass(frozen=True, slots=True)
class KnowledgeNode:
    """A stable knowledge identity backed by one or more repository files."""

    id: str
    name: str
    files: tuple[str, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "files", tuple(self.files))
        _require_text(self.id, "node id")
        _require_text(self.name, "node name")
        if not self.files:
            raise ValueError("node files must contain at least one path")
        if len(set(self.files)) != len(self.files):
            raise ValueError("node files must not contain duplicate paths")
        for path in self.files:
            _validate_repository_path(path)


@dataclass(frozen=True, slots=True)
class DerivationInput:
    """One input and its role in a derivation."""

    node: str
    short: str
    detail: str

    def __post_init__(self) -> None:
        _require_text(self.node, "input node id")
        _require_text(self.short, "input short")
        _require_text(self.detail, "input detail")


@dataclass(frozen=True, slots=True)
class DerivationOutput:
    """One output and its meaning in a derivation."""

    node: str
    short: str
    detail: str

    def __post_init__(self) -> None:
        _require_text(self.node, "output node id")
        _require_text(self.short, "output short")
        _require_text(self.detail, "output detail")


@dataclass(frozen=True, slots=True)
class Derivation:
    """A complete zero-or-more-input to one-or-more-output derivation."""

    id: str
    short: str
    detail: str
    inputs: tuple[DerivationInput, ...]
    outputs: tuple[DerivationOutput, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "inputs", tuple(self.inputs))
        object.__setattr__(self, "outputs", tuple(self.outputs))
        _require_text(self.id, "derivation id")
        _require_text(self.short, "derivation short")
        _require_text(self.detail, "derivation detail")
        if not self.outputs:
            raise ValueError("derivation outputs must contain at least one node")

        input_ids = tuple(item.node for item in self.inputs)
        output_ids = tuple(item.node for item in self.outputs)
        if len(set(input_ids)) != len(input_ids):
            raise ValueError("derivation inputs must not contain duplicate nodes")
        if len(set(output_ids)) != len(output_ids):
            raise ValueError("derivation outputs must not contain duplicate nodes")
        overlap = set(input_ids) & set(output_ids)
        if overlap:
            joined = ", ".join(sorted(overlap))
            raise ValueError(f"derivation inputs and outputs overlap: {joined}")
