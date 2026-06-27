"""kflow remove — delete a node, optionally cascading red downstream."""
from pathlib import Path
from kflow.store import load_index, save_index, load_node, save_node, require_kflow
from kflow.errors import NodeNotFoundError, DerivationBlockedError
from kflow.status import propagate_red


def remove_node(root: Path, name: str, force: bool = False, keep_file: bool = False) -> dict:
    """Remove a node. With --force, deletes associated derivations and marks downstream red."""
    require_kflow(root)
    index = load_index(root)

    node_id = None
    for nid, nd in index.nodes.items():
        if nd.name == name:
            node_id = nid
            break

    if node_id is None:
        raise NodeNotFoundError(name)

    node = index.nodes[node_id]
    affected = set()

    downstream_names = []
    for dv_id in node.derivations_as_input:
        dv = index.derivations.get(dv_id)
        if dv:
            out_id = dv.output["node"]
            out_node = index.nodes.get(out_id)
            if out_node:
                downstream_names.append(out_node.name)

    if downstream_names and not force:
        raise DerivationBlockedError(name, downstream_names)

    if force:
        for dv_id in list(node.derivations_as_output):
            dv = index.derivations.get(dv_id)
            if dv:
                for inp in dv.inputs:
                    inp_node = index.nodes.get(inp["node"])
                    if inp_node and dv_id in inp_node.derivations_as_input:
                        inp_node.derivations_as_input = [
                            x for x in inp_node.derivations_as_input if x != dv_id
                        ]
                        try:
                            fn = load_node(root, inp["node"])
                            fn.derivations_as_input = [
                                x for x in fn.derivations_as_input if x != dv_id
                            ]
                            save_node(root, fn)
                        except FileNotFoundError:
                            pass
            if dv_id in index.derivations:
                del index.derivations[dv_id]
            dv_file = root / ".kflow" / "derivations" / f"{dv_id}.json"
            if dv_file.exists():
                dv_file.unlink()

        for dv_id in list(node.derivations_as_input):
            dv = index.derivations.get(dv_id)
            if dv:
                out_id = dv.output["node"]
                red_affected = propagate_red(index, out_id)
                affected.update(red_affected)
                for ra_id in red_affected:
                    try:
                        fn = load_node(root, ra_id)
                        fn.status = "red"
                        save_node(root, fn)
                    except FileNotFoundError:
                        pass
            dv_file = root / ".kflow" / "derivations" / f"{dv_id}.json"
            if dv_file.exists():
                dv_file.unlink()
            if dv_id in index.derivations:
                del index.derivations[dv_id]

    node_file = root / ".kflow" / "nodes" / f"{node_id}.json"
    if node_file.exists():
        node_file.unlink()

    if not keep_file and node.file:
        md_path = root / node.file
        if md_path.exists():
            md_path.unlink()

    if node_id in index.nodes:
        del index.nodes[node_id]

    save_index(root, index)

    return {
        "ok": True,
        "node": {"id": node_id, "name": name, "status": "removed", "file": node.file},
        "affected": list(affected),
    }
