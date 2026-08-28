import { nodeVisualState } from "../components/nodeVisualState";
import type { SelectedElement } from "../state/ProjectContext";
import type { DerivationResult, ProjectGraphResult } from "../types/projectGraph";
import {
  derivationFlowId,
  knowledgeFlowId,
} from "./buildFlowGraph";

export type StatusFilter = "all" | "current" | "attention" | "unknown";

export interface GraphViewOptions {
  searchText: string;
  statusFilter: StatusFilter;
  onlyNeedsReview: boolean;
  selectedElement: SelectedElement;
}

export interface GraphView {
  visibleKnowledgeNodeIds: string[];
  visibleFlowNodeIds: string[];
  visibleEdgeIds: string[];
  emphasizedNodeIds: string[];
  emphasizedEdgeIds: string[];
  hasFocus: boolean;
  searchActive: boolean;
  searchMatchCount: number;
}

function inputEdgeId(nodeId: string, derivationId: string): string {
  return `input:${nodeId}:${derivationId}`;
}

function outputEdgeId(derivationId: string, nodeId: string): string {
  return `output:${derivationId}:${nodeId}`;
}

function derivationNodeIds(derivation: DerivationResult): string[] {
  return [
    ...derivation.inputs.map((role) => role.node),
    ...derivation.outputs.map((role) => role.node),
  ];
}

function addDerivationFocus(
  derivation: DerivationResult,
  nodes: Set<string>,
  edges: Set<string>,
): void {
  nodes.add(derivationFlowId(derivation.id));
  for (const role of derivation.inputs) {
    nodes.add(knowledgeFlowId(role.node));
    edges.add(inputEdgeId(role.node, derivation.id));
  }
  for (const role of derivation.outputs) {
    nodes.add(knowledgeFlowId(role.node));
    edges.add(outputEdgeId(derivation.id, role.node));
  }
}

function addKnowledgeFocus(
  nodeId: string,
  derivations: DerivationResult[],
  nodes: Set<string>,
  edges: Set<string>,
): void {
  nodes.add(knowledgeFlowId(nodeId));
  for (const derivation of derivations) {
    if (derivation.outputs.some((role) => role.node === nodeId)) {
      nodes.add(derivationFlowId(derivation.id));
      edges.add(outputEdgeId(derivation.id, nodeId));
      for (const role of derivation.inputs) {
        nodes.add(knowledgeFlowId(role.node));
        edges.add(inputEdgeId(role.node, derivation.id));
      }
    }
    if (derivation.inputs.some((role) => role.node === nodeId)) {
      nodes.add(derivationFlowId(derivation.id));
      edges.add(inputEdgeId(nodeId, derivation.id));
      for (const role of derivation.outputs) {
        nodes.add(knowledgeFlowId(role.node));
        edges.add(outputEdgeId(derivation.id, role.node));
      }
    }
  }
}

function includesSearch(values: string[], searchText: string): boolean {
  return values.some((value) => value.toLocaleLowerCase().includes(searchText));
}

export function buildGraphView(
  project: ProjectGraphResult,
  options: GraphViewOptions,
): GraphView {
  const visibleKnowledge = new Set(
    project.nodes
      .filter((node) => {
        const state = nodeVisualState(node);
        const matchesStatus =
          options.statusFilter === "all" || options.statusFilter === state;
        return matchesStatus && (!options.onlyNeedsReview || node.reasons.length > 0);
      })
      .map((node) => node.id),
  );
  const visibleDerivations = new Set(
    project.derivations
      .filter((derivation) =>
        derivationNodeIds(derivation).some((nodeId) => visibleKnowledge.has(nodeId)),
      )
      .map((derivation) => derivation.id),
  );
  const visibleFlowNodes = new Set([
    ...[...visibleKnowledge].map(knowledgeFlowId),
    ...[...visibleDerivations].map(derivationFlowId),
  ]);
  const visibleEdges = new Set<string>();
  for (const derivation of project.derivations) {
    if (!visibleDerivations.has(derivation.id)) continue;
    for (const role of derivation.inputs) {
      if (visibleKnowledge.has(role.node)) {
        visibleEdges.add(inputEdgeId(role.node, derivation.id));
      }
    }
    for (const role of derivation.outputs) {
      if (visibleKnowledge.has(role.node)) {
        visibleEdges.add(outputEdgeId(derivation.id, role.node));
      }
    }
  }

  const emphasizedNodes = new Set<string>();
  const emphasizedEdges = new Set<string>();
  const normalizedSearch = options.searchText.trim().toLocaleLowerCase();
  const searchActive = normalizedSearch.length > 0;
  const matchingNodeIds = searchActive
    ? project.nodes
        .filter((node) =>
          includesSearch([node.name, node.id, ...node.files], normalizedSearch),
        )
        .map((node) => node.id)
    : [];
  const matchingDerivationIds = searchActive
    ? project.derivations
        .filter((derivation) =>
          includesSearch(
            [derivation.id, derivation.short, derivation.detail],
            normalizedSearch,
          ),
        )
        .map((derivation) => derivation.id)
    : [];
  const searchMatchCount = matchingNodeIds.length + matchingDerivationIds.length;

  if (options.selectedElement?.kind === "knowledge") {
    addKnowledgeFocus(
      options.selectedElement.id,
      project.derivations,
      emphasizedNodes,
      emphasizedEdges,
    );
  } else if (options.selectedElement?.kind === "derivation") {
    const derivation = project.derivations.find(
      (candidate) => candidate.id === options.selectedElement?.id,
    );
    if (derivation) addDerivationFocus(derivation, emphasizedNodes, emphasizedEdges);
  } else if (searchActive) {
    for (const nodeId of matchingNodeIds) {
      addKnowledgeFocus(nodeId, project.derivations, emphasizedNodes, emphasizedEdges);
    }
    for (const derivationId of matchingDerivationIds) {
      const derivation = project.derivations.find(
        (candidate) => candidate.id === derivationId,
      );
      if (derivation) {
        addDerivationFocus(derivation, emphasizedNodes, emphasizedEdges);
      }
    }
  } else {
    visibleFlowNodes.forEach((id) => emphasizedNodes.add(id));
    visibleEdges.forEach((id) => emphasizedEdges.add(id));
  }
  const hasFocus =
    options.selectedElement !== null || (searchActive && searchMatchCount > 0);

  return {
    visibleKnowledgeNodeIds: [...visibleKnowledge].map(knowledgeFlowId),
    visibleFlowNodeIds: [...visibleFlowNodes],
    visibleEdgeIds: [...visibleEdges],
    emphasizedNodeIds: [...emphasizedNodes].filter((id) => visibleFlowNodes.has(id)),
    emphasizedEdgeIds: [...emphasizedEdges].filter((id) => visibleEdges.has(id)),
    hasFocus,
    searchActive,
    searchMatchCount,
  };
}
