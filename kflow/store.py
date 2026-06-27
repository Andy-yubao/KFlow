"""File I/O layer — read/write node files, derivation files, and atomic index."""
import json
import os
from dataclasses import asdict
from pathlib import Path
from kflow.models import Node, Derivation, InputSpec, OutputSpec, Index, IndexNode, IndexDerivation
from kflow.errors import ProjectNotInitError

KFLOW_DIR = ".kflow"
INDEX_TMP = ".index.tmp"
INDEX_FILE = "index.json"


def project_root_has_kflow(path: Path) -> bool:
    """Check if path contains a .kflow/ directory."""
    return (path / KFLOW_DIR).is_dir()


def require_kflow(path: Path) -> Path:
    """Return .kflow path or raise ProjectNotInitError."""
    kf = path / KFLOW_DIR
    if not kf.is_dir():
        raise ProjectNotInitError()
    return kf


def write_atomic(dest: Path, data: dict) -> None:
    """Write JSON data atomically via temp file + os.replace."""
    tmp = dest.parent / INDEX_TMP
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    os.replace(tmp, dest)


def load_index(root: Path) -> Index:
    """Load index.json. Auto-reindex if missing or corrupt."""
    idx_path = root / KFLOW_DIR / INDEX_FILE
    # Clean up stale temp file
    tmp_path = root / KFLOW_DIR / INDEX_TMP
    if tmp_path.exists():
        tmp_path.unlink()

    if idx_path.exists():
        try:
            with open(idx_path, encoding="utf-8") as f:
                data = json.load(f)
            return _dict_to_index(data)
        except (json.JSONDecodeError, KeyError):
            pass  # corrupt — fall through to reindex

    return _reindex_and_save(root)


def save_index(root: Path, index: Index) -> None:
    """Atomically write index to index.json."""
    data = _index_to_dict(index)
    idx_path = root / KFLOW_DIR / INDEX_FILE
    write_atomic(idx_path, data)


def save_node(root: Path, node: Node) -> None:
    """Write node to .kflow/nodes/<id>.json."""
    nodes_dir = root / KFLOW_DIR / "nodes"
    nodes_dir.mkdir(parents=True, exist_ok=True)
    with open(nodes_dir / f"{node.id}.json", "w", encoding="utf-8") as f:
        json.dump(asdict(node), f, indent=2, ensure_ascii=False)


def load_node(root: Path, node_id: str) -> Node:
    """Load a node from .kflow/nodes/<id>.json."""
    path = root / KFLOW_DIR / "nodes" / f"{node_id}.json"
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    return Node(**data)


def save_derivation(root: Path, derivation: Derivation) -> None:
    """Write derivation to .kflow/derivations/<id>.json."""
    deriv_dir = root / KFLOW_DIR / "derivations"
    deriv_dir.mkdir(parents=True, exist_ok=True)
    with open(deriv_dir / f"{derivation.id}.json", "w", encoding="utf-8") as f:
        json.dump(asdict(derivation), f, indent=2, ensure_ascii=False)


def load_derivation(root: Path, derivation_id: str) -> Derivation:
    """Load a derivation from .kflow/derivations/<id>.json."""
    path = root / KFLOW_DIR / "derivations" / f"{derivation_id}.json"
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    inputs = [InputSpec(**i) for i in data["inputs"]]
    output = OutputSpec(**data["output"])
    return Derivation(id=data["id"], summary=data["summary"], inputs=inputs, output=output)


def reindex(root: Path) -> dict:
    """Rebuild index.json from individual node and derivation files. Returns counts."""
    idx = _reindex_and_save(root)
    return {"node_count": len(idx.nodes), "derivation_count": len(idx.derivations)}


def _reindex_and_save(root: Path) -> Index:
    """Scan nodes/ and derivations/, build index, save, and return."""
    idx = Index(nodes={}, derivations={})
    nodes_dir = root / KFLOW_DIR / "nodes"
    deriv_dir = root / KFLOW_DIR / "derivations"

    if nodes_dir.is_dir():
        for f in sorted(nodes_dir.glob("*.json")):
            with open(f, encoding="utf-8") as fh:
                data = json.load(fh)
            idx.nodes[data["id"]] = IndexNode(
                name=data["name"],
                file=data.get("file"),
                status=data["status"],
                derivations_as_input=data.get("derivations_as_input", []),
                derivations_as_output=data.get("derivations_as_output", []),
            )

    if deriv_dir.is_dir():
        for f in sorted(deriv_dir.glob("*.json")):
            with open(f, encoding="utf-8") as fh:
                data = json.load(fh)
            idx.derivations[data["id"]] = IndexDerivation(
                summary=data["summary"],
                inputs=[{"node": i["node"], "role": i["role"]} for i in data["inputs"]],
                output={"node": data["output"]["node"], "method": data["output"]["method"]},
            )

    save_index(root, idx)
    return idx


def _index_to_dict(index: Index) -> dict:
    return {
        "nodes": {
            nid: {
                "name": n.name,
                "file": n.file,
                "status": n.status,
                "derivations_as_input": n.derivations_as_input,
                "derivations_as_output": n.derivations_as_output,
            }
            for nid, n in index.nodes.items()
        },
        "derivations": {
            did: {
                "summary": d.summary,
                "inputs": d.inputs,
                "output": d.output,
            }
            for did, d in index.derivations.items()
        },
    }


def _dict_to_index(data: dict) -> Index:
    nodes = {}
    for nid, nd in data.get("nodes", {}).items():
        nodes[nid] = IndexNode(
            name=nd["name"],
            file=nd.get("file"),
            status=nd["status"],
            derivations_as_input=nd.get("derivations_as_input", []),
            derivations_as_output=nd.get("derivations_as_output", []),
        )
    derivations = {}
    for did, dd in data.get("derivations", {}).items():
        derivations[did] = IndexDerivation(
            summary=dd["summary"],
            inputs=dd["inputs"],
            output=dd["output"],
        )
    return Index(nodes=nodes, derivations=derivations)
