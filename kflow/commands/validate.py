"""kflow validate — run 6 integrity checks, report-only."""
from pathlib import Path
from kflow.store import load_index, require_kflow
from kflow.graph import has_cycle


def validate_project(root: Path) -> dict:
    require_kflow(root)
    index = load_index(root)
    issues = []

    # Check 1: orphan nodes
    for nid, nd in index.nodes.items():
        if not nd.derivations_as_input and not nd.derivations_as_output:
            issues.append({
                "check": "orphan_node", "severity": "warning",
                "message": f"Node '{nd.name}' ({nid}) has no input or output derivations.",
            })

    # Check 2: dangling references
    for nid, nd in index.nodes.items():
        for dv_id in nd.derivations_as_input:
            if dv_id not in index.derivations:
                issues.append({
                    "check": "dangling_reference", "severity": "error",
                    "message": f"Node '{nd.name}' ({nid}) references missing derivation {dv_id}.",
                })
        for dv_id in nd.derivations_as_output:
            if dv_id not in index.derivations:
                issues.append({
                    "check": "dangling_reference", "severity": "error",
                    "message": f"Node '{nd.name}' ({nid}) references missing derivation {dv_id}.",
                })
    for did, dv in index.derivations.items():
        for inp in dv.inputs:
            if inp["node"] not in index.nodes:
                issues.append({
                    "check": "dangling_reference", "severity": "error",
                    "message": f"Derivation '{dv.summary}' ({did}) references missing node {inp['node']}.",
                })
        if dv.output["node"] not in index.nodes:
            issues.append({
                "check": "dangling_reference", "severity": "error",
                "message": f"Derivation '{dv.summary}' ({did}) output node {dv.output['node']} not found.",
            })

    # Check 3: cycle detection
    if has_cycle(index):
        issues.append({
            "check": "cycle", "severity": "error",
            "message": "DAG contains one or more cycles.",
        })

    # Check 4: index vs individual files consistency
    nodes_dir = root / ".kflow" / "nodes"
    deriv_dir = root / ".kflow" / "derivations"
    node_files = set(f.stem for f in nodes_dir.glob("*.json")) if nodes_dir.is_dir() else set()
    deriv_files = set(f.stem for f in deriv_dir.glob("*.json")) if deriv_dir.is_dir() else set()
    if node_files != set(index.nodes.keys()):
        issues.append({
            "check": "index_inconsistency", "severity": "error",
            "message": "index.json node list does not match nodes/ directory. Run 'kflow reindex'.",
        })
    if deriv_files != set(index.derivations.keys()):
        issues.append({
            "check": "index_inconsistency", "severity": "error",
            "message": "index.json derivation list does not match derivations/ directory. Run 'kflow reindex'.",
        })

    # Check 5: missing .md files
    for nid, nd in index.nodes.items():
        if nd.file:
            md_path = root / nd.file
            if not md_path.exists():
                issues.append({
                    "check": "missing_markdown", "severity": "error",
                    "message": f"Node '{nd.name}' ({nid}) references missing file: {nd.file}",
                })

    # Check 6: unregistered .md files
    knowledge_dir = root / "knowledge"
    if knowledge_dir.is_dir():
        registered_files = {nd.file for nd in index.nodes.values() if nd.file}
        for md_file in knowledge_dir.glob("*.md"):
            rel_path = str(md_file.relative_to(root))
            if rel_path not in registered_files:
                issues.append({
                    "check": "unregistered_markdown", "severity": "warning",
                    "message": f"File '{rel_path}' is not registered to any node.",
                })

    return {"ok": True, "issues": issues}
