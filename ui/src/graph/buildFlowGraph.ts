import type { Edge, Node } from "@xyflow/react";

import type {
  DerivationResult,
  DerivationRole,
  ProjectGraphResult,
  StatusNode,
} from "../types/projectGraph";

export type KnowledgeNodeData = {
  kind: "knowledge";
  node: StatusNode;
};

export type DerivationNodeData = {
  kind: "derivation";
  derivation: DerivationResult;
};

export type RoleEdgeData = {
  kind: "input" | "output";
  role: DerivationRole;
};

export type KnowledgeFlowNode = Node<KnowledgeNodeData, "knowledgeNode">;
export type DerivationFlowNode = Node<DerivationNodeData, "derivationNode">;
export type ProjectFlowNode = KnowledgeFlowNode | DerivationFlowNode;
export type ProjectFlowEdge = Edge<RoleEdgeData>;

export interface FlowGraph {
  nodes: ProjectFlowNode[];
  edges: ProjectFlowEdge[];
}

export function knowledgeFlowId(nodeId: string): string {
  return `node:${nodeId}`;
}

export function derivationFlowId(derivationId: string): string {
  return `derivation:${derivationId}`;
}

export function buildFlowGraph(project: ProjectGraphResult): FlowGraph {
  const nodeById = new Map(project.nodes.map((node) => [node.id, node]));
  const seen = new Set<string>();
  const orderedKnowledgeNodes: StatusNode[] = [];

  for (const nodeId of project.topological_order) {
    const node = nodeById.get(nodeId);
    if (node && !seen.has(nodeId)) {
      orderedKnowledgeNodes.push(node);
      seen.add(nodeId);
    }
  }
  orderedKnowledgeNodes.push(
    ...project.nodes
      .filter((node) => !seen.has(node.id))
      .sort((left, right) => left.id.localeCompare(right.id)),
  );

  const derivations = [...project.derivations].sort((left, right) =>
    left.id.localeCompare(right.id),
  );
  const nodes: ProjectFlowNode[] = [
    ...orderedKnowledgeNodes.map<KnowledgeFlowNode>((node) => ({
      id: knowledgeFlowId(node.id),
      type: "knowledgeNode",
      position: { x: 0, y: 0 },
      data: { kind: "knowledge", node },
    })),
    ...derivations.map<DerivationFlowNode>((derivation) => ({
      id: derivationFlowId(derivation.id),
      type: "derivationNode",
      position: { x: 0, y: 0 },
      data: { kind: "derivation", derivation },
    })),
  ];

  const edges: ProjectFlowEdge[] = [];
  for (const derivation of derivations) {
    const derivationId = derivationFlowId(derivation.id);
    for (const role of derivation.inputs) {
      edges.push({
        id: `input:${role.node}:${derivation.id}`,
        source: knowledgeFlowId(role.node),
        target: derivationId,
        data: { kind: "input", role },
      });
    }
    for (const role of derivation.outputs) {
      edges.push({
        id: `output:${derivation.id}:${role.node}`,
        source: derivationId,
        target: knowledgeFlowId(role.node),
        data: { kind: "output", role },
      });
    }
  }

  return { nodes, edges };
}
