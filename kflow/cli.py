"""CLI entry point — argparse definition and command dispatch."""
import argparse
import sys
from pathlib import Path
from kflow.errors import KFlowError, handle_error


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="kflow", description="Knowledge Flow CLI")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    sub = parser.add_subparsers(dest="command")

    # Commands will be registered in subsequent tasks
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
    pass
