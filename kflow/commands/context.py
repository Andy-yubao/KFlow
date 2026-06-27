"""kflow context — show upstream knowledge context."""
from pathlib import Path
from kflow.store import load_index, require_kflow
from kflow.errors import NodeNotFoundError
from kflow.graph import bfs_upstream


def context_node(root: Path, name: str, depth: int | None = None) -> dict:
    """Get upstream context for a node in topological order."""
    require_kflow(root)
    index = load_index(root)

    node_id = None
    for nid, nd in index.nodes.items():
        if nd.name == name:
            node_id = nid
            break
    if node_id is None:
        raise NodeNotFoundError(name)

    ordered_ids = bfs_upstream(index, node_id, max_depth=depth)
    nodes = []
    for nid in ordered_ids:
        nd = index.nodes.get(nid)
        if nd is None:
            continue
        source = None
        for dv_id in nd.derivations_as_output:
            dv = index.derivations.get(dv_id)
            if dv:
                source = {
                    "derivation_id": dv_id,
                    "summary": dv.summary,
                    "inputs": dv.inputs,
                }
                break
        nodes.append({
            "id": nid, "name": nd.name, "status": nd.status, "file": nd.file,
            "source": source,
        })

    return {"target": node_id, "nodes": nodes}
