"""Create the external Human Interface Graph Diff demonstration project.

This one-time helper uses KFlow's domain models and storage API so that the
fixture is validated by the same invariants as a normal project. It creates two
committed structural baselines, then deliberately leaves structural changes
uncommitted for comparison by Graph Diff vs HEAD.
"""

from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path

from kflow.core.graph import KnowledgeGraph
from kflow.core.models import (
    Derivation,
    DerivationInput,
    DerivationOutput,
    KnowledgeNode,
)
from kflow.core.query import query_project_graph
from kflow.core.scan import confirm, validate
from kflow.core.storage import initialize_project, save_graph
from kflow.human.git_snapshot import (
    graph_diff_against_head,
    graph_diff_against_revision,
    query_git_history,
)


BASELINE_FILES = {
    "docs/requirements.md": """# Requirements

The local project view must expose the registered knowledge structure.
""",
    "docs/constraints.md": """# Constraints

The service must stay local, read-only, and dependency-free at runtime.
""",
    "docs/architecture.md": """# Architecture

The application separates domain queries, a local adapter, and a browser UI.
""",
    "docs/api-design.md": """# API Design

The local adapter exposes narrowly scoped JSON endpoints.
""",
    "docs/deployment-plan.md": """# Deployment Plan

The Python package distributes the production frontend assets.
""",
    "docs/testing-plan.md": """# Testing Plan

Automated and manual checks cover the graph, HTTP boundary, and packaged UI.
""",
    "docs/api-legacy-notes.md": """# API Legacy Notes

This historical output is present only in the committed demo baseline.
""",
    "docs/legacy-reference.md": """# Legacy Reference

This reference is present only in the committed demo baseline.
""",
    "notes/personal-note.md": """# Personal Note

This file intentionally remains outside the KFlow knowledge graph.
""",
}

CURRENT_FILES = {
    "docs/system-architecture.md": """# System Architecture

The current structure adds an explicit read-only Git comparison adapter.
""",
    "docs/architecture.svg": """<svg xmlns="http://www.w3.org/2000/svg" width="480" height="120" role="img" aria-label="KFlow architecture">
  <rect x="10" y="30" width="120" height="60" rx="8" fill="#eaf5ef" stroke="#275b43" />
  <rect x="180" y="30" width="120" height="60" rx="8" fill="#f3f7f4" stroke="#53635a" />
  <rect x="350" y="30" width="120" height="60" rx="8" fill="#eaf5ef" stroke="#275b43" />
  <path d="M130 60h50m120 0h50" stroke="#53635a" />
</svg>
""",
    "docs/operations-guide.md": """# Operations Guide

Launch the packaged local interface and stop it with Ctrl+C.
""",
    "docs/api-release-notes.md": """# API Release Notes

The current API exposes the project graph and Graph Diff vs HEAD.
""",
}


def node(node_id: str, name: str, *files: str) -> KnowledgeNode:
    return KnowledgeNode(node_id, name, files)


def input_role(node_id: str, short: str, detail: str = "") -> DerivationInput:
    return DerivationInput(node_id, short, detail)


def output_role(node_id: str, short: str, detail: str = "") -> DerivationOutput:
    return DerivationOutput(node_id, short, detail)


def baseline_graph() -> KnowledgeGraph:
    nodes = (
        node("nd_requirements", "requirements", "docs/requirements.md"),
        node("nd_constraints", "constraints", "docs/constraints.md"),
        node("nd_architecture", "architecture", "docs/architecture.md"),
        node("nd_api_design", "api-design", "docs/api-design.md"),
        node("nd_deployment_plan", "deployment-plan", "docs/deployment-plan.md"),
        node("nd_testing_plan", "testing-plan", "docs/testing-plan.md"),
        node(
            "nd_api_legacy_notes",
            "api-legacy-notes",
            "docs/api-legacy-notes.md",
        ),
        node(
            "nd_legacy_reference",
            "legacy-reference",
            "docs/legacy-reference.md",
        ),
    )
    derivations = (
        Derivation(
            "dv_architecture",
            "Requirements and constraints shape architecture",
            "Product goals and operating limits jointly determine the structure.",
            (
                input_role("nd_requirements", "Provides product goals"),
                input_role("nd_constraints", "Provides operating limits"),
            ),
            (output_role("nd_architecture", "Defines the system structure"),),
        ),
        Derivation(
            "dv_api_design",
            "Architecture defines API design",
            "System boundaries determine the local interface.",
            (
                input_role("nd_architecture", "Provides component boundaries"),
                input_role("nd_requirements", "Provides endpoint goals"),
            ),
            (
                output_role("nd_api_design", "Defines the local API"),
                output_role(
                    "nd_api_legacy_notes",
                    "Records compatibility notes",
                ),
            ),
        ),
        Derivation(
            "dv_delivery",
            "Architecture drives delivery plans",
            "The same architecture informs deployment and testing.",
            (input_role("nd_architecture", "Provides runtime boundaries"),),
            (
                output_role("nd_deployment_plan", "Defines packaging and launch"),
                output_role("nd_testing_plan", "Defines verification coverage"),
            ),
        ),
        Derivation(
            "dv_legacy_reference",
            "API design retains a legacy reference",
            "The baseline preserves one historical reference for removal.",
            (input_role("nd_api_design", "Provides historical endpoints"),),
            (output_role("nd_legacy_reference", "Records legacy behavior"),),
        ),
    )
    return KnowledgeGraph.build(nodes, derivations)


def initial_graph() -> KnowledgeGraph:
    """Return an earlier valid structural graph distinct from the HEAD baseline."""
    nodes = tuple(
        item
        for item in baseline_graph().nodes.values()
        if item.id not in {"nd_api_legacy_notes", "nd_legacy_reference"}
    )
    derivations = (
        Derivation(
            "dv_architecture",
            "Requirements and constraints shape architecture",
            "Product goals and operating limits jointly determine the structure.",
            (
                input_role("nd_requirements", "Provides product goals"),
                input_role("nd_constraints", "Provides operating limits"),
            ),
            (output_role("nd_architecture", "Defines the system structure"),),
        ),
        Derivation(
            "dv_api_design",
            "Architecture defines API design",
            "System boundaries determine the local interface.",
            (
                input_role("nd_architecture", "Provides component boundaries"),
                input_role("nd_requirements", "Provides endpoint goals"),
            ),
            (output_role("nd_api_design", "Defines the local API"),),
        ),
        Derivation(
            "dv_delivery",
            "Architecture drives delivery plans",
            "The same architecture informs deployment and testing.",
            (input_role("nd_architecture", "Provides runtime boundaries"),),
            (
                output_role("nd_deployment_plan", "Defines packaging and launch"),
                output_role("nd_testing_plan", "Defines verification coverage"),
            ),
        ),
    )
    return KnowledgeGraph.build(nodes, derivations)


def current_graph() -> KnowledgeGraph:
    nodes = (
        node("nd_requirements", "requirements", "docs/requirements.md"),
        node("nd_constraints", "constraints", "docs/constraints.md"),
        node(
            "nd_architecture",
            "system-architecture",
            "docs/system-architecture.md",
            "docs/architecture.svg",
        ),
        node("nd_api_design", "api-design", "docs/api-design.md"),
        node("nd_deployment_plan", "deployment-plan", "docs/deployment-plan.md"),
        node("nd_testing_plan", "testing-plan", "docs/testing-plan.md"),
        node(
            "nd_operations_guide",
            "operations-guide",
            "docs/operations-guide.md",
        ),
        node(
            "nd_api_release_notes",
            "api-release-notes",
            "docs/api-release-notes.md",
        ),
    )
    derivations = (
        Derivation(
            "dv_architecture",
            "Requirements and constraints shape architecture",
            "Product goals and operating limits jointly determine the structure.",
            (
                input_role("nd_requirements", "Provides product goals"),
                input_role("nd_constraints", "Provides operating limits"),
            ),
            (output_role("nd_architecture", "Defines the system structure"),),
        ),
        Derivation(
            "dv_api_design",
            "Validated architecture defines the public API",
            "Current boundaries and operating limits determine the interface.",
            (
                input_role(
                    "nd_architecture",
                    "Provides validated component boundaries",
                    "Includes the Git comparison adapter.",
                ),
                input_role(
                    "nd_constraints",
                    "Provides current operating limits",
                    "Keeps the interface local and read-only.",
                ),
            ),
            (
                output_role(
                    "nd_api_design",
                    "Defines validated local endpoints",
                    "Includes response contracts.",
                ),
                output_role(
                    "nd_api_release_notes",
                    "Records the current API surface",
                    "Replaces the legacy compatibility notes.",
                ),
            ),
        ),
        Derivation(
            "dv_delivery",
            "Architecture drives delivery plans",
            "The same architecture informs deployment and testing.",
            (input_role("nd_architecture", "Provides runtime boundaries"),),
            (
                output_role("nd_deployment_plan", "Defines packaging and launch"),
                output_role("nd_testing_plan", "Defines verification coverage"),
            ),
        ),
        Derivation(
            "dv_operations",
            "Deployment plan defines operations",
            "Launch and packaging decisions determine the operator workflow.",
            (input_role("nd_deployment_plan", "Provides launch decisions"),),
            (output_role("nd_operations_guide", "Defines operator steps"),),
        ),
    )
    return KnowledgeGraph.build(nodes, derivations)


def write_files(root: Path, files: dict[str, str]) -> None:
    for relative_path, content in files.items():
        path = root / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8", newline="\n")


def run_git(root: Path, *arguments: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(root), *arguments],
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    return result.stdout.strip()


def remove_fact(root: Path, group: str, fact_id: str) -> None:
    path = (root / ".kflow" / group / f"{fact_id}.json").resolve()
    expected_parent = (root / ".kflow" / group).resolve()
    if path.parent != expected_parent or not path.is_file():
        raise RuntimeError(f"Expected Demo fact is missing: {path}")
    path.unlink()


def create_demo(root: Path) -> dict:
    if root.exists():
        raise RuntimeError(f"Demo target already exists: {root}")
    root.mkdir(parents=True)
    write_files(root, BASELINE_FILES)
    initialize_project(root)
    save_graph(root, initial_graph())

    run_git(root, "init", "-b", "main")
    run_git(root, "config", "user.name", "KFlow Demo")
    run_git(root, "config", "user.email", "kflow-demo@example.local")
    for node_id in initial_graph().topological_order():
        confirm(root, node_id)
    if issues := validate(root):
        raise RuntimeError(f"Initial history validation failed: {issues}")

    run_git(
        root,
        "add",
        ".kflow/.gitignore",
        ".kflow/project.json",
        ".kflow/nodes",
        ".kflow/derivations",
        ".kflow/confirmations",
        "docs",
        "notes/personal-note.md",
    )
    run_git(root, "commit", "-m", "chore: create graph diff demo baseline")

    save_graph(root, baseline_graph())
    for node_id in baseline_graph().topological_order():
        confirm(root, node_id)
    if issues := validate(root):
        raise RuntimeError(f"HEAD baseline validation failed: {issues}")
    run_git(root, "add", ".kflow")
    run_git(root, "commit", "-m", "chore: establish graph diff HEAD baseline")

    write_files(root, CURRENT_FILES)
    save_graph(root, current_graph())
    remove_fact(root, "nodes", "nd_api_legacy_notes")
    remove_fact(root, "nodes", "nd_legacy_reference")
    remove_fact(root, "derivations", "dv_legacy_reference")
    remove_fact(root, "confirmations", "nd_api_legacy_notes")
    remove_fact(root, "confirmations", "nd_legacy_reference")
    if issues := validate(root):
        raise RuntimeError(f"Current graph validation failed: {issues}")

    head_diff = graph_diff_against_head(root)
    if not head_diff["available"]:
        raise RuntimeError(f"Graph Diff is unavailable: {head_diff['issues']}")
    _assert_head_diff(root, head_diff)

    history = query_git_history(root)
    if not history["available"] or not history["commits"]:
        raise RuntimeError(f"Structural history is unavailable: {history['issues']}")
    earlier_diff = graph_diff_against_revision(root, history["commits"][0]["commit"])
    if not earlier_diff["available"]:
        raise RuntimeError(
            f"Earlier Graph Diff is unavailable: {earlier_diff['issues']}"
        )
    if earlier_diff["summary"] == head_diff["summary"]:
        raise RuntimeError("Earlier commit must produce a distinct Graph Diff summary.")

    status = run_git(root, "status", "--short")
    if not status:
        raise RuntimeError("Demo working tree must retain uncommitted changes.")
    return {
        "head": run_git(root, "rev-parse", "HEAD"),
        "history": history,
        "head_diff": head_diff,
        "earlier_diff": earlier_diff,
        "git_status": status,
    }


def _assert_head_diff(root: Path, result: dict) -> None:
    expected_summary = {
        "added_nodes": 2,
        "removed_nodes": 2,
        "changed_nodes": 1,
        "added_derivations": 1,
        "removed_derivations": 1,
        "changed_derivations": 3,
        "topology_changed": True,
    }
    if result["summary"] != expected_summary:
        raise RuntimeError(f"Unexpected HEAD Graph Diff summary: {result['summary']}")
    expected_ids = {
        "nodes.added": {"nd_api_release_notes", "nd_operations_guide"},
        "nodes.removed": {"nd_api_legacy_notes", "nd_legacy_reference"},
        "nodes.changed": {"nd_architecture"},
        "derivations.added": {"dv_operations"},
        "derivations.removed": {"dv_legacy_reference"},
        "derivations.changed": {
            "dv_api_design",
            "dv_architecture",
            "dv_delivery",
        },
    }
    actual_ids = {
        "nodes.added": {item["id"] for item in result["nodes"]["added"]},
        "nodes.removed": {item["id"] for item in result["nodes"]["removed"]},
        "nodes.changed": {item["id"] for item in result["nodes"]["changed"]},
        "derivations.added": {item["id"] for item in result["derivations"]["added"]},
        "derivations.removed": {
            item["id"] for item in result["derivations"]["removed"]
        },
        "derivations.changed": {
            item["id"] for item in result["derivations"]["changed"]
        },
    }
    if actual_ids != expected_ids:
        raise RuntimeError(f"Unexpected HEAD Graph Diff IDs: {actual_ids}")
    graph = query_project_graph(root)
    registered = {path for node in graph["nodes"] for path in node["files"]}
    if "notes/personal-note.md" in registered:
        raise RuntimeError("Unregistered personal note entered the project graph.")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("demo_root", type=Path)
    arguments = parser.parse_args()
    root = arguments.demo_root.resolve()
    result = create_demo(root)
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
