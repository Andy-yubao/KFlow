"""Output formatting — human-readable and JSON modes."""
import json
import sys


def print_result(data: dict, json_output: bool = False) -> None:
    """Print command result. In JSON mode, dump raw. Otherwise print formatted."""
    if json_output:
        print(json.dumps(data, indent=2, ensure_ascii=False))
    else:
        _print_human(data)


def print_list(data: list, json_output: bool = False) -> None:
    """Print list results."""
    if json_output:
        print(json.dumps(data, indent=2, ensure_ascii=False))
    else:
        for item in data:
            print(item)


def _print_human(data: dict) -> None:
    """Human-readable output dispatch based on data keys."""
    if "ok" in data and "node" in data:
        node = data["node"]
        affected = data.get("affected", [])
        status_icon = {"green": "🟢", "yellow": "🟡", "red": "🔴"}.get(node["status"], "")
        print(f"Created node '{node['name']}' ({node['id']}) {status_icon}")
        if affected:
            print(f"  Affected: {', '.join(affected)}")
