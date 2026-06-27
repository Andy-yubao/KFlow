"""kflow list — flat list of all nodes."""
from pathlib import Path
from kflow.store import load_index


def list_nodes(root: Path) -> list[dict]:
    """Return a flat list of all nodes with name, id, status, file."""
    index = load_index(root)
    result = []
    for nid, node in index.nodes.items():
        result.append({
            "id": nid,
            "name": node.name,
            "status": node.status,
            "file": node.file,
        })
    result.sort(key=lambda x: x["name"])
    return result
