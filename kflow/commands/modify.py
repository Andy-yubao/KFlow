"""kflow modify — mark a node as modified, propagate yellow downstream."""
from pathlib import Path
from kflow.store import load_index, save_index, save_node, load_node, require_kflow
from kflow.errors import NodeNotFoundError
from kflow.status import propagate_yellow


def modify_node(root: Path, name: str) -> dict:
    """Mark node as green (modified but confirmed) and all downstream yellow."""
    require_kflow(root)
    index = load_index(root)

    node_id = None
    for nid, nd in index.nodes.items():
        if nd.name == name:
            node_id = nid
            break

    if node_id is None:
        raise NodeNotFoundError(name)

    node = load_node(root, node_id)
    node.status = "green"
    save_node(root, node)
    index.nodes[node_id].status = "green"

    affected = propagate_yellow(index, node_id)

    for affected_id in affected:
        try:
            an = load_node(root, affected_id)
            an.status = "yellow"
            save_node(root, an)
        except FileNotFoundError:
            pass

    save_index(root, index)

    return {
        "ok": True,
        "node": {"id": node_id, "name": name, "status": "green", "file": index.nodes[node_id].file},
        "affected": list(affected),
    }
