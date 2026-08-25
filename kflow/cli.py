"""KFlow command-line interface."""

import argparse
import json
import sys
from pathlib import Path

from kflow.core.operations import add_derivation, add_node
from kflow.core.query import query_affected_context, query_context, query_impact
from kflow.core.scan import confirm
from kflow.core.scan import scan as scan_project
from kflow.core.scan import scan_and_sync
from kflow.core.scan import validate as validate_project
from kflow.core.storage import initialize_project


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="kflow",
        description=(
            "Understand important project knowledge, what changed, and what to "
            "review next."
        ),
        epilog=(
            "Typical workflow: kflow status -> kflow context --affected -> "
            "review files -> kflow confirm NODE"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Return the stable machine-readable result.",
    )
    sub = parser.add_subparsers(dest="command", title="commands", metavar="COMMAND")

    p_init = sub.add_parser(
        "init",
        help="Initialize KFlow in a project.",
        description="Create Git-native KFlow metadata without scanning project files.",
    )
    p_init.add_argument(
        "path",
        nargs="?",
        default=".",
        help="Project path (default: current directory).",
    )
    _add_json_option(p_init)

    p_add = sub.add_parser(
        "add-node",
        help="Register existing files as one Knowledge Node.",
        description="Register one complete knowledge unit made from existing files.",
    )
    p_add.add_argument("name", help="Unique, human-readable Node name.")
    p_add.add_argument(
        "--file",
        action="append",
        required=True,
        dest="files",
        help="Project-relative file path; repeat for a multi-file Node.",
    )
    _add_json_option(p_add)

    p_derive = sub.add_parser(
        "derive",
        help="Connect existing Nodes with an explicit Derivation.",
        description="Record one explainable, acyclic derivation between existing Nodes.",
    )
    p_derive.add_argument(
        "--short", required=True, help="Short derivation explanation."
    )
    p_derive.add_argument("--detail", default="", help="Optional detailed explanation.")
    p_derive.add_argument(
        "--input",
        nargs=2,
        action="append",
        required=True,
        metavar=("NODE", "SHORT"),
        help="Input Node and its role; repeat for additional inputs.",
    )
    p_derive.add_argument(
        "--output",
        nargs=2,
        action="append",
        required=True,
        metavar=("NODE", "SHORT"),
        help="Output Node and its role; repeat for additional outputs.",
    )
    _add_json_option(p_derive)

    p_status = sub.add_parser(
        "status",
        help="Show project health and Nodes needing attention.",
        description=(
            "Explain the current project state, what needs review, and why. "
            "This operation is read-only."
        ),
    )
    _add_json_option(p_status)

    p_scan = sub.add_parser(
        "scan",
        help="Observe managed file changes and current Node status.",
        description=(
            "Compare managed files with the last observation and refresh only the "
            "rebuildable local scan cache."
        ),
    )
    _add_json_option(p_scan)

    p_confirm = sub.add_parser(
        "confirm",
        help="Record that one Node has been reviewed.",
        description=(
            "Confirm exactly one Node under its current files, producer, and direct "
            "input conditions. Confirmation never cascades."
        ),
    )
    p_confirm.add_argument("node", help="Node ID, name, or registered file path.")
    _add_json_option(p_confirm)

    p_validate = sub.add_parser(
        "validate",
        help="Check metadata, file references, and graph invariants.",
        description="Report structural issues without changing project files.",
    )
    _add_json_option(p_validate)

    p_context = sub.add_parser(
        "context",
        help="Show why a Node or current review scope matters.",
        description=(
            "Show registered paths, relationships, impact, and review order without "
            "returning file contents."
        ),
    )
    p_context.add_argument(
        "node", nargs="?", help="Node ID, name, or registered file path."
    )
    p_context.add_argument(
        "--affected",
        action="store_true",
        help="Show the current affected scope and recommended review order.",
    )
    _add_json_option(p_context)

    p_explain = sub.add_parser(
        "explain",
        help="Explain a Node's downstream impact.",
        description="Trace direct and indirect impact from one explicit change root.",
    )
    p_explain.add_argument("node", help="Node ID, name, or registered file path.")
    _add_json_option(p_explain)

    p_review = sub.add_parser(
        "review-order",
        help="Show the recommended review order for current changes.",
        description="List affected Nodes in a stable, upstream-first order.",
    )
    _add_json_option(p_review)

    return parser


def _add_json_option(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--json",
        action="store_true",
        help="Return the stable machine-readable result.",
    )


def main(argv=None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)

    if not args.command:
        parser.print_help()
        raise SystemExit(1)

    try:
        dispatch(args)
    except Exception as error:
        if getattr(args, "json", False):
            print(
                json.dumps(
                    {
                        "ok": False,
                        "error": str(error),
                        "type": type(error).__name__,
                    },
                    ensure_ascii=False,
                    sort_keys=True,
                )
            )
        else:
            print(f"KFlow could not complete the command: {error}", file=sys.stderr)
        raise SystemExit(2) from error


def dispatch(args) -> None:
    """Run one official KFlow command."""
    root = Path.cwd()
    if args.command == "init":
        root = Path(args.path).resolve()
        initialize_project(root)
        result = {"ok": True, "schema_version": 2, "root": str(root)}
    elif args.command == "add-node":
        node = add_node(root, args.name, tuple(args.files))
        result = {
            "ok": True,
            "schema_version": 2,
            "node": {
                "id": node.id,
                "name": node.name,
                "files": list(node.files),
            },
        }
    elif args.command == "derive":
        derivation = add_derivation(
            root,
            args.short,
            args.detail,
            tuple((node, short, "") for node, short in args.input),
            tuple((node, short, "") for node, short in args.output),
        )
        result = {
            "ok": True,
            "schema_version": 2,
            "derivation": {
                "id": derivation.id,
                "inputs": [node for node, _short in args.input],
                "outputs": [node for node, _short in args.output],
            },
        }
    elif args.command == "status":
        result = _status_result(root)
    elif args.command == "scan":
        result = _scan_result(root)
    elif args.command == "confirm":
        before, after = confirm(root, args.node)
        current = _status_result(root)
        result = {
            "ok": True,
            "schema_version": 2,
            "node": after.node,
            "before": {"status": before.status, "reasons": list(before.reasons)},
            "after": {"status": after.status, "reasons": list(after.reasons)},
            "remaining_review": [
                item["id"] for item in current["nodes"] if item["reasons"]
            ],
        }
    elif args.command == "validate":
        issues = validate_project(root)
        result = {
            "ok": not issues,
            "schema_version": 2,
            "issues": [
                {
                    "code": issue.code,
                    "message": issue.message,
                    "references": list(issue.references),
                }
                for issue in issues
            ],
        }
    elif args.command == "context":
        if args.affected and args.node is not None:
            raise ValueError("context accepts either NODE or --affected, not both")
        if args.affected:
            result = query_affected_context(root)
        elif args.node is not None:
            result = query_context(root, args.node)
        else:
            raise ValueError("context requires NODE or --affected")
    elif args.command == "explain":
        result = query_impact(root, args.node)
    elif args.command == "review-order":
        result = query_impact(root)
    else:
        raise ValueError(f"unknown command: {args.command}")
    _print_result(result, getattr(args, "json", False), args.command)


def _status_result(root: Path) -> dict:
    return _status_from_scan(scan_project(root))


def _status_from_scan(scanned) -> dict:
    nodes = []
    for node_id in scanned.graph.topological_order():
        node = scanned.graph.nodes[node_id]
        status = scanned.statuses.get(node_id)
        nodes.append(
            {
                "id": node.id,
                "name": node.name,
                "files": list(node.files),
                "status": None if status is None else status.status,
                "reasons": [] if status is None else list(status.reasons),
                "changed_files": [] if status is None else list(status.changed_files),
            }
        )
    return {
        "ok": not scanned.issues,
        "schema_version": 2,
        "nodes": nodes,
        "issues": [
            {
                "code": issue.code,
                "message": issue.message,
                "references": list(issue.references),
            }
            for issue in scanned.issues
        ],
    }


def _scan_result(root: Path) -> dict:
    summary = scan_and_sync(root)
    status = _status_from_scan(summary.scanned)
    return {
        **status,
        "changes": {
            "added": list(summary.added_files),
            "modified": list(summary.modified_files),
            "deleted": list(summary.deleted_files),
        },
        "fingerprints": [
            {
                "path": path,
                "fingerprint": {
                    "algorithm": fingerprint.algorithm,
                    "value": fingerprint.value,
                },
            }
            for path, fingerprint in sorted(summary.scanned.file_fingerprints.items())
        ],
    }


def _print_result(result: dict, json_output: bool, command: str) -> None:
    if json_output:
        print(json.dumps(result, ensure_ascii=False, sort_keys=True))
        return
    printers = {
        "status": _print_status,
        "scan": _print_scan,
        "context": _print_context,
        "explain": _print_explanation,
        "review-order": _print_review_order,
        "validate": _print_validation,
    }
    if command in printers:
        printers[command](result)
    elif command == "init":
        print(f"Initialized KFlow at {result['root']}")
    elif command == "add-node":
        node = result["node"]
        print(f"Registered Node {node['name']} ({node['id']})")
        for path in node["files"]:
            print(f"- {path}")
    elif command == "derive":
        derivation = result["derivation"]
        print(f"Created Derivation {derivation['id']}")
        print(f"Inputs: {', '.join(derivation['inputs'])}")
        print(f"Outputs: {', '.join(derivation['outputs'])}")
    elif command == "confirm":
        print(f"Confirmed Node {result['node']}")
        print(f"Remaining Nodes needing review: {len(result['remaining_review'])}")


def _print_status(result: dict) -> None:
    nodes = result["nodes"]
    issues = result["issues"]
    needs_review = [node for node in nodes if node["reasons"]]
    current = len(nodes) - len(needs_review)
    state = (
        "blocked by validation issues"
        if issues
        else "attention required"
        if needs_review
        else "current"
    )

    print("KFlow project status")
    print(f"State: {state}")
    print(
        f"Summary: {len(nodes)} Nodes; {current} current; "
        f"{len(needs_review)} need review; {len(issues)} issues"
    )
    print("\nNeeds attention:")
    if not needs_review:
        print("none")
    for node in needs_review:
        reasons = ", ".join(node["reasons"])
        print(f"- {node['name']} [{reasons}]")
        print(f"  Why: {_explain_reasons(node['reasons'])}")
        relevant_files = node["changed_files"] or node["files"]
        print(f"  Files: {', '.join(relevant_files)}")

    print("\nValidation issues:")
    _print_issues(issues)
    if needs_review and not issues:
        print("\nNext: run 'kflow context --affected' for impact and review order.")


def _explain_reasons(reasons: list[str]) -> str:
    descriptions = {
        "unconfirmed": "no review baseline has been recorded",
        "files_changed": "registered files changed since the last confirmation",
        "derivation_changed": "the producing Derivation changed",
        "input_changed": "one or more direct input Nodes changed",
    }
    return "; ".join(descriptions.get(reason, reason) for reason in reasons)


def _print_validation(result: dict) -> None:
    if result["ok"]:
        print("KFlow metadata is valid.")
        return
    print("KFlow metadata has validation issues:")
    _print_issues(result["issues"])


def _print_issues(issues: list[dict]) -> None:
    if not issues:
        print("none")
    for issue in issues:
        references = ", ".join(issue.get("references", []))
        suffix = f" ({references})" if references else ""
        print(f"- {issue['code']}: {issue['message']}{suffix}")


def _print_context(result: dict) -> None:
    node = result["node"]
    if node is None:
        _print_affected_context(result)
        return
    relations = result["relations"]
    affected = result["impact"]["affected_nodes"]
    names = {
        item["id"]: item["name"] for item in (node, *relations["upstream"], *affected)
    }
    print("Target Node:")
    print(f"{node['name']} ({node['id']})")
    print("\nFiles:")
    for path in node["files"]:
        print(path)
    print("\nCurrent Status:")
    print(result["status"])
    print("\nWhy Relevant:")
    if not result["reasons"]:
        print("none")
    for reason in result["reasons"]:
        print(f"{reason}: {_explain_reasons([reason])}")
    print("\nUpstream Dependencies:")
    _print_node_names(relations["upstream"])
    print("\nDownstream Impact:")
    _print_impacts(affected, names)
    print("\nRelated Derivations:")
    if not relations["derivations"]:
        print("none")
    for derivation in relations["derivations"]:
        print(f"{derivation['id']}: {derivation['short']}")
    print("\nRecommended Review Order:")
    _print_named_order(result["review_order"], names)
    print("\nValidation Issues:")
    _print_issues(result["issues"])


def _print_explanation(result: dict) -> None:
    roots = result["impact"]["changed_nodes"]
    affected = result["impact"]["affected_nodes"]
    names = {node["id"]: node["name"] for node in (*roots, *affected)}
    print("Cause:")
    if not roots:
        print("none")
    for node in roots:
        reasons = ", ".join(node["reasons"]) or "explicit impact query"
        print(f"{node['name']}: {reasons}")

    direct = [item for item in affected if item["depth"] == 1]
    indirect = [item for item in affected if item["depth"] > 1]
    print("\nDirect impact:")
    _print_impacts(direct, names)
    print("\nIndirect impact:")
    _print_impacts(indirect, names)
    print("\nRecommended review order:")
    _print_review_items(result)
    print("\nValidation issues:")
    _print_issues(result["issues"])


def _print_review_order(result: dict) -> None:
    print("Recommended review order:")
    _print_review_items(result)
    print("\nValidation issues:")
    _print_issues(result["issues"])


def _print_node_names(nodes: list[dict]) -> None:
    if not nodes:
        print("none")
    for node in nodes:
        print(node["name"])


def _print_impacts(nodes: list[dict], names: dict[str, str]) -> None:
    if not nodes:
        print("none")
    for node in nodes:
        path = " -> ".join(names[node_id] for node_id in node["paths"][0]["nodes"])
        print(node["name"])
        print(f"Reason: {node['impact_reason']} via {path}")


def _print_review_items(result: dict) -> None:
    nodes = {
        node["id"]: node["name"]
        for node in (
            *result["impact"]["changed_nodes"],
            *result["impact"]["affected_nodes"],
        )
    }
    _print_named_order(result["review_order"], nodes)


def _print_affected_context(result: dict) -> None:
    roots = result["impact"]["changed_nodes"]
    affected = result["impact"]["affected_nodes"]
    names = {node["id"]: node["name"] for node in (*roots, *affected)}
    print("Changed Nodes:")
    _print_node_names(roots)
    print("\nNeed Review:")
    _print_named_order(result["review_order"], names)
    print("\nReasons:")
    if not result["reasons"]:
        print("none")
    for item in roots:
        reasons = ", ".join(item["reasons"]) or "none"
        print(f"{item['name']}: {reasons}")
    print("\nValidation Issues:")
    _print_issues(result["issues"])


def _print_scan(result: dict) -> None:
    print("Managed file changes:")
    found = False
    for label in ("added", "modified", "deleted"):
        for path in result["changes"][label]:
            found = True
            print(f"- {label}: {path}")
    if not found:
        print("none")
    print("")
    _print_status(result)


def _print_named_order(order: list[str], names: dict[str, str]) -> None:
    if not order:
        print("none")
    for position, node_id in enumerate(order, start=1):
        print(f"{position}. {names[node_id]}")
