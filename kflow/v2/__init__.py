"""KFlow v2 pure domain package.

The v2 namespace is intentionally isolated from the legacy CLI while its
contracts are implemented and reviewed incrementally.
"""

from kflow.v2.graph import GraphValidationError, KnowledgeGraph, ValidationIssue
from kflow.v2.models import (
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
from kflow.v2.versioning import (
    build_confirmation,
    compute_effective_versions,
    fingerprint_derivation,
    fingerprint_file,
    fingerprint_files,
)

__all__ = [
    "ConfirmationFile",
    "ConfirmationInput",
    "ConfirmationProducer",
    "Derivation",
    "DerivationInput",
    "DerivationOutput",
    "Fingerprint",
    "GraphValidationError",
    "KnowledgeGraph",
    "KnowledgeNode",
    "NodeConfirmation",
    "ValidationIssue",
    "build_confirmation",
    "compute_effective_versions",
    "fingerprint_derivation",
    "fingerprint_file",
    "fingerprint_files",
]
