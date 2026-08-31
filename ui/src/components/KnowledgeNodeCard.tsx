import { Handle, Position, type NodeProps } from "@xyflow/react";

import type { KnowledgeFlowNode } from "../graph/buildFlowGraph";
import { nodeVisualState } from "./nodeVisualState";

const roleLabels = {
  source: "Source",
  intermediate: "Intermediate",
  terminal: "Terminal",
  isolated: "Isolated",
} as const;

const statusPresentation = {
  current: { symbol: "✓", label: "Current" },
  attention: { symbol: "!", label: "Needs review" },
  unknown: { symbol: "?", label: "Unknown" },
} as const;

export function KnowledgeNodeCard({ data, selected }: NodeProps<KnowledgeFlowNode>) {
  const { node, role, layer } = data;
  const visualState = nodeVisualState(node);
  const roleLabel = roleLabels[role];
  const status = statusPresentation[visualState];

  return (
    <div
      className={`graph-node knowledge-node role-${role} ${selected ? "selected" : ""}`}
      aria-label={`Knowledge Node: ${node.name}. ${roleLabel}, layer ${layer}. ${status.label}.`}
      tabIndex={0}
    >
      <Handle type="target" position={Position.Left} />
      <div className="node-kicker">{roleLabel} · L{layer}</div>
      <strong title={node.name}>{node.name}</strong>
      <div className="node-meta">
        <span className={`status-badge ${visualState}`}>
          <span aria-hidden="true">{status.symbol}</span> {status.label}
        </span>
        <span>{node.files.length} {node.files.length === 1 ? "file" : "files"}</span>
      </div>
      <Handle type="source" position={Position.Right} />
    </div>
  );
}
