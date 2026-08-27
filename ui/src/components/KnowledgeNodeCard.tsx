import { Handle, Position, type NodeProps } from "@xyflow/react";

import type { KnowledgeFlowNode } from "../graph/buildFlowGraph";
import { nodeVisualState } from "./nodeVisualState";

export function KnowledgeNodeCard({ data, selected }: NodeProps<KnowledgeFlowNode>) {
  const { node } = data;
  const visualState = nodeVisualState(node);

  return (
    <div className={`graph-node knowledge-node ${visualState} ${selected ? "selected" : ""}`}>
      <Handle type="target" position={Position.Left} />
      <div className="node-kicker">Knowledge Node</div>
      <strong title={node.name}>{node.name}</strong>
      <div className="node-meta">
        <span className={`status-dot ${visualState}`} aria-hidden="true" />
        {node.status ?? "unknown"} · {node.files.length} {node.files.length === 1 ? "file" : "files"}
      </div>
      <Handle type="source" position={Position.Right} />
    </div>
  );
}
