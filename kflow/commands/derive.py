"""kflow derive — create a derivation and its output node."""
from pathlib import Path
from kflow.models import Node, Derivation, InputSpec, OutputSpec, IndexNode, IndexDerivation, generate_unique_id
from kflow.store import load_index, save_index, save_node, save_derivation, load_node, require_kflow
from kflow.errors import NodeNotFoundError, NodeExistsError, CyclicError
from kflow.graph import would_create_cycle


def derive_node(root: Path, inputs: list[dict], output: dict, summary: str) -> dict:
    """Create a derivation from input nodes to a new output node."""
    kf = require_kflow(root)
    index = load_index(root)

    # Resolve input node names to IDs
    input_specs = []
    input_ids = []
    for inp in inputs:
        node_id = _resolve_name(index, inp["node"])
        input_specs.append(InputSpec(node=node_id, role=inp["role"], role_detail=inp.get("role_detail", "")))
        input_ids.append(node_id)

    # Check output name uniqueness
    for existing in index.nodes.values():
        if existing.name == output["name"]:
            raise NodeExistsError(output["name"])

    # Generate IDs
    existing_ids = set(index.derivations.keys()) | set(index.nodes.keys())
    dv_id = generate_unique_id("dv", existing_ids)
    all_ids = set(index.nodes.keys())
    out_id = generate_unique_id("nd", all_ids | {dv_id})

    # Cycle check
    if would_create_cycle(index, input_ids, out_id):
        raise CyclicError(f"would connect {input_ids} → {out_id} forming a cycle")

    # Create output node
    out_node = Node(
        id=out_id, name=output["name"],
        file=f"knowledge/{output['name']}.md",
        status="green",
        derivations_as_input=[],
        derivations_as_output=[dv_id],
    )

    # Create derivation
    out_spec = OutputSpec(node=out_id, method=output["method"], method_detail=output.get("method_detail", ""))
    dv = Derivation(id=dv_id, summary=summary, inputs=input_specs, output=out_spec)

    # Create markdown file
    knowledge_dir = root / "knowledge"
    knowledge_dir.mkdir(exist_ok=True)
    md_file = knowledge_dir / f"{output['name']}.md"
    if not md_file.exists():
        md_file.write_text(f"# {output['name']}\n", encoding="utf-8")

    # Update input nodes (both index and individual files)
    for inp_id in input_ids:
        in_node_data = index.nodes.get(inp_id)
        if in_node_data:
            updated_list = list(in_node_data.derivations_as_input)
            updated_list.append(dv_id)
            in_node_data.derivations_as_input = updated_list
            full_node = load_node(root, inp_id)
            full_node.derivations_as_input.append(dv_id)
            save_node(root, full_node)

    # Persist new files
    save_node(root, out_node)
    save_derivation(root, dv)

    # Update index
    index.nodes[out_id] = IndexNode(
        name=out_node.name, file=out_node.file, status=out_node.status,
        derivations_as_input=[], derivations_as_output=[dv_id],
    )
    index.derivations[dv_id] = IndexDerivation(
        summary=dv.summary,
        inputs=[{"node": isp.node, "role": isp.role} for isp in dv.inputs],
        output={"node": dv.output.node, "method": dv.output.method},
    )
    save_index(root, index)

    return {
        "ok": True,
        "node": {"id": out_id, "name": out_node.name, "status": out_node.status, "file": out_node.file},
        "derivation": dv_id,
        "affected": [],
    }


def _resolve_name(index, name: str) -> str:
    """Find a node ID by name. Raises NodeNotFoundError if missing."""
    for nid, node in index.nodes.items():
        if node.name == name:
            return nid
    raise NodeNotFoundError(name)
