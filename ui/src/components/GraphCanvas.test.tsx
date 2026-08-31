import { render } from "@testing-library/react";
import type { ReactNode } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type { GraphView } from "../graph/graphView";
import type { ProjectGraphResult } from "../types/projectGraph";
import { GraphCanvas } from "./GraphCanvas";

const flow = vi.hoisted(() => ({ fitView: vi.fn() }));
const context = vi.hoisted(() => ({
  state: { selectedElement: null },
  select: vi.fn(),
}));

vi.mock("../state/ProjectContext", () => ({ useProject: () => context }));
vi.mock("@xyflow/react", () => ({
  Background: () => null,
  BackgroundVariant: { Dots: "dots" },
  Controls: () => null,
  Handle: () => null,
  MarkerType: { ArrowClosed: "arrowclosed" },
  Position: { Left: "left", Right: "right" },
  ReactFlow: ({ children }: { children: ReactNode }) => <div>{children}</div>,
  ReactFlowProvider: ({ children }: { children: ReactNode }) => <>{children}</>,
  useReactFlow: () => flow,
}));

function graph(reason: string[] = []): ProjectGraphResult {
  return {
    ok: true,
    schema_version: 2,
    project: {
      status: reason.length ? "attention_required" : "current",
      node_count: 1,
      derivation_count: 0,
      needs_review_count: reason.length ? 1 : 0,
      issue_count: 0,
    },
    nodes: [
      {
        id: "nd_one",
        name: "One",
        files: ["one.md"],
        changed_files: [],
        status: "valid",
        reasons: reason,
      },
    ],
    derivations: [],
    topological_order: ["nd_one"],
    issues: [],
  };
}

const view: GraphView = {
  visibleKnowledgeNodeIds: ["nd_one"],
  visibleFlowNodeIds: ["node:nd_one"],
  visibleEdgeIds: [],
  emphasizedNodeIds: [],
  emphasizedEdgeIds: [],
  hasFocus: false,
  searchActive: false,
  searchMatchCount: 0,
};

beforeEach(() => {
  flow.fitView.mockReset();
  vi.spyOn(window, "requestAnimationFrame").mockImplementation((callback) => {
    callback(0);
    return 1;
  });
  vi.spyOn(window, "cancelAnimationFrame").mockImplementation(() => undefined);
});

describe("GraphCanvas viewport preservation", () => {
  it("does not fit the graph again when refreshed project data replaces it", () => {
    const rendered = render(<GraphCanvas graph={graph()} view={view} />);
    expect(flow.fitView).toHaveBeenCalledTimes(1);

    rendered.rerender(
      <GraphCanvas graph={graph(["files_changed"])} view={view} />,
    );

    expect(flow.fitView).toHaveBeenCalledTimes(1);
  });
});
