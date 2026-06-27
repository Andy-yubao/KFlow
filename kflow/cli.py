"""CLI entry point — argparse definition and command dispatch."""
import argparse
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
from kflow.output import print_result, print_list


class DeriveInputAction(argparse.Action):
    def __call__(self, parser, namespace, values, option_string=None):
        inputs = getattr(namespace, 'derive_inputs', []) or []
        cur = getattr(namespace, '_derive_cur', None)
        if cur:
            inputs.append(cur)
        namespace._derive_cur = {"node": values}
        namespace.derive_inputs = inputs


class DeriveRoleAction(argparse.Action):
    def __call__(self, parser, namespace, values, option_string=None):
        cur = getattr(namespace, '_derive_cur', None)
        if cur is None:
            parser.error("--role must follow --input")
        cur["role"] = values


class DeriveRoleDetailAction(argparse.Action):
    def __call__(self, parser, namespace, values, option_string=None):
        cur = getattr(namespace, '_derive_cur', None)
        if cur is None:
            parser.error("--role-detail must follow --input")
        cur["role_detail"] = values


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="kflow", description="Knowledge Flow CLI")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    sub = parser.add_subparsers(dest="command")

    p_init = sub.add_parser("init", help="Initialize a KFlow project")
    p_init.add_argument("path", nargs="?", default=".", help="Project path (default: .)")

    p_create = sub.add_parser("create", help="Create a source knowledge node")
    p_create.add_argument("name", help="Node name (corresponds to knowledge/<name>.md)")
    p_create.add_argument("--no-file", action="store_true", help="Create without a markdown file")

    p_list = sub.add_parser("list", help="List all knowledge nodes")

    p_query = sub.add_parser("query", help="Search nodes and derivations")
    p_query.add_argument("word", help="Search term")

    p_derive = sub.add_parser("derive", help="Create a derivation linking input nodes to output node")
    p_derive.add_argument("--input", action=DeriveInputAction, dest="derive_inputs", default=[])
    p_derive.add_argument("--role", action=DeriveRoleAction)
    p_derive.add_argument("--role-detail", action=DeriveRoleDetailAction)
    p_derive.add_argument("--output", dest="derive_output_name")
    p_derive.add_argument("--method", dest="derive_method")
    p_derive.add_argument("--method-detail", dest="derive_method_detail")
    p_derive.add_argument("--summary", dest="derive_summary")

    p_modify = sub.add_parser("modify", help="Mark node as modified, downstream goes yellow")
    p_modify.add_argument("name", help="Node name")

    p_confirm = sub.add_parser("confirm", help="Confirm node validity, optionally cascade")
    p_confirm.add_argument("name")
    p_confirm.add_argument("--cascade", action="store_true")

    p_remove = sub.add_parser("remove", help="Remove a node")
    p_remove.add_argument("name")
    p_remove.add_argument("--force", action="store_true")
    p_remove.add_argument("--keep-file", action="store_true")

    p_context = sub.add_parser("context", help="Show upstream knowledge context")
    p_context.add_argument("name")
    p_context.add_argument("--depth", type=int, default=None)

    p_affect = sub.add_parser("affect", help="Show downstream impact")
    p_affect.add_argument("name")
    p_affect.add_argument("--depth", type=int, default=None)

    p_validate = sub.add_parser("validate", help="Run integrity checks")

    p_reindex = sub.add_parser("reindex", help="Rebuild index.json from individual files")

    return parser


def main():
    parser = build_parser()
    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    try:
        dispatch(args)
    except KFlowError as e:
        handle_error(e, json_output=getattr(args, 'json', False))
    except Exception as e:
        if getattr(args, 'json', False):
            import json as _json
            print(_json.dumps({"ok": False, "error": str(e), "type": "UnexpectedError"}))
        else:
            print(f"Error: {e}", file=sys.stderr)
        sys.exit(2)


def dispatch(args):
    """Route to the appropriate command handler."""
    if args.command == "init":
        path = Path(args.path).resolve()
        init_project(path)
        print(f"Initialized KFlow project at {path}")
    elif args.command == "create":
        result = create_node(Path.cwd(), args.name, no_file=args.no_file)
        print_result(result, json_output=getattr(args, 'json', False))
    elif args.command == "list":
        result = list_nodes(Path.cwd())
        print_list(result, json_output=getattr(args, 'json', False))
    elif args.command == "query":
        result = query_kflow(Path.cwd(), args.word)
        from kflow.output import print_result as pr
        pr(result, json_output=getattr(args, 'json', False))
    elif args.command == "derive":
        cur = getattr(args, '_derive_cur', None)
        if cur:
            args.derive_inputs.append(cur)
        result = derive_node(
            Path.cwd(),
            inputs=args.derive_inputs,
            output={"name": args.derive_output_name, "method": args.derive_method,
                    "method_detail": args.derive_method_detail or ""},
            summary=args.derive_summary,
        )
        print_result(result, json_output=getattr(args, 'json', False))
    elif args.command == "modify":
        result = modify_node(Path.cwd(), args.name)
        print_result(result, json_output=getattr(args, 'json', False))
    elif args.command == "confirm":
        result = confirm_node(Path.cwd(), args.name, cascade=getattr(args, 'cascade', False))
        print_result(result, json_output=getattr(args, 'json', False))
    elif args.command == "remove":
        result = remove_node(Path.cwd(), args.name, force=getattr(args, 'force', False),
                             keep_file=getattr(args, 'keep_file', False))
        print_result(result, json_output=getattr(args, 'json', False))
    elif args.command == "context":
        result = context_node(Path.cwd(), args.name, depth=args.depth)
        print_result(result, json_output=getattr(args, 'json', False))
    elif args.command == "affect":
        result = affect_node(Path.cwd(), args.name, depth=args.depth)
        print_result(result, json_output=getattr(args, 'json', False))
    elif args.command == "validate":
        result = validate_project(Path.cwd())
        print_result(result, json_output=getattr(args, 'json', False))
    elif args.command == "reindex":
        result = reindex_project(Path.cwd())
        print_result(result, json_output=getattr(args, 'json', False))
