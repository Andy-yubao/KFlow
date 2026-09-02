"""Create the optional Git-backed project used by Quickstart Part 2.

The helper creates a real repository with three deterministic structural
commits, then deliberately leaves one upstream content edit and one isolated
Node uncommitted. It is demo tooling, not a production KFlow command.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
from pathlib import Path

from kflow.core.graph import KnowledgeGraph
from kflow.core.models import (
    Derivation,
    DerivationInput,
    DerivationOutput,
    KnowledgeNode,
)
from kflow.core.query import query_project_graph, query_review_order
from kflow.core.scan import confirm, validate
from kflow.core.storage import initialize_project, save_graph
from kflow.human.git_snapshot import (
    graph_diff_against_head,
    graph_diff_against_revision,
    query_git_history,
)


SOURCE_FILES = {
    "docs/requirements.md": """# Requirements

The release must expose a small, read-only project knowledge view.
""",
    "docs/security-constraints.md": """# Security Constraints

The local service must remain loopback-only and must not expose document bodies.
""",
}

PLANNING_FILES = {
    "docs/api-design.md": """# API Design

The local adapter exposes narrowly scoped project and review endpoints.
""",
    "docs/testing-plan.md": """# Testing Plan

Core, HTTP, and browser boundaries require automated and manual verification.
""",
}

DELIVERY_FILES = {
    "docs/deployment-plan.md": """# Deployment Plan

The package bundles the read-only browser assets and starts a localhost service.
""",
    "docs/release-checklist.md": """# Release Checklist

Validate the graph, run the test suite, and inspect the packaged Human Interface.
""",
}

WORKTREE_FILES = {
    "docs/requirements.md": """# Requirements

The release must expose a small, read-only project knowledge view.

The next iteration must also export a portable project summary.
""",
    "docs/research-notes.md": """# Research Notes

This intentionally isolated Node provides a neutral structure-color example.
""",
}

COMMIT_DATES = (
    "2026-01-10T09:00:00+00:00",
    "2026-01-10T09:05:00+00:00",
    "2026-01-10T09:10:00+00:00",
)


def node(node_id: str, name: str, file: str) -> KnowledgeNode:
    return KnowledgeNode(node_id, name, (file,))


def input_role(node_id: str, short: str) -> DerivationInput:
    return DerivationInput(node_id, short, "")


def output_role(node_id: str, short: str) -> DerivationOutput:
    return DerivationOutput(node_id, short, "")


def source_graph() -> KnowledgeGraph:
    return KnowledgeGraph.build(
        (
            node("nd_requirements", "requirements", "docs/requirements.md"),
            node(
                "nd_security_constraints",
                "security-constraints",
                "docs/security-constraints.md",
            ),
        ),
        (),
    )


def planning_graph() -> KnowledgeGraph:
    nodes = (
        *source_graph().nodes.values(),
        node("nd_api_design", "api-design", "docs/api-design.md"),
        node("nd_testing_plan", "testing-plan", "docs/testing-plan.md"),
    )
    derivations = (
        Derivation(
            "dv_design_and_testing",
            "Requirements shape design and testing plans",
            "One upstream brief produces two coordinated plans.",
            (input_role("nd_requirements", "Provides product goals"),),
            (
                output_role("nd_api_design", "Defines the API plan"),
                output_role("nd_testing_plan", "Defines verification coverage"),
            ),
        ),
    )
    return KnowledgeGraph.build(nodes, derivations)


def delivery_graph() -> KnowledgeGraph:
    nodes = (
        *planning_graph().nodes.values(),
        node(
            "nd_deployment_plan",
            "deployment-plan",
            "docs/deployment-plan.md",
        ),
        node(
            "nd_release_checklist",
            "release-checklist",
            "docs/release-checklist.md",
        ),
    )
    derivations = (
        *planning_graph().derivations.values(),
        Derivation(
            "dv_deployment",
            "Design and security constraints shape deployment",
            "The deployable plan combines the API boundary with security limits.",
            (
                input_role("nd_api_design", "Provides the runtime API boundary"),
                input_role(
                    "nd_security_constraints",
                    "Provides the security boundary",
                ),
            ),
            (output_role("nd_deployment_plan", "Defines packaged delivery"),),
        ),
        Derivation(
            "dv_release",
            "Deployment plan produces the release checklist",
            "One delivery plan maps to one operational checklist.",
            (input_role("nd_deployment_plan", "Provides release steps"),),
            (
                output_role(
                    "nd_release_checklist",
                    "Defines release verification",
                ),
            ),
        ),
    )
    return KnowledgeGraph.build(nodes, derivations)


def working_graph() -> KnowledgeGraph:
    return KnowledgeGraph.build(
        (
            *delivery_graph().nodes.values(),
            node("nd_research_notes", "research-notes", "docs/research-notes.md"),
        ),
        delivery_graph().derivations.values(),
    )


def write_files(root: Path, files: dict[str, str]) -> None:
    for relative_path, content in files.items():
        path = root / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8", newline="\n")


def run_git(
    root: Path, *arguments: str, environment: dict[str, str] | None = None
) -> str:
    creationflags = 0
    if os.name == "nt":
        creationflags = subprocess.CREATE_NO_WINDOW
    result = subprocess.run(
        ["git", "-C", str(root), *arguments],
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
        env=environment,
        creationflags=creationflags,
    )
    return result.stdout.strip()


def commit(root: Path, message: str, committed_at: str) -> str:
    environment = os.environ.copy()
    environment.update(
        {
            "GIT_AUTHOR_DATE": committed_at,
            "GIT_COMMITTER_DATE": committed_at,
        }
    )
    run_git(
        root,
        "-c",
        "commit.gpgSign=false",
        "commit",
        "-m",
        message,
        environment=environment,
    )
    return run_git(root, "rev-parse", "HEAD")


def confirm_graph(root: Path, graph: KnowledgeGraph) -> None:
    for node_id in graph.topological_order():
        confirm(root, node_id)
    if issues := validate(root):
        raise RuntimeError(f"Demo graph validation failed: {issues}")


def create_demo(root: Path) -> dict:
    root = root.resolve()
    if root.exists():
        raise RuntimeError(f"Demo target already exists: {root}")
    root.mkdir(parents=True)
    try:
        write_files(root, SOURCE_FILES)
        initialize_project(root)
        first_graph = source_graph()
        save_graph(root, first_graph)
        confirm_graph(root, first_graph)

        run_git(root, "init", "-b", "main")
        run_git(root, "config", "user.name", "KFlow Demo")
        run_git(root, "config", "user.email", "kflow-demo@example.local")
        run_git(root, "config", "core.autocrlf", "false")
        run_git(root, "add", ".kflow", "docs")
        first_commit = commit(root, "demo: add project requirements", COMMIT_DATES[0])

        write_files(root, PLANNING_FILES)
        second_graph = planning_graph()
        save_graph(root, second_graph)
        confirm_graph(root, second_graph)
        run_git(root, "add", ".kflow", "docs")
        second_commit = commit(
            root,
            "demo: derive design and testing plans",
            COMMIT_DATES[1],
        )

        write_files(root, DELIVERY_FILES)
        head_graph = delivery_graph()
        save_graph(root, head_graph)
        confirm_graph(root, head_graph)
        run_git(root, "add", ".kflow", "docs")
        head_commit = commit(
            root,
            "demo: derive deployment and release plans",
            COMMIT_DATES[2],
        )

        write_files(root, WORKTREE_FILES)
        save_graph(root, working_graph())
        if issues := validate(root):
            raise RuntimeError(f"Working tree validation failed: {issues}")

        result = _verify_demo(
            root,
            commits=(first_commit, second_commit, head_commit),
        )
    except Exception:
        shutil.rmtree(root)
        raise
    return result


def _verify_demo(root: Path, commits: tuple[str, str, str]) -> dict:
    graph = query_project_graph(root)
    if not graph["ok"]:
        raise RuntimeError(f"Project graph query failed: {graph['issues']}")
    derivation_shapes = {
        (len(item["inputs"]), len(item["outputs"])) for item in graph["derivations"]
    }
    if derivation_shapes != {(1, 1), (1, 2), (2, 1)}:
        raise RuntimeError(f"Unexpected topology coverage: {derivation_shapes}")

    by_name = {item["name"]: item for item in graph["nodes"]}
    expected_reasons = {
        "requirements": ["files_changed"],
        "security-constraints": [],
        "api-design": ["input_changed"],
        "testing-plan": ["input_changed"],
        "deployment-plan": ["input_changed"],
        "release-checklist": ["input_changed"],
        "research-notes": ["unconfirmed"],
    }
    actual_reasons = {name: by_name[name]["reasons"] for name in expected_reasons}
    if actual_reasons != expected_reasons:
        raise RuntimeError(f"Unexpected review reasons: {actual_reasons}")

    review = query_review_order(root)
    expected_review_ids = [
        node_id
        for node_id in graph["topological_order"]
        if next(item for item in graph["nodes"] if item["id"] == node_id)["reasons"]
    ]
    if review["review_order"] != expected_review_ids:
        raise RuntimeError(f"Unexpected review order: {review['review_order']}")

    history = query_git_history(root)
    if not history["available"] or len(history["commits"]) < 2:
        raise RuntimeError(f"Structural history is incomplete: {history['issues']}")
    if run_git(root, "rev-parse", "HEAD~1") != commits[1]:
        raise RuntimeError("HEAD~1 does not resolve to the planning commit.")
    if run_git(root, "rev-parse", "HEAD~2") != commits[0]:
        raise RuntimeError("HEAD~2 does not resolve to the source commit.")

    head_diff = graph_diff_against_head(root)
    if not head_diff["available"]:
        raise RuntimeError(f"Graph Diff vs HEAD failed: {head_diff['issues']}")
    expected_summary = {
        "added_nodes": 1,
        "removed_nodes": 0,
        "changed_nodes": 0,
        "added_derivations": 0,
        "removed_derivations": 0,
        "changed_derivations": 0,
        "topology_changed": True,
    }
    if head_diff["summary"] != expected_summary:
        raise RuntimeError(f"Unexpected HEAD diff: {head_diff['summary']}")

    historical_diffs = {
        "HEAD~1": graph_diff_against_revision(root, commits[1]),
        "HEAD~2": graph_diff_against_revision(root, commits[0]),
    }
    if not all(item["available"] for item in historical_diffs.values()):
        raise RuntimeError("A historical Graph Diff is unavailable.")

    git_status = run_git(root, "status", "--short")
    if not git_status:
        raise RuntimeError("Demo working tree must retain uncommitted changes.")
    return {
        "head": commits[2],
        "refs": {"HEAD~1": commits[1], "HEAD~2": commits[0]},
        "commits": list(commits),
        "history": history,
        "head_diff": head_diff,
        "historical_diffs": historical_diffs,
        "review_order": review,
        "git_status": git_status,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("demo_root", type=Path)
    arguments = parser.parse_args()
    result = create_demo(arguments.demo_root)
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
