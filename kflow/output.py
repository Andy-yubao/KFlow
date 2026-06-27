"""Output formatting — human-readable and JSON modes."""
import json
import sys

# Ensure UTF-8 output on all platforms, especially Windows
try:
    sys.stdout.reconfigure(encoding='utf-8')
except Exception:
    pass


def print_result(data: dict, json_output: bool = False) -> None:
    if json_output:
        print(json.dumps(data, indent=2, ensure_ascii=False))
    else:
        _print_human(data)


def print_list(data: list, json_output: bool = False) -> None:
    if json_output:
        print(json.dumps(data, indent=2, ensure_ascii=False))
    else:
        for item in data:
            if isinstance(item, dict):
                _print_node_line(item)
            else:
                print(item)


def print_context(data: dict, json_output: bool = False) -> None:
    if json_output:
        print(json.dumps(data, indent=2, ensure_ascii=False))
    else:
        target_name = data['nodes'][-1]['name'] if data['nodes'] else data['target']
        print(f"\n## Context for: {target_name}\n")
        for n in data["nodes"]:
            status_icon = {"green": "🟢", "yellow": "🟡", "red": "🔴"}.get(n["status"], "")
            file_info = f"  {n['file']}" if n.get("file") else ""
            source_info = ""
            if n.get("source"):
                src = n["source"]
                roles = ", ".join(f"{i['node']}({i['role']})" for i in src.get("inputs", []))
                source_info = f"\n  来源: {src['summary']} — 由 {roles} 组合生成"
            else:
                source_info = "\n  来源: (source node)"
            print(f"### {n['name']} [{n['status']}] {status_icon}{file_info}{source_info}\n")


def print_affect(data: dict, json_output: bool = False) -> None:
    if json_output:
        print(json.dumps(data, indent=2, ensure_ascii=False))
    else:
        for n in sorted(data["nodes"], key=lambda x: x["depth"]):
            status_icon = {"green": "🟢", "yellow": "🟡", "red": "🔴"}.get(n["status"], "")
            indent = "  " * n["depth"]
            print(f"{indent}{n['name']} [{n['status']}] {status_icon}")


def print_query(data: dict, json_output: bool = False) -> None:
    if json_output:
        print(json.dumps(data, indent=2, ensure_ascii=False))
    else:
        if data["nodes"]:
            print(f"\n## Nodes ({len(data['nodes'])})")
            for n in data["nodes"]:
                status_icon = {"green": "🟢", "yellow": "🟡", "red": "🔴"}.get(n["status"], "")
                file_info = f"  {n['file']}" if n.get("file") else ""
                print(f"  {n['name']}  {file_info}  [{n['status']}] {status_icon}")
        if data["derivations"]:
            print(f"\n## Derivations ({len(data['derivations'])})")
            for dv in data["derivations"]:
                inputs_str = ", ".join(dv["inputs"])
                print(f"  {dv['summary']} ({dv['id']})")
                print(f"    {inputs_str} → {dv['output']}")


def print_validate(data: dict, json_output: bool = False) -> None:
    if json_output:
        print(json.dumps(data, indent=2, ensure_ascii=False))
    else:
        if not data["issues"]:
            print("✓ All checks passed.")
            return
        errors = [i for i in data["issues"] if i["severity"] == "error"]
        warnings = [i for i in data["issues"] if i["severity"] == "warning"]
        if errors:
            print(f"\n## Errors ({len(errors)})")
            for e in errors:
                print(f"  ✗ [{e['check']}] {e['message']}")
        if warnings:
            print(f"\n## Warnings ({len(warnings)})")
            for w in warnings:
                print(f"  ⚠ [{w['check']}] {w['message']}")


def _print_human(data: dict) -> None:
    if "node" in data and "ok" in data:
        node = data["node"]
        affected = data.get("affected", [])
        status_icon = {"green": "🟢", "yellow": "🟡", "red": "🔴"}.get(node.get("status", ""), "")
        print(f"{node['name']} ({node['id']}) {status_icon}")
        if affected:
            print(f"  Affected: {', '.join(affected)}")
    elif "issues" in data:
        print_validate(data, json_output=False)
    elif "q" in data:
        print_query(data, json_output=False)


def _print_node_line(item: dict) -> None:
    status_icon = {"green": "🟢", "yellow": "🟡", "red": "🔴"}.get(item.get("status", ""), "")
    file_info = f"  {item['file']}" if item.get("file") else ""
    print(f"{item['name']}  [{item['status']}] {status_icon}{file_info}")
