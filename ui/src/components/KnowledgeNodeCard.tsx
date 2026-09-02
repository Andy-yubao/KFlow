import { Handle, Position, type NodeProps } from "@xyflow/react";
import type { CSSProperties } from "react";

import type {
  KnowledgeFlowNode,
  NodeStructureRole,
} from "../graph/buildFlowGraph";
import { nodeVisualState } from "./nodeVisualState";

type StructureStyle = CSSProperties & {
  "--role-color": string;
  "--role-text-color": string;
  "--role-border-color": string;
  "--role-background": string;
};

export const NODE_STRUCTURE_STYLES: Record<NodeStructureRole, StructureStyle> = {
  source: {
    "--role-color": "#3b82f6",
    "--role-text-color": "#1d4ed8",
    "--role-border-color": "#93c5fd",
    "--role-background": "#eff6ff",
  },
  intermediate: {
    "--role-color": "#8b5cf6",
    "--role-text-color": "#6d28d9",
    "--role-border-color": "#c4b5fd",
    "--role-background": "#f5f3ff",
  },
  terminal: {
    "--role-color": "#0f766e",
    "--role-text-color": "#0f766e",
    "--role-border-color": "#5fb7ad",
    "--role-background": "#f0fdfa",
  },
  isolated: {
    "--role-color": "#94a3b8",
    "--role-text-color": "#475569",
    "--role-border-color": "#94a3b8",
    "--role-background": "#f8fafc",
  },
};

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
      style={NODE_STRUCTURE_STYLES[role]}
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
