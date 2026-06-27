"""CLI entry point — argparse definition and command dispatch."""
import argparse
import sys
from pathlib import Path
from kflow.errors import KFlowError, handle_error
from kflow.commands.init import init_project
from kflow.commands.create import create_node
from kflow.commands.list_cmd import list_nodes
from kflow.commands.query import query_kflow
from kflow.output import print_result, print_list


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
