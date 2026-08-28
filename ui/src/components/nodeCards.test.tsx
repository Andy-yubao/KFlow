import type { NodeProps } from "@xyflow/react";
import { fireEvent, render, screen } from "@testing-library/react";
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
    const markup = renderToStaticMarkup(<KnowledgeNodeCard {...props} />);

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
    const markup = renderToStaticMarkup(<DerivationNodeCard {...props} />);

    expect(markup).toContain(`title="${short}"`);
    expect(markup).toContain("derivation-mark");
    expect(markup).not.toContain("derivation-tooltip");
  });

  it("shows and hides the Derivation tooltip on pointer and keyboard interaction", () => {
    const short = "A complete Derivation short description";
    const derivation = {
      id: "dv_design",
      short,
      detail: "Detailed meaning.",
      inputs: [],
      outputs: [],
    };
    const props = {
      id: "derivation:dv_design",
      type: "derivationNode",
      data: { kind: "derivation" as const, derivation },
      dragging: false,
      zIndex: 0,
      selectable: true,
      deletable: false,
      selected: false,
      draggable: false,
      isConnectable: false,
      positionAbsoluteX: 0,
      positionAbsoluteY: 0,
    } satisfies NodeProps<DerivationFlowNode>;

    render(<DerivationNodeCard {...props} />);
    const card = screen.getByLabelText(`Derivation: ${short}`);
    expect(card.getAttribute("title")).toBe(short);
    expect(screen.queryByRole("tooltip")).toBeNull();

    fireEvent.mouseEnter(card);
    expect(screen.getByRole("tooltip").textContent).toBe(short);
    fireEvent.mouseLeave(card);
    expect(screen.queryByRole("tooltip")).toBeNull();

    fireEvent.focus(card);
    expect(screen.getByRole("tooltip").textContent).toBe(short);
    fireEvent.blur(card);
    expect(screen.queryByRole("tooltip")).toBeNull();
    expect(derivation).toEqual(props.data.derivation);
    expect(card.className).not.toContain("selected");
  });
});
