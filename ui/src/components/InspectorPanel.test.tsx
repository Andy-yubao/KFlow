import { act, fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { openRegisteredFile } from "../api/project";
import { buildFlowGraph } from "../graph/buildFlowGraph";
import type { ProjectGraphResult } from "../types/projectGraph";
import { selectedElementForFlowNode } from "./GraphCanvas";
import { InspectorPanel } from "./InspectorPanel";

vi.mock("../api/project", async (importOriginal) => {
  const original = await importOriginal<typeof import("../api/project")>();
  return { ...original, openRegisteredFile: vi.fn() };
});

function project(): ProjectGraphResult {
  return {
    ok: true,
    schema_version: 3,
    project: {
      status: "current",
      node_count: 2,
      derivation_count: 1,
      needs_review_count: 0,
      issue_count: 0,
    },
    nodes: [
      {
        id: "nd_input",
        name: "Input",
        files: ["docs/input.md", "docs/input.svg"],
        changed_files: [],
        status: "confirmed",
        reasons: [],
      },
      {
        id: "nd_output",
        name: "Output",
        files: ["docs/output.md"],
        changed_files: [],
        status: "confirmed",
        reasons: [],
      },
    ],
    derivations: [
      {
        id: "dv_design",
        name: "design",
        short: "Input creates output",
        detail: "The complete derivation detail.",
        inputs: [
          {
            node: "nd_input",
            name: "Input",
            short: "Provides source facts",
            detail: "Input role detail.",
          },
        ],
        outputs: [
          {
            node: "nd_output",
            name: "Output",
            short: "Creates the result",
            detail: "Output role detail.",
          },
        ],
      },
    ],
    topological_order: ["nd_input", "nd_output"],
    issues: [],
  };
}

beforeEach(() => {
  vi.mocked(openRegisteredFile).mockReset();
});

describe("InspectorPanel interactions", () => {
  it("connects a clicked Derivation flow node to its complete Inspector facts", () => {
    const graph = project();
    const flowNode = buildFlowGraph(graph).nodes.find(
      (node) => node.id === "derivation:dv_design",
    );
    expect(flowNode).toBeDefined();
    const selected = selectedElementForFlowNode(flowNode!);

    render(<InspectorPanel graph={graph} selected={selected} />);

    expect(selected).toEqual({ kind: "derivation", id: "dv_design" });
    expect(screen.getByRole("heading", { name: "design" })).toBeTruthy();
    expect(screen.getByRole("heading", { name: "Short" })).toBeTruthy();
    expect(screen.getByText("Input creates output")).toBeTruthy();
    expect(screen.getByRole("heading", { name: "Detail" })).toBeTruthy();
    expect(screen.getByText("The complete derivation detail.")).toBeTruthy();
    expect(screen.getByText("Provides source facts")).toBeTruthy();
    expect(screen.getByText("Creates the result")).toBeTruthy();
  });

  it("tracks Opening and Opened independently for each registered file", async () => {
    let finishFirst: (() => void) | undefined;
    vi.mocked(openRegisteredFile).mockImplementation(
      (path) =>
        new Promise((resolve) => {
          if (path === "docs/input.md") {
            finishFirst = () => resolve({ ok: true, path });
          }
        }),
    );
    render(
      <InspectorPanel
        graph={project()}
        selected={{ kind: "knowledge", id: "nd_input" }}
      />,
    );
    const buttons = screen.getAllByRole("button", { name: "Open" });

    fireEvent.click(buttons[0]);
    expect(openRegisteredFile).toHaveBeenCalledWith("docs/input.md");
    expect(screen.getByText("Opening…")).toBeTruthy();
    expect(screen.queryByText("Opened")).toBeNull();
    await act(async () => finishFirst?.());
    expect(await screen.findByText("Opened")).toBeTruthy();
    const updatedButtons = screen.getAllByRole("button", { name: "Open" });
    expect(updatedButtons).toHaveLength(2);
    expect(updatedButtons[0].closest("li")?.textContent).toContain("Opened");
    expect(updatedButtons[1].closest("li")?.textContent).not.toContain("Opened");
  });

  it("shows a readable error only beside the file whose Open failed", async () => {
    vi.mocked(openRegisteredFile).mockImplementation(async () => {
      throw new Error("The registered file no longer exists.");
    });
    render(
      <InspectorPanel
        graph={project()}
        selected={{ kind: "knowledge", id: "nd_input" }}
      />,
    );

    fireEvent.click(screen.getAllByRole("button", { name: "Open" })[1]);
    expect(openRegisteredFile).toHaveBeenCalledWith("docs/input.svg");
    expect(await screen.findByText("The registered file no longer exists.")).toBeTruthy();
    expect(screen.getAllByRole("button", { name: "Open" })).toHaveLength(2);
  });
});
