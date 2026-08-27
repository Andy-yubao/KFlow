import type { NodeProps } from "@xyflow/react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it, vi } from "vitest";

import type {
  DerivationFlowNode,
  KnowledgeFlowNode,
} from "../graph/buildFlowGraph";
import { DerivationNodeCard } from "./DerivationNodeCard";
import { KnowledgeNodeCard } from "./KnowledgeNodeCard";

vi.mock("@xyflow/react", () => ({
  Handle: () => null,
  Position: { Left: "left", Right: "right" },
}));

describe("graph node cards", () => {
  it("keeps the full Knowledge Node name available and styles unknown gray", () => {
    const name = "A complete Knowledge Node name for the Inspector";
    const props: NodeProps<KnowledgeFlowNode> = {
      id: "node:nd_architecture",
      type: "knowledgeNode",
      data: {
        kind: "knowledge",
        node: {
          id: "nd_architecture",
          name,
          files: ["docs/architecture.md"],
          changed_files: [],
          status: null,
          reasons: [],
        },
      },
      dragging: false,
      zIndex: 0,
      selectable: true,
      deletable: false,
      selected: false,
      draggable: false,
      isConnectable: false,
      positionAbsoluteX: 0,
      positionAbsoluteY: 0,
    };
    const markup = renderToStaticMarkup(KnowledgeNodeCard(props));

    expect(markup).toContain(`title="${name}"`);
    expect(markup).toContain("knowledge-node unknown");
    expect(markup).toContain("status-dot unknown");
  });

  it("keeps the full Derivation short text available", () => {
    const short = "A complete Derivation short description";
    const props: NodeProps<DerivationFlowNode> = {
      id: "derivation:dv_design",
      type: "derivationNode",
      data: {
        kind: "derivation",
        derivation: {
          id: "dv_design",
          short,
          detail: "",
          inputs: [],
          outputs: [],
        },
      },
      dragging: false,
      zIndex: 0,
      selectable: true,
      deletable: false,
      selected: false,
      draggable: false,
      isConnectable: false,
      positionAbsoluteX: 0,
      positionAbsoluteY: 0,
    };
    const markup = renderToStaticMarkup(DerivationNodeCard(props));

    expect(markup).toContain(`title="${short}"`);
  });
});
