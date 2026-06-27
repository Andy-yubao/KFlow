"""kflow create — create a source knowledge node."""
from pathlib import Path
from kflow.models import Node, generate_unique_id, IndexNode
from kflow.store import load_index, save_index, save_node, require_kflow
from kflow.errors import NodeExistsError


def create_node(root: Path, name: str, no_file: bool = False) -> dict:
    """Create a new source node. Returns result dict with node info."""
    kf = require_kflow(root)
    index = load_index(root)

    for existing in index.nodes.values():
        if existing.name == name:
            raise NodeExistsError(name)

    node_id = generate_unique_id("nd", set(index.nodes.keys()))

    file_path = None
    if not no_file:
        knowledge_dir = root / "knowledge"
        knowledge_dir.mkdir(exist_ok=True)
        md_file = knowledge_dir / f"{name}.md"
        if not md_file.exists():
            md_file.write_text(f"# {name}\n", encoding="utf-8")
        file_path = f"knowledge/{name}.md"

    node = Node(
        id=node_id, name=name, file=file_path, status="green",
        derivations_as_input=[], derivations_as_output=[],
    )

    save_node(root, node)

    index.nodes[node_id] = IndexNode(
        name=node.name, file=node.file, status=node.status,
        derivations_as_input=[], derivations_as_output=[],
    )
    save_index(root, index)

    return {
        "ok": True,
        "node": {"id": node.id, "name": node.name, "status": node.status, "file": node.file},
        "affected": [],
    }
