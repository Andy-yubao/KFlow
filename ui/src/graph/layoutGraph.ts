import dagre from "@dagrejs/dagre";
import { Position } from "@xyflow/react";

import type {
  FlowGraph,
  ProjectFlowNode,
} from "./buildFlowGraph";

// Must match the fixed card dimensions in styles.css.
export const KNOWLEDGE_NODE_SIZE = { width: 240, height: 120 };
export const DERIVATION_NODE_SIZE = { width: 210, height: 96 };

function nodeSize(node: ProjectFlowNode) {
  return node.type === "derivationNode"
    ? DERIVATION_NODE_SIZE
    : KNOWLEDGE_NODE_SIZE;
}

export function layoutProjectGraph(graph: FlowGraph): FlowGraph {
  const layout = new dagre.graphlib.Graph();
  layout.setDefaultEdgeLabel(() => ({}));
  layout.setGraph({
    rankdir: "LR",
    ranksep: 90,
    nodesep: 42,
    marginx: 28,
    marginy: 28,
  });

  for (const node of graph.nodes) {
    layout.setNode(node.id, { ...nodeSize(node) });
  }
  for (const edge of graph.edges) {
    layout.setEdge(edge.source, edge.target);
  }
  dagre.layout(layout);

  return {
    nodes: graph.nodes.map((node) => {
      const point = layout.node(node.id);
      const size = nodeSize(node);
      return {
        ...node,
        sourcePosition: Position.Right,
        targetPosition: Position.Left,
        position: {
          x: point.x - size.width / 2,
          y: point.y - size.height / 2,
        },
      };
    }),
    edges: graph.edges.map((edge) => ({ ...edge })),
  };
}
