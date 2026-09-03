"""KFlow command-line interface."""

import argparse
import json
import sys
from pathlib import Path

from kflow.core.graph import GraphValidationError
from kflow.core.operations import (
    add_derivation,
    add_node,
    edit_derivation,
    edit_node,
    remove_derivation,
    remove_node,
)
from kflow.core.query import (
    present_derivation,
    query_context,
    query_impact,
    query_project_graph,
    query_review_order,
)
from kflow.core.schema_versions import (
    MUTATION_SCHEMA_VERSION,
    TASK_QUERY_SCHEMA_VERSION,
)
from kflow.core.scan import confirm
from kflow.core.scan import validate as validate_project
from kflow.core.storage import StorageError, initialize_project, load_graph
from kflow.human.runtime import print_ui_status, start_ui, stop_ui


class KFlowArgumentParser(argparse.ArgumentParser):
    """Argument parser that preserves the JSON error contract."""

    json_error_mode = False

    def error(self, message: str) -> None:
        if self.json_error_mode:
            result = {
                "ok": False,
                "schema_version": TASK_QUERY_SCHEMA_VERSION,
                "issues": [
                    {
                        "code": "invalid_argument",
                        "message": message,
                        "references": [],
                    }
                ],
            }
            print(json.dumps(result, ensure_ascii=False, sort_keys=True))
            raise SystemExit(2)
        super().error(message)


def build_parser() -> argparse.ArgumentParser:
    parser = KFlowArgumentParser(
        prog="kflow",
        description=(
            "Understand important project knowledge, direct relationships, and "
            "what to review next."
        ),
        epilog=(
            "Typical workflow: kflow overview -> kflow review-order -> "
            "kflow context NODE -> review files -> kflow confirm NODE"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--json",
        action="store_true",
        default=argparse.SUPPRESS,
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

    p_node = sub.add_parser("node", help="Maintain Knowledge Nodes.")
    node_commands = p_node.add_subparsers(dest="entity_action", metavar="ACTION")
    p_node_add = node_commands.add_parser(
        "add", help="Register existing files as one Knowledge Node."
    )
    p_node_add.add_argument("name", help="Unique, human-readable Node name.")
    _add_files_argument(p_node_add)
    _add_json_option(p_node_add)
    p_node_edit = node_commands.add_parser(
        "edit", help="Replace one Node's complete definition."
    )
    p_node_edit.add_argument("old_name", help="Exact current Node name.")
    p_node_edit.add_argument("--name", required=True, help="Complete new Node name.")
    _add_files_argument(p_node_edit)
    _add_json_option(p_node_edit)
    p_node_remove = node_commands.add_parser(
        "remove", help="Remove an unreferenced Node."
    )
    p_node_remove.add_argument("name", help="Exact current Node name.")
    _add_json_option(p_node_remove)
    _add_json_option(p_node)
    p_node.set_defaults(entity_parser=p_node)

    p_derivation = sub.add_parser("derivation", help="Maintain Derivations.")
    derivation_commands = p_derivation.add_subparsers(
        dest="entity_action", metavar="ACTION"
    )
    p_derivation_add = derivation_commands.add_parser(
        "add", help="Connect Nodes with an explicit Derivation."
    )
    p_derivation_add.add_argument("name", help="Unique Derivation name.")
    _add_derivation_definition_arguments(p_derivation_add)
    _add_json_option(p_derivation_add)
    p_derivation_edit = derivation_commands.add_parser(
        "edit", help="Replace one Derivation's complete definition."
    )
    p_derivation_edit.add_argument("old_name", help="Exact current Derivation name.")
    p_derivation_edit.add_argument(
        "--name", required=True, help="Complete new Derivation name."
    )
    _add_derivation_definition_arguments(p_derivation_edit)
    _add_json_option(p_derivation_edit)
    p_derivation_remove = derivation_commands.add_parser(
        "remove", help="Remove one Derivation without removing Nodes."
    )
    p_derivation_remove.add_argument("name", help="Exact current Derivation name.")
    _add_json_option(p_derivation_remove)
    _add_json_option(p_derivation)
    p_derivation.set_defaults(entity_parser=p_derivation)

    p_overview = sub.add_parser(
        "overview",
        help="Show the complete project knowledge topology.",
        description="Show every complete Derivation in stable topological order.",
    )
    p_overview.add_argument(
        "--status", action="store_true", help="Mark Nodes that currently need review."
    )
    _add_json_option(p_overview)

    p_context = sub.add_parser(
        "context",
        help="Show one Node's direct local relationships.",
        description="Show the target, its producer, and its direct consumer Derivations.",
    )
    p_context.add_argument("node", help="Node ID, name, or registered file path.")
    _add_json_option(p_context)

    p_impact = sub.add_parser(
        "impact",
        help="Show direct Derivations and further downstream Nodes.",
        description="Start from one explicit Node and inspect its structural downstream.",
    )
    p_impact.add_argument("node", help="Node ID, name, or registered file path.")
    _add_json_option(p_impact)

    p_review = sub.add_parser(
        "review-order",
        help="Show the current stable review order.",
        description="List only Nodes that still need review, with upstream first.",
    )
    p_review.add_argument(
        "node",
        nargs="?",
        help="Optional Node limiting the scope to its downstream subgraph.",
    )
    _add_json_option(p_review)

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

    p_ui = sub.add_parser(
        "ui",
        help="Open the local read-only Human Interface.",
        description=("Manage the current project's read-only UI on 127.0.0.1."),
    )
    ui_commands = p_ui.add_subparsers(dest="ui_command", metavar="ACTION")
    p_ui_start = ui_commands.add_parser("start", help="Start or reuse the UI.")
    ui_commands.add_parser("stop", help="Stop this project's UI.")
    ui_commands.add_parser("status", help="Show this project's UI status.")
    _add_ui_start_options(p_ui_start)
    _add_json_option(p_ui)
    p_ui.set_defaults(ui_parser=p_ui)
    return parser


def _add_ui_start_options(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--port",
        type=_port_number,
        default=0,
        help="Loopback port (default: choose a random available port).",
    )
    parser.add_argument(
        "--no-open", action="store_true", help="Do not open the browser automatically."
    )


def _add_files_argument(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--file",
        action="append",
        required=True,
        dest="files",
        help="Project-relative file path; repeat for a multi-file Node.",
    )


def _add_derivation_definition_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--short", required=True, help="Short derivation explanation.")
    parser.add_argument("--detail", default="", help="Optional detailed explanation.")
    parser.add_argument(
        "--input",
        nargs=2,
        action="append",
        required=True,
        metavar=("NODE", "SHORT"),
        help="Input Node and its role; repeat for additional inputs.",
    )
    parser.add_argument(
        "--output",
        nargs=2,
        action="append",
        required=True,
        metavar=("NODE", "SHORT"),
        help="Output Node and its role; repeat for additional outputs.",
    )


def _add_json_option(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--json",
        action="store_true",
        default=argparse.SUPPRESS,
        help="Return the stable machine-readable result.",
    )


def _port_number(value: str) -> int:
    port = int(value)
    if not 0 <= port <= 65535:
        raise argparse.ArgumentTypeError("port must be between 0 and 65535")
    return port


def main(argv=None) -> None:
    parser = build_parser()
    arguments = list(sys.argv[1:] if argv is None else argv)
    _set_json_error_mode(parser, "--json" in arguments)
    args = parser.parse_args(arguments)

    if not args.command and getattr(args, "json", False):
        parser.error("a command is required")
    if not args.command:
        parser.print_help()
        raise SystemExit(1)
    if args.command in {"node", "derivation"} and args.entity_action is None:
        if getattr(args, "json", False):
            args.entity_parser.error("an action is required")
        args.entity_parser.print_help()
        raise SystemExit(1)
    if args.command == "ui" and getattr(args, "json", False):
        parser.error("ui does not support --json")
    if args.command == "ui":
        if args.ui_command is None:
            args.ui_parser.print_help()
            raise SystemExit(1)
        try:
            action = args.ui_command
            if action == "start":
                start_ui(
                    Path.cwd(),
                    port=args.port,
                    open_browser=not args.no_open,
                )
            elif action == "stop":
                stop_ui(Path.cwd())
            else:
                print_ui_status(Path.cwd())
        except Exception as error:
            print(f"KFlow could not complete 'ui {action}': {error}", file=sys.stderr)
            raise SystemExit(2) from error
        return

    try:
        result = dispatch(args)
    except Exception as error:
        schema_version = (
            MUTATION_SCHEMA_VERSION
            if args.command in {"node", "derivation"}
            else TASK_QUERY_SCHEMA_VERSION
        )
        result = _error_envelope(
            error, _command_references(args), schema_version=schema_version
        )
        if getattr(args, "json", False):
            print(json.dumps(result, ensure_ascii=False, sort_keys=True))
        else:
            print(f"KFlow could not complete the command: {error}", file=sys.stderr)
        raise SystemExit(2) from error

    _print_result(result, getattr(args, "json", False), args)
    if not result.get("ok", True):
        raise SystemExit(2)


def _set_json_error_mode(parser: argparse.ArgumentParser, enabled: bool) -> None:
    if isinstance(parser, KFlowArgumentParser):
        parser.json_error_mode = enabled
    for action in parser._actions:
        if isinstance(action, argparse._SubParsersAction):
            for child in action.choices.values():
                _set_json_error_mode(child, enabled)


def dispatch(args) -> dict:
    """Run one official KFlow command."""
    root = Path.cwd()
    if args.command == "init":
        root = Path(args.path).resolve()
        initialize_project(root)
        return {
            "ok": True,
            "schema_version": TASK_QUERY_SCHEMA_VERSION,
            "root": str(root),
        }
    if args.command == "node" and args.entity_action == "add":
        node = add_node(root, args.name, tuple(args.files))
        return {
            "ok": True,
            "schema_version": MUTATION_SCHEMA_VERSION,
            "node": {"id": node.id, "name": node.name, "files": list(node.files)},
        }
    if args.command == "node" and args.entity_action == "edit":
        node = edit_node(root, args.old_name, name=args.name, files=tuple(args.files))
        return {
            "ok": True,
            "schema_version": MUTATION_SCHEMA_VERSION,
            "previous_name": args.old_name,
            "node": {"id": node.id, "name": node.name, "files": list(node.files)},
        }
    if args.command == "node" and args.entity_action == "remove":
        node = remove_node(root, args.name)
        return {
            "ok": True,
            "schema_version": MUTATION_SCHEMA_VERSION,
            "node": {"id": node.id, "name": node.name, "files": list(node.files)},
        }
    if args.command == "derivation" and args.entity_action == "add":
        derivation = add_derivation(
            root,
            args.name,
            args.short,
            args.detail,
            tuple((node, short, "") for node, short in args.input),
            tuple((node, short, "") for node, short in args.output),
        )
        return {
            "ok": True,
            "schema_version": MUTATION_SCHEMA_VERSION,
            "derivation": present_derivation(load_graph(root), derivation),
        }
    if args.command == "derivation" and args.entity_action == "edit":
        derivation = edit_derivation(
            root,
            args.old_name,
            name=args.name,
            short=args.short,
            detail=args.detail,
            inputs=tuple((node, short, "") for node, short in args.input),
            outputs=tuple((node, short, "") for node, short in args.output),
        )
        return {
            "ok": True,
            "schema_version": MUTATION_SCHEMA_VERSION,
            "previous_name": args.old_name,
            "derivation": present_derivation(load_graph(root), derivation),
        }
    if args.command == "derivation" and args.entity_action == "remove":
        derivation = remove_derivation(root, args.name)
        return {
            "ok": True,
            "schema_version": MUTATION_SCHEMA_VERSION,
            "derivation": present_derivation(load_graph(root), derivation),
        }
    if args.command == "overview":
        return query_project_graph(root)
    if args.command == "context":
        return query_context(root, args.node)
    if args.command == "impact":
        return query_impact(root, args.node)
    if args.command == "review-order":
        return query_review_order(root, args.node)
    if args.command == "confirm":
        before, after = confirm(root, args.node)
        graph = load_graph(root)
        node = graph.nodes[after.node]
        remaining = query_review_order(root)
        return {
            "ok": True,
            "schema_version": TASK_QUERY_SCHEMA_VERSION,
            "node": {"id": node.id, "name": node.name, "files": list(node.files)},
            "before": {"status": before.status, "reasons": list(before.reasons)},
            "after": {"status": after.status, "reasons": list(after.reasons)},
            "next": remaining["nodes"][0] if remaining["nodes"] else None,
            "issues": remaining["issues"],
        }
    if args.command == "validate":
        issues = validate_project(root)
        return {
            "ok": not issues,
            "schema_version": TASK_QUERY_SCHEMA_VERSION,
            "issues": [
                {
                    "code": issue.code,
                    "message": issue.message,
                    "references": list(issue.references),
                }
                for issue in issues
            ],
        }
    raise ValueError(f"unknown command: {args.command}")


def _command_references(args) -> list[str]:
    references: list[str] = []
    node = getattr(args, "node", None)
    if node:
        references.append(node)
    for attribute in ("name", "old_name"):
        value = getattr(args, attribute, None)
        if value:
            references.append(value)
    references.extend(getattr(args, "files", ()) or ())
    for attribute in ("input", "output"):
        references.extend(item[0] for item in (getattr(args, attribute, ()) or ()))
    return references


def _error_envelope(
    error: Exception, references: list[str], *, schema_version: int
) -> dict:
    if isinstance(error, GraphValidationError):
        issues = [
            {
                "code": issue.code,
                "message": issue.message,
                "references": list(issue.references),
            }
            for issue in error.issues
        ]
    else:
        if isinstance(error, StorageError):
            code = "invalid_project"
        elif isinstance(error, KeyError):
            code = "unknown_node"
        elif isinstance(error, OSError):
            code = "io_error"
        elif isinstance(error, (TypeError, ValueError)):
            code = "invalid_argument"
        else:
            code = "internal_error"
        issues = [
            {
                "code": code,
                "message": str(error).strip("'"),
                "references": references,
            }
        ]
    return {
        "ok": False,
        "schema_version": schema_version,
        "issues": issues,
    }


def _print_result(result: dict, json_output: bool, args) -> None:
    if json_output:
        print(json.dumps(result, ensure_ascii=False, sort_keys=True))
        return
    command = args.command
    if command == "validate":
        _print_validation(result)
        return
    if command == "overview" and _can_render_overview(result):
        _print_overview(result, include_status=args.status)
        return
    if not result.get("ok", True):
        print("KFlow could not complete the command:", file=sys.stderr)
        _print_issues(result.get("issues", []), file=sys.stderr)
        return
    if command == "overview":
        _print_overview(result, include_status=args.status)
    elif command == "context":
        _print_context(result)
    elif command == "impact":
        _print_impact(result)
    elif command == "review-order":
        _print_review_order(result)
    elif command == "init":
        print(f"Initialized KFlow at {result['root']}")
    elif command == "node":
        node = result["node"]
        if args.entity_action == "add":
            print(f"Added Node: {node['name']}")
        elif args.entity_action == "edit":
            suffix = (
                node["name"]
                if args.old_name == node["name"]
                else f"{args.old_name} -> {node['name']}"
            )
            print(f"Edited Node: {suffix}")
        else:
            print(f"Removed Node: {node['name']}")
    elif command == "derivation":
        derivation = result["derivation"]
        if args.entity_action == "add":
            print(f"Added Derivation: {derivation['name']}")
        elif args.entity_action == "edit":
            suffix = (
                derivation["name"]
                if args.old_name == derivation["name"]
                else f"{args.old_name} -> {derivation['name']}"
            )
            print(f"Edited Derivation: {suffix}")
        else:
            print(f"Removed Derivation: {derivation['name']}")
    elif command == "confirm":
        _print_confirmation(result)


def _print_overview(result: dict, *, include_status: bool) -> None:
    project = result["project"]
    print(
        f"KFlow project: {project['node_count']} nodes, "
        f"{project['derivation_count']} derivations"
    )
    if include_status:
        if project["status"] == "invalid":
            print("Project status: invalid")
            print("Review status unavailable until validation issues are resolved.")
        else:
            print(f"Need review: {project['needs_review_count']} nodes")

    if result["nodes"]:
        nodes = {node["id"]: node for node in result["nodes"]}
        derivations = _overview_derivations(result)
        for derivation in derivations:
            print()
            _print_derivation(
                derivation,
                descriptor="files",
                nodes=nodes,
                include_status=include_status,
            )

        related = {
            role["node"]
            for derivation in derivations
            for role in (*derivation["inputs"], *derivation["outputs"])
        }
        standalone = [node for node in result["nodes"] if node["id"] not in related]
        if standalone:
            print("\nStandalone nodes\n")
            for node in standalone:
                print(_format_node(node, ", ".join(node["files"]), include_status))
    else:
        print("\nNo knowledge nodes registered.")

    if result["issues"]:
        print("\nValidation issues\n")
        _print_issues(result["issues"])


def _can_render_overview(result: dict) -> bool:
    if result.get("nodes") or result.get("ok", True):
        return True
    return any(
        issue.get("code") != "invalid_project" for issue in result.get("issues", [])
    )


def _overview_derivations(result: dict) -> list[dict]:
    """Project stable machine facts into topological human reading order."""
    positions = {
        node_id: position
        for position, node_id in enumerate(result["topological_order"])
    }

    def role_key(role: dict) -> tuple[int, str]:
        return positions[role["node"]], role["node"]

    def derivation_key(derivation: dict) -> tuple[tuple[int, ...], str]:
        output_positions = tuple(
            sorted(positions[role["node"]] for role in derivation["outputs"])
        )
        return output_positions, derivation["id"]

    return [
        {
            **derivation,
            "inputs": sorted(derivation["inputs"], key=role_key),
            "outputs": sorted(derivation["outputs"], key=role_key),
        }
        for derivation in sorted(result["derivations"], key=derivation_key)
    ]


def _print_context(result: dict) -> None:
    node = result["node"]
    assert node is not None
    print(_format_node(node, None, True))
    print("\nFiles:")
    for path in node["files"]:
        print(f"- {path}")
    print("\nProduced by:")
    producer = result["producing_derivation"]
    if producer is None:
        print("source node")
    else:
        print()
        _print_derivation(
            producer, descriptor="short", nodes=_node_map(result), include_status=True
        )
    print("\nUsed by:")
    consumers = result["consumer_derivations"]
    if not consumers:
        print("no direct derivations")
    for derivation in consumers:
        print()
        _print_derivation(
            derivation, descriptor="short", nodes=_node_map(result), include_status=True
        )


def _print_impact(result: dict) -> None:
    node = result["node"]
    assert node is not None
    print(f"Impact from: {node['name']}")
    derivations = result["direct_derivations"]
    if not derivations:
        print(f"\nNo downstream derivations from {node['name']}.")
        return
    print("\nDirect derivations")
    for derivation in derivations:
        print()
        _print_derivation(
            derivation,
            descriptor="short",
            selected_id=node["id"],
        )
    further = result["further_downstream"]
    if not further:
        print("\nFurther downstream: none")
        return
    print("\nFurther downstream, in topological order\n")
    for position, downstream in enumerate(further, start=1):
        print(f"{position}. {downstream['name']}")


def _print_review_order(result: dict) -> None:
    scope = result["scope"]
    if not result["nodes"]:
        if scope is None:
            print("Review scope is clear.")
        else:
            print(f"No nodes need review from {scope['name']}.")
        return
    if scope is None:
        print("Review order")
    else:
        print(f"Review order from: {scope['name']}")
    for position, node in enumerate(result["nodes"], start=1):
        print(f"\n{position}. {node['name']} — {_reason_text(node['reasons'])}")
        for path in node["files"]:
            print(f"   {path}")


def _print_confirmation(result: dict) -> None:
    print(f"Confirmed: {result['node']['name']}")
    next_node = result["next"]
    if next_node is None:
        print("Current review scope is clear.")
    else:
        print(f"Next: {next_node['name']} — {_reason_text(next_node['reasons'])}")


def _print_validation(result: dict) -> None:
    if result["ok"]:
        print("KFlow metadata is valid.")
        return
    print("KFlow metadata is invalid.\n")
    _print_issues(result["issues"])


def _print_derivation(
    derivation: dict,
    *,
    descriptor: str,
    nodes: dict[str, dict] | None = None,
    include_status: bool = False,
    selected_id: str | None = None,
) -> None:
    nodes = {} if nodes is None else nodes
    inputs = derivation["inputs"]
    outputs = derivation["outputs"]
    input_labels = [
        _format_role(role, descriptor, nodes, include_status, selected_id)
        for role in inputs
    ]
    for label in input_labels:
        print(label)
    print(f"  └─ {derivation['short']}")
    output_labels = [
        _format_role(role, descriptor, nodes, include_status, selected_id)
        for role in outputs
    ]
    if len(output_labels) == 1:
        print(f"     → {output_labels[0]}")
    else:
        for index, label in enumerate(output_labels):
            connector = "└─→" if index == len(output_labels) - 1 else "├─→"
            print(f"     {connector} {label}")


def _format_role(
    role: dict,
    descriptor: str,
    nodes: dict[str, dict],
    include_status: bool,
    selected_id: str | None,
) -> str:
    node = nodes.get(role["node"], {"name": role["name"], "reasons": []})
    value = ", ".join(node.get("files", [])) if descriptor == "files" else role["short"]
    label = _format_node(node, value, include_status)
    if role["node"] == selected_id:
        label += " [selected]"
    return label


def _format_node(node: dict, descriptor: str | None, include_status: bool) -> str:
    label = node["name"]
    if include_status and node.get("reasons"):
        label += f" [{_reason_text(node['reasons'])}]"
    if descriptor:
        label += f" — {descriptor}"
    return label


def _node_map(result: dict) -> dict[str, dict]:
    return {node["id"]: node for node in result["nodes"]}


def _reason_text(reasons: list[str]) -> str:
    return ", ".join(reason.replace("_", " ") for reason in reasons)


def _print_issues(issues: list[dict], *, file=None) -> None:
    output = sys.stdout if file is None else file
    for issue in issues:
        print(f"- {issue['code']}: {_format_issue(issue)}", file=output)


def _format_issue(issue: dict) -> str:
    """Keep graph diagnostics intact while abbreviating path-only file issues."""
    if issue.get("code") in {"missing_file", "unreadable_file"}:
        references = issue.get("references", [])
        if references:
            return references[-1]
    return issue["message"]
