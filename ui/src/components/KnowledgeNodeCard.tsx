import { Handle, Position, type NodeProps } from "@xyflow/react";

import type { KnowledgeFlowNode } from "../graph/buildFlowGraph";

export function KnowledgeNodeCard({ data, selected }: NodeProps<KnowledgeFlowNode>) {
  const { node } = data;
  const statusClass = node.reasons.length ? "attention" : "current";

  return (
    <div className={`graph-node knowledge-node ${statusClass} ${selected ? "selected" : ""}`}>
      <Handle type="target" position={Position.Left} />
      <div className="node-kicker">Knowledge Node</div>
      <strong>{node.name}</strong>
      <div className="node-meta">
        <span className={`status-dot ${statusClass}`} aria-hidden="true" />
        {node.status ?? "unknown"} · {node.files.length} {node.files.length === 1 ? "file" : "files"}
      </div>
      <Handle type="source" position={Position.Right} />
    </div>
  );
}
