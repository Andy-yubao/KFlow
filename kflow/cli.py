"""CLI entry point — argparse definition and command dispatch."""

import argparse
import json
import sys
from pathlib import Path
from kflow.errors import KFlowError, handle_error
from kflow.commands.init import init_project
from kflow.commands.create import create_node
from kflow.commands.list_cmd import list_nodes
from kflow.commands.query import query_kflow
from kflow.commands.derive import derive_node
from kflow.commands.modify import modify_node
from kflow.commands.confirm import confirm_node
from kflow.commands.remove import remove_node
from kflow.commands.context import context_node
from kflow.commands.affect import affect_node
from kflow.commands.validate import validate_project
from kflow.commands.reindex import reindex_project
from kflow.output import (
    print_result,
    print_list,
    print_context,
    print_affect,
    print_query,
    print_validate,
)
from kflow.v2.operations import add_derivation as add_v2_derivation
from kflow.v2.operations import add_node as add_v2_node
from kflow.v2.scan import confirm as confirm_v2_node
from kflow.v2.scan import scan as scan_v2_project
from kflow.v2.scan import validate as validate_v2_project
from kflow.v2.storage import initialize_project as initialize_v2_project


class DeriveInputAction(argparse.Action):
    def __call__(self, parser, namespace, values, option_string=None):
        inputs = getattr(namespace, "derive_inputs", []) or []
        cur = getattr(namespace, "_derive_cur", None)
        if cur:
            inputs.append(cur)
        namespace._derive_cur = {"node": values}
        namespace.derive_inputs = inputs


class DeriveRoleAction(argparse.Action):
    def __call__(self, parser, namespace, values, option_string=None):
        cur = getattr(namespace, "_derive_cur", None)
        if cur is None:
            parser.error("--role must follow --input")
        cur["role"] = values


class DeriveRoleDetailAction(argparse.Action):
    def __call__(self, parser, namespace, values, option_string=None):
        cur = getattr(namespace, "_derive_cur", None)
        if cur is None:
            parser.error("--role-detail must follow --input")
        cur["role_detail"] = values


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="kflow", description="Knowledge Flow CLI")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    sub = parser.add_subparsers(dest="command")

    p_init = sub.add_parser("init", help="Initialize KFlow metadata")
    p_init.add_argument(
        "path", nargs="?", default=".", help="Project path (default: .)"
    )
    p_init.add_argument("--json", action="store_true", help="Output as JSON")

    p_add = sub.add_parser("add-node", help="Register existing files as a Node")
    p_add.add_argument("name")
    p_add.add_argument("--file", action="append", required=True, dest="files")
    p_add.add_argument("--json", action="store_true", help="Output as JSON")

    p_derive = sub.add_parser("derive", help="Connect existing Nodes")
    p_derive.add_argument("--short", required=True)
    p_derive.add_argument("--detail", default="")
    p_derive.add_argument(
        "--input", nargs=2, action="append", required=True, metavar=("NODE", "SHORT")
    )
    p_derive.add_argument(
        "--output", nargs=2, action="append", required=True, metavar=("NODE", "SHORT")
    )
    p_derive.add_argument("--json", action="store_true", help="Output as JSON")

    p_status = sub.add_parser("status", help="Scan current impact status")
    p_status.add_argument("--json", action="store_true", help="Output as JSON")

    p_confirm = sub.add_parser("confirm", help="Confirm exactly one Node")
    p_confirm.add_argument("node")
    p_confirm.add_argument("--json", action="store_true", help="Output as JSON")

    p_validate = sub.add_parser("validate", help="Validate KFlow facts")
    p_validate.add_argument("--json", action="store_true", help="Output as JSON")

    p_legacy = sub.add_parser("legacy", help="Use the legacy v1 command interface")
    legacy_sub = p_legacy.add_subparsers(dest="legacy_command", required=True)
    _add_legacy_parsers(legacy_sub)

    return parser


def _add_legacy_parsers(sub) -> None:
    p_init = sub.add_parser("init", help="[legacy] Initialize a v1 project")
    p_init.add_argument("path", nargs="?", default=".")
    p_init.add_argument("--json", action="store_true", help="Output as JSON")

    p_create = sub.add_parser("create", help="[legacy] Create a source node")
    p_create.add_argument("name", help="Node name (corresponds to knowledge/<name>.md)")
    p_create.add_argument(
        "--no-file", action="store_true", help="Create without a markdown file"
    )
    p_create.add_argument("--json", action="store_true", help="Output as JSON")

    p_list = sub.add_parser("list", help="[legacy] List all nodes")
    p_list.add_argument("--json", action="store_true", help="Output as JSON")

    p_query = sub.add_parser("query", help="[legacy] Search nodes and derivations")
    p_query.add_argument("word", help="Search term")
    p_query.add_argument("--json", action="store_true", help="Output as JSON")

    p_derive = sub.add_parser("derive", help="[legacy] Create a v1 derivation")
    p_derive.add_argument(
        "--input", action=DeriveInputAction, dest="derive_inputs", default=[]
    )
    p_derive.add_argument("--role", action=DeriveRoleAction)
    p_derive.add_argument("--role-detail", action=DeriveRoleDetailAction)
    p_derive.add_argument("--output", dest="derive_output_name")
    p_derive.add_argument("--method", dest="derive_method")
    p_derive.add_argument("--method-detail", dest="derive_method_detail")
    p_derive.add_argument("--summary", dest="derive_summary")
    p_derive.add_argument("--json", action="store_true", help="Output as JSON")

    p_modify = sub.add_parser("modify", help="[legacy] Mark a node as modified")
    p_modify.add_argument("name", help="Node name")
    p_modify.add_argument("--json", action="store_true", help="Output as JSON")

    p_confirm = sub.add_parser("confirm", help="[legacy] Confirm a v1 node")
    p_confirm.add_argument("name")
    p_confirm.add_argument("--cascade", action="store_true")
    p_confirm.add_argument("--json", action="store_true", help="Output as JSON")

    p_remove = sub.add_parser("remove", help="[legacy] Remove a node")
    p_remove.add_argument("name")
    p_remove.add_argument("--force", action="store_true")
    p_remove.add_argument("--keep-file", action="store_true")
    p_remove.add_argument("--json", action="store_true", help="Output as JSON")

    p_context = sub.add_parser("context", help="[legacy] Show upstream context")
    p_context.add_argument("name")
    p_context.add_argument("--depth", type=int, default=None)
    p_context.add_argument("--json", action="store_true", help="Output as JSON")

    p_affect = sub.add_parser("affect", help="[legacy] Show downstream impact")
    p_affect.add_argument("name")
    p_affect.add_argument("--depth", type=int, default=None)
    p_affect.add_argument("--json", action="store_true", help="Output as JSON")

    p_validate = sub.add_parser("validate", help="[legacy] Run v1 integrity checks")
    p_validate.add_argument("--json", action="store_true", help="Output as JSON")

    p_reindex = sub.add_parser("reindex", help="[legacy] Rebuild the v1 index")
    p_reindex.add_argument("--json", action="store_true", help="Output as JSON")


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)

    if not args.command:
        parser.print_help()
        sys.exit(1)

    try:
        dispatch(args)
    except KFlowError as e:
        handle_error(e, json_output=getattr(args, "json", False))
    except Exception as e:
        if getattr(args, "json", False):
            import json as _json

            print(
                _json.dumps({"ok": False, "error": str(e), "type": "UnexpectedError"})
            )
        else:
            print(f"Error: {e}", file=sys.stderr)
        sys.exit(2)


def dispatch(args):
    """Route to the appropriate command handler."""
    if args.command == "legacy":
        dispatch_legacy(args)
    else:
        dispatch_current(args)


def dispatch_legacy(args):
    """Route explicitly requested legacy v1 commands."""
    if args.legacy_command == "init":
        path = Path(args.path).resolve()
        init_project(path)
        print(f"Initialized KFlow project at {path}")
    elif args.legacy_command == "create":
        result = create_node(Path.cwd(), args.name, no_file=args.no_file)
        print_result(result, json_output=getattr(args, "json", False))
    elif args.legacy_command == "list":
        result = list_nodes(Path.cwd())
        print_list(result, json_output=getattr(args, "json", False))
    elif args.legacy_command == "query":
        result = query_kflow(Path.cwd(), args.word)
        print_query(result, json_output=getattr(args, "json", False))
    elif args.legacy_command == "derive":
        cur = getattr(args, "_derive_cur", None)
        if cur:
            args.derive_inputs.append(cur)
        result = derive_node(
            Path.cwd(),
            inputs=args.derive_inputs,
            output={
                "name": args.derive_output_name,
                "method": args.derive_method,
                "method_detail": args.derive_method_detail or "",
            },
            summary=args.derive_summary,
        )
        print_result(result, json_output=getattr(args, "json", False))
    elif args.legacy_command == "modify":
        result = modify_node(Path.cwd(), args.name)
        print_result(result, json_output=getattr(args, "json", False))
    elif args.legacy_command == "confirm":
        result = confirm_node(
            Path.cwd(), args.name, cascade=getattr(args, "cascade", False)
        )
        print_result(result, json_output=getattr(args, "json", False))
    elif args.legacy_command == "remove":
        result = remove_node(
            Path.cwd(),
            args.name,
            force=getattr(args, "force", False),
            keep_file=getattr(args, "keep_file", False),
        )
        print_result(result, json_output=getattr(args, "json", False))
    elif args.legacy_command == "context":
        result = context_node(Path.cwd(), args.name, depth=args.depth)
        print_context(result, json_output=getattr(args, "json", False))
    elif args.legacy_command == "affect":
        result = affect_node(Path.cwd(), args.name, depth=args.depth)
        print_affect(result, json_output=getattr(args, "json", False))
    elif args.legacy_command == "validate":
        result = validate_project(Path.cwd())
        print_validate(result, json_output=getattr(args, "json", False))
    elif args.legacy_command == "reindex":
        result = reindex_project(Path.cwd())
        print_result(result, json_output=getattr(args, "json", False))
    else:
        raise ValueError(f"unknown legacy command: {args.legacy_command}")


def dispatch_current(args):
    """Route the default schema-v2 command interface."""
    root = Path.cwd()
    if args.command == "init":
        root = Path(args.path).resolve()
        initialize_v2_project(root)
        result = {"ok": True, "schema_version": 2, "root": str(root)}
    elif args.command == "add-node":
        node = add_v2_node(root, args.name, tuple(args.files))
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
        derivation = add_v2_derivation(
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
        result = _v2_status_result(root)
    elif args.command == "confirm":
        before, after = confirm_v2_node(root, args.node)
        current = _v2_status_result(root)
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
        issues = validate_v2_project(root)
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
    else:
        raise ValueError(f"unknown command: {args.command}")
    _print_v2(result, getattr(args, "json", False))


def _v2_status_result(root: Path) -> dict:
    scanned = scan_v2_project(root)
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


def _print_v2(result: dict, json_output: bool) -> None:
    if json_output:
        print(json.dumps(result, ensure_ascii=False, sort_keys=True))
        return
    if "nodes" in result:
        for node in result["nodes"]:
            reasons = ", ".join(node["reasons"]) or "none"
            print(f"{node['name']}: {node['status']} ({reasons})")
        return
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
