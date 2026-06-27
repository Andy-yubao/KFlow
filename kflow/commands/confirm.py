"""kflow confirm — confirm node is valid, optionally cascade green downstream."""
from pathlib import Path
from kflow.store import load_index, save_index, save_node, load_node, require_kflow
from kflow.errors import NodeNotFoundError
from kflow.status import propagate_green_cascade


def confirm_node(root: Path, name: str, cascade: bool = False) -> dict:
    """Confirm a node. If cascade, propagate green downstream."""
    require_kflow(root)
    index = load_index(root)

    node_id = None
    for nid, nd in index.nodes.items():
        if nd.name == name:
            node_id = nid
            break

    if node_id is None:
        raise NodeNotFoundError(name)

    if cascade:
        affected = propagate_green_cascade(index, node_id)
    else:
        node = load_node(root, node_id)
        node.status = "green"
        save_node(root, node)
        index.nodes[node_id].status = "green"
        affected = {node_id}

    for affected_id in affected:
        if affected_id == node_id and not cascade:
            continue
        try:
            an = load_node(root, affected_id)
            an.status = "green"
            save_node(root, an)
        except FileNotFoundError:
            pass

    save_index(root, index)

    return {
        "ok": True,
        "node": {"id": node_id, "name": name, "status": "green", "file": index.nodes[node_id].file},
        "affected": list(affected - {node_id}),
    }
