"""Immutable KFlow v2 domain values."""

import re
from dataclasses import dataclass
from pathlib import PurePosixPath


_WINDOWS_DRIVE = re.compile(r"^[A-Za-z]:")
_SHA256_VALUE = re.compile(r"^[0-9a-f]{64}$")


def _require_text(value: str, field_name: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} must be non-empty text")


def _require_optional_text(value: str, field_name: str) -> None:
    if not isinstance(value, str):
        raise ValueError(f"{field_name} must be text")


def _require_sha256_value(value: str, field_name: str) -> None:
    if not isinstance(value, str) or not _SHA256_VALUE.fullmatch(value):
        raise ValueError(f"{field_name} must be a lowercase SHA-256 value")


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
        _require_optional_text(self.detail, "input detail")


@dataclass(frozen=True, slots=True)
class DerivationOutput:
    """One output and its meaning in a derivation."""

    node: str
    short: str
    detail: str

    def __post_init__(self) -> None:
        _require_text(self.node, "output node id")
        _require_text(self.short, "output short")
        _require_optional_text(self.detail, "output detail")


@dataclass(frozen=True, slots=True)
class Derivation:
    """One complete many-input, many-output derivation activity."""

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
        _require_optional_text(self.detail, "derivation detail")
        if not self.inputs:
            raise ValueError("derivation inputs must contain at least one node")
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


@dataclass(frozen=True, slots=True)
class Fingerprint:
    """An algorithm-labelled content fingerprint."""

    algorithm: str
    value: str

    def __post_init__(self) -> None:
        if self.algorithm != "sha256":
            raise ValueError("fingerprint algorithm must be 'sha256'")
        _require_sha256_value(self.value, "fingerprint value")


@dataclass(frozen=True, slots=True)
class ConfirmationFile:
    """One file fact recorded in a Node confirmation baseline."""

    path: str
    fingerprint: Fingerprint

    def __post_init__(self) -> None:
        _validate_repository_path(self.path)
        if not isinstance(self.fingerprint, Fingerprint):
            raise ValueError("confirmation file fingerprint must be a Fingerprint")


@dataclass(frozen=True, slots=True)
class ConfirmationProducer:
    """The producing Derivation recorded in a confirmation baseline."""

    id: str
    fingerprint: Fingerprint

    def __post_init__(self) -> None:
        _require_text(self.id, "confirmation producer id")
        if not isinstance(self.fingerprint, Fingerprint):
            raise ValueError("confirmation producer fingerprint must be a Fingerprint")


@dataclass(frozen=True, slots=True)
class ConfirmationInput:
    """One direct input version recorded in a confirmation baseline."""

    node: str
    effective_version: str

    def __post_init__(self) -> None:
        _require_text(self.node, "confirmation input node id")
        _require_sha256_value(
            self.effective_version, "confirmation input effective version"
        )


@dataclass(frozen=True, slots=True)
class NodeConfirmation:
    """The last reviewed fact baseline for exactly one Knowledge Node."""

    node: str
    files: tuple[ConfirmationFile, ...]
    files_fingerprint: Fingerprint
    producing_derivation: ConfirmationProducer | None
    inputs: tuple[ConfirmationInput, ...]
    effective_version: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "files", tuple(self.files))
        object.__setattr__(self, "inputs", tuple(self.inputs))
        _require_text(self.node, "confirmation node id")
        if not self.files:
            raise ValueError("confirmation files must contain at least one file")
        if any(not isinstance(item, ConfirmationFile) for item in self.files):
            raise ValueError("confirmation files must contain ConfirmationFile values")
        file_paths = tuple(item.path for item in self.files)
        if len(set(file_paths)) != len(file_paths):
            raise ValueError("confirmation files must not contain duplicate paths")
        if not isinstance(self.files_fingerprint, Fingerprint):
            raise ValueError("confirmation files fingerprint must be a Fingerprint")
        if self.producing_derivation is not None and not isinstance(
            self.producing_derivation, ConfirmationProducer
        ):
            raise ValueError(
                "confirmation producing derivation must be a ConfirmationProducer"
            )
        if any(not isinstance(item, ConfirmationInput) for item in self.inputs):
            raise ValueError(
                "confirmation inputs must contain ConfirmationInput values"
            )
        input_nodes = tuple(item.node for item in self.inputs)
        if len(set(input_nodes)) != len(input_nodes):
            raise ValueError("confirmation inputs must not contain duplicate nodes")
        if self.producing_derivation is None and self.inputs:
            raise ValueError("source confirmation must not contain inputs")
        if self.producing_derivation is not None and not self.inputs:
            raise ValueError("derived confirmation must contain at least one input")
        _require_sha256_value(self.effective_version, "confirmation effective version")
