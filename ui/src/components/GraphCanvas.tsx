import {
  Background,
  BackgroundVariant,
  Controls,
  MarkerType,
  ReactFlow,
  ReactFlowProvider,
  useReactFlow,
  type NodeMouseHandler,
  type NodeTypes,
} from "@xyflow/react";
import { useEffect, useMemo } from "react";

import { buildFlowGraph, type ProjectFlowNode } from "../graph/buildFlowGraph";
import { buildGraphView } from "../graph/graphView";
import { layoutProjectGraph } from "../graph/layoutGraph";
import { useProject } from "../state/ProjectContext";
import type { ProjectGraphResult } from "../types/projectGraph";
import { DerivationNodeCard } from "./DerivationNodeCard";
import { KnowledgeNodeCard } from "./KnowledgeNodeCard";

const nodeTypes: NodeTypes = {
  knowledgeNode: KnowledgeNodeCard,
  derivationNode: DerivationNodeCard,
};

const defaultEdgeOptions = {
  markerEnd: { type: MarkerType.ArrowClosed, color: "#8b9991" },
};

function ProjectGraphView({ graph }: { graph: ProjectGraphResult }) {
  const { state, select } = useProject();
  const { fitView } = useReactFlow();
  const view = useMemo(
    () =>
      buildGraphView(graph, {
        searchText: state.searchText,
        statusFilter: state.statusFilter,
        onlyNeedsReview: state.onlyNeedsReview,
        selectedElement: state.selectedElement,
      }),
    [
      graph,
      state.onlyNeedsReview,
      state.searchText,
      state.selectedElement,
      state.statusFilter,
    ],
  );
  const flow = useMemo(() => {
    const visibleNodes = new Set(view.visibleFlowNodeIds);
    const visibleEdges = new Set(view.visibleEdgeIds);
    const emphasizedNodes = new Set(view.emphasizedNodeIds);
    const emphasizedEdges = new Set(view.emphasizedEdgeIds);
    const built = buildFlowGraph(graph);
    const laidOut = layoutProjectGraph({
      nodes: built.nodes.filter((node) => visibleNodes.has(node.id)),
      edges: built.edges.filter((edge) => visibleEdges.has(edge.id)),
    });
    return {
      nodes: laidOut.nodes.map((node) => ({
        ...node,
        selected:
          state.selectedElement?.kind === node.data.kind &&
          state.selectedElement.id ===
            (node.data.kind === "knowledge"
              ? node.data.node.id
              : node.data.derivation.id),
        className:
          view.hasFocus && !emphasizedNodes.has(node.id) ? "is-dimmed" : "",
      })),
      edges: laidOut.edges.map((edge) => ({
        ...edge,
        className:
          view.hasFocus && !emphasizedEdges.has(edge.id) ? "is-dimmed" : "",
      })),
    };
  }, [graph, state.selectedElement, view]);

  useEffect(() => {
    if (state.selectedElement !== null) return;
    const frame = window.requestAnimationFrame(() => {
      void fitView({ padding: 0.18, duration: 0 });
    });
    return () => window.cancelAnimationFrame(frame);
  }, [fitView, flow.nodes, state.selectedElement]);

  useEffect(() => {
    if (state.selectedElement === null) return;
    const selectedId =
      state.selectedElement.kind === "knowledge"
        ? `node:${state.selectedElement.id}`
        : `derivation:${state.selectedElement.id}`;
    const selectedNode = flow.nodes.find((node) => node.id === selectedId);
    if (selectedNode) {
      void fitView({ nodes: [selectedNode], padding: 0.8, maxZoom: 1.15, duration: 240 });
    }
  }, [fitView, flow.nodes, state.selectedElement]);

  const onNodeClick: NodeMouseHandler<ProjectFlowNode> = (_event, node) => {
    if (node.data.kind === "knowledge") {
      select({ kind: "knowledge", id: node.data.node.id });
    } else {
      select({ kind: "derivation", id: node.data.derivation.id });
    }
  };

  return (
    <ReactFlow
      nodes={flow.nodes}
      edges={flow.edges}
      nodeTypes={nodeTypes}
      defaultEdgeOptions={defaultEdgeOptions}
      onNodeClick={onNodeClick}
      onPaneClick={() => select(null)}
      nodesDraggable={false}
      nodesConnectable={false}
      elementsSelectable
      fitView
      minZoom={0.2}
      maxZoom={1.8}
      proOptions={{ hideAttribution: true }}
    >
      <Background variant={BackgroundVariant.Dots} gap={24} size={1} />
      <Controls showInteractive={false} />
    </ReactFlow>
  );
}

export function GraphCanvas({ graph }: { graph: ProjectGraphResult }) {
  if (graph.ok && graph.nodes.length === 0) {
    return (
      <section className="graph-empty">
        <div>
          <span className="empty-symbol" aria-hidden="true">○</span>
          <h2>项目图为空</h2>
          <p>KFlow 已初始化，但尚未登记 Knowledge Node。</p>
        </div>
      </section>
    );
  }

  if (graph.nodes.length === 0) {
    return (
      <section className="graph-empty">
        <div><h2>Project graph unavailable</h2><p>Resolve the reported issues, then reload.</p></div>
      </section>
    );
  }

  return (
    <section className="graph-canvas" aria-label="Project knowledge graph">
      <ReactFlowProvider>
        <ProjectGraphView graph={graph} />
      </ReactFlowProvider>
    </section>
  );
}
