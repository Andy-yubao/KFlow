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
  role: NodeStructureRole;
  layer: number;
};

export type NodeStructureRole =
  | "source"
  | "intermediate"
  | "terminal"
  | "isolated";

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
  const producerInputs = new Map<string, string[]>();
  const consumerIds = new Set<string>();
  for (const derivation of project.derivations) {
    const inputs = derivation.inputs.map((role) => role.node);
    for (const input of inputs) consumerIds.add(input);
    for (const output of derivation.outputs) {
      producerInputs.set(output.node, inputs);
    }
  }
  const layerById = computeNodeLayers(project.nodes, producerInputs);
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
      data: {
        kind: "knowledge",
        node,
        role: structureRole(
          producerInputs.has(node.id),
          consumerIds.has(node.id),
        ),
        layer: layerById.get(node.id) ?? 0,
      },
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

function structureRole(
  hasProducer: boolean,
  hasConsumer: boolean,
): NodeStructureRole {
  if (!hasProducer && hasConsumer) return "source";
  if (hasProducer && hasConsumer) return "intermediate";
  if (hasProducer) return "terminal";
  return "isolated";
}

export function computeNodeLayers(
  nodes: StatusNode[],
  producerInputs: ReadonlyMap<string, readonly string[]>,
): Map<string, number> {
  const nodeIds = new Set(nodes.map((node) => node.id));
  const layers = new Map<string, number>();
  const visiting = new Set<string>();

  const layerFor = (nodeId: string): number => {
    const cached = layers.get(nodeId);
    if (cached !== undefined) return cached;
    const inputs = producerInputs.get(nodeId);
    if (!inputs || inputs.length === 0 || visiting.has(nodeId)) {
      layers.set(nodeId, 0);
      return 0;
    }
    visiting.add(nodeId);
    const inputLayers = inputs
      .filter((inputId) => nodeIds.has(inputId))
      .map(layerFor);
    visiting.delete(nodeId);
    const layer = (inputLayers.length > 0 ? Math.max(...inputLayers) : -1) + 1;
    layers.set(nodeId, Math.max(0, layer));
    return Math.max(0, layer);
  };

  for (const node of nodes) layerFor(node.id);
  return layers;
}
