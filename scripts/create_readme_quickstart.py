"""Create the ordinary files used by the README Quickstart.

This onboarding helper deliberately does not import KFlow or invoke Git.  The
user builds and confirms the example graph with the documented KFlow CLI.
"""

from __future__ import annotations

import argparse
import shutil
import sys
from collections.abc import Sequence
from pathlib import Path


QUICKSTART_FILES = {
    "docs/requirements.md": """# Requirements

The local project view must help both human maintainers and an AI Agent understand the registered knowledge structure.

It must:

- show the important Knowledge Nodes and their explicit relationships;
- show the current scope that needs review and the reason for each item;
- let a user open a registered file through a read-only action;
- keep the Human Interface and Agent Interface aligned on the same project facts.
""",
    "docs/constraints.md": """# Constraints

The product must respect these operating boundaries:

- the local service listens only on localhost;
- the Human Interface remains read-only;
- the Python runtime introduces no third-party dependency;
- the browser must never request or open arbitrary project files;
- project knowledge and structural history remain backed by explicit metadata and Git.
""",
    "docs/architecture.md": """# Architecture

The requirements and constraints lead to four cooperating parts:

- a Core query layer that owns project graph and review-order facts;
- a local HTTP adapter that exposes those facts without duplicating domain logic;
- a browser UI that presents the graph to human maintainers;
- Git-backed structural history for comparing the current graph with earlier structure.

The browser stays read-only and consumes the same Core results used by an Agent.
""",
    "docs/api-design.md": """# API Design

The architecture is exposed through narrowly scoped local endpoints:

- `/api/project` returns the complete registered project graph;
- `/api/review-order` returns the current affected scope and review order;
- `/api/git-history` lists relevant structural commits;
- `/api/graph-diff` compares graph structure with a selected Git baseline.

Every endpoint preserves the read-only boundary and returns project facts rather than document contents.
""",
    "docs/testing-plan.md": """# Testing Plan

The architecture requires verification at each boundary:

- Core tests cover graph invariants, status propagation, and stable ordering;
- API tests cover response contracts and restricted file opening;
- frontend tests cover graph rendering, selection, and review-order presentation;
- packaged UI verification checks that production assets ship with Python;
- concurrency and stale-response tests ensure an older reload cannot replace newer state.
""",
    "docs/deployment-plan.md": """# Deployment Plan

The API design leads to a local, packaged delivery model:

- publish KFlow as a Python package;
- bundle the built static assets inside that package;
- launch the local interface with `kflow ui`;
- bind the service to localhost and stop it with the foreground process;
- require no Node.js installation from the end user.
""",
}


def _write_file(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8", newline="\n")


def create_quickstart(target: Path | str = Path("kflow-quickstart")) -> Path:
    """Create a new ordinary-file Quickstart directory and return its path."""
    root = Path(target).expanduser().resolve()
    if root.exists():
        raise FileExistsError(f"Quickstart target already exists: {root}")

    created = False
    try:
        root.mkdir(parents=True)
        created = True
        for relative_path, content in QUICKSTART_FILES.items():
            _write_file(root / relative_path, content)
    except Exception:
        if created:
            shutil.rmtree(root)
        raise
    return root


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Create the ordinary files for the KFlow README Quickstart."
    )
    parser.add_argument(
        "target",
        nargs="?",
        type=Path,
        default=Path("kflow-quickstart"),
        help="New target directory (default: ./kflow-quickstart).",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    arguments = build_parser().parse_args(argv)
    try:
        root = create_quickstart(arguments.target)
    except Exception as error:
        print(f"Could not create quickstart files: {error}", file=sys.stderr)
        return 1

    print(f"Quickstart files created at: {root}")
    print()
    print("No KFlow metadata has been created.")
    print("Follow README.md to run:")
    print("  kflow init")
    print("  kflow add-node ...")
    print("  kflow derive ...")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
