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
from kflow.v2.scan import ScanIssue, ScanResult, confirm, scan, validate
from kflow.v2.status import NodeStatus, evaluate_statuses
from kflow.v2.storage import (
    SCHEMA_VERSION,
    StorageError,
    initialize_project,
    load_confirmations,
    load_graph,
    save_confirmation,
    save_derivation,
    save_graph,
    save_node,
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
    "NodeStatus",
    "SCHEMA_VERSION",
    "ScanIssue",
    "ScanResult",
    "StorageError",
    "ValidationIssue",
    "build_confirmation",
    "compute_effective_versions",
    "fingerprint_derivation",
    "fingerprint_file",
    "fingerprint_files",
    "confirm",
    "evaluate_statuses",
    "initialize_project",
    "load_confirmations",
    "load_graph",
    "save_confirmation",
    "save_derivation",
    "save_graph",
    "save_node",
    "scan",
    "validate",
]
