"""kflow query — full-text search across nodes and derivations."""
from pathlib import Path
from kflow.store import load_index


def query_kflow(root: Path, word: str) -> dict:
    """Search word in node names, derivation summaries, input roles, output methods."""
    index = load_index(root)
    matched_nodes = []
    matched_derivations = []

    for nid, node in index.nodes.items():
        if word in node.name:
            matched_nodes.append({
                "id": nid, "name": node.name, "status": node.status, "file": node.file,
            })

    for did, dv in index.derivations.items():
        matched = word in dv.summary
        if not matched:
            for inp in dv.inputs:
                if word in inp.get("role", ""):
                    matched = True
                    break
        if not matched:
            if word in dv.output.get("method", ""):
                matched = True
        if matched:
            matched_derivations.append({
                "id": did,
                "summary": dv.summary,
                "inputs": [inp["node"] for inp in dv.inputs],
                "output": dv.output["node"],
            })

    return {"q": word, "nodes": matched_nodes, "derivations": matched_derivations}
