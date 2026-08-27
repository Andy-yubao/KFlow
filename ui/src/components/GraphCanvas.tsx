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
  const { select } = useProject();
  const { fitView } = useReactFlow();
  const flow = useMemo(
    () => layoutProjectGraph(buildFlowGraph(graph)),
    [graph],
  );

  useEffect(() => {
    const frame = window.requestAnimationFrame(() => {
      void fitView({ padding: 0.18, duration: 0 });
    });
    return () => window.cancelAnimationFrame(frame);
  }, [fitView, flow.nodes]);

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
