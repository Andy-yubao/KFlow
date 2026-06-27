"""kflow affect — show downstream impact."""
from pathlib import Path
from kflow.store import load_index, require_kflow
from kflow.errors import NodeNotFoundError
from kflow.graph import bfs_downstream


def affect_node(root: Path, name: str, depth: int | None = None) -> dict:
    require_kflow(root)
    index = load_index(root)

    node_id = None
    for nid, nd in index.nodes.items():
        if nd.name == name:
            node_id = nid
            break
    if node_id is None:
        raise NodeNotFoundError(name)

    downstream = bfs_downstream(index, node_id, max_depth=depth)
    nodes = []
    for nid, d in sorted(downstream.items(), key=lambda x: x[1]):
        nd = index.nodes.get(nid)
        if nd:
            nodes.append({"id": nid, "name": nd.name, "status": nd.status, "depth": d})

    return {"target": node_id, "nodes": nodes}
