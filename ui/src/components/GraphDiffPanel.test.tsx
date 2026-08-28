import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import type { GraphDiffResult } from "../types/projectGraph";
import { GraphDiffPanel } from "./GraphDiffPanel";

const context = vi.hoisted(() => ({
  state: {
    graphDiff: null as GraphDiffResult | null,
    graphDiffLoading: false,
    graphDiffError: null as string | null,
    graphDiffCollapsed: false,
  },
  toggleGraphDiff: vi.fn(),
  selectGraphDiffElement: vi.fn(),
}));

vi.mock("../state/ProjectContext", () => ({ useProject: () => context }));

function result(): GraphDiffResult {
  const role = {
    node: "nd_input",
    name: "Input",
    short: "Uses input",
    detail: "",
  };
  const derivation = {
    id: "dv_added",
    short: "Added Derivation",
    detail: "Added detail",
    inputs: [role],
    outputs: [{ ...role, node: "nd_added", name: "Added Node" }],
  };
  return {
    ok: true,
    available: true,
    schema_version: 1,
    base: {
      revision: "HEAD",
      commit: "a".repeat(40),
      short_commit: "aaaaaaa",
      subject: "baseline graph",
    },
    summary: {
      added_nodes: 1,
      removed_nodes: 1,
      changed_nodes: 1,
      added_derivations: 1,
      removed_derivations: 1,
      changed_derivations: 1,
      topology_changed: true,
    },
    nodes: {
      added: [{ id: "nd_added", name: "Added Node", files: ["added.md"] }],
      removed: [
        { id: "nd_removed", name: "Removed Node", files: ["removed.md"] },
      ],
      changed: [
        {
          id: "nd_changed",
          changed_fields: ["name"],
          before: { id: "nd_changed", name: "Before", files: ["changed.md"] },
          after: { id: "nd_changed", name: "Changed Node", files: ["changed.md"] },
        },
      ],
    },
    derivations: {
      added: [derivation],
      removed: [{ ...derivation, id: "dv_removed", short: "Removed Derivation" }],
      changed: [
        {
          id: "dv_changed",
          changed_fields: ["detail"],
          before: { ...derivation, id: "dv_changed", detail: "Before" },
          after: {
            ...derivation,
            id: "dv_changed",
            short: "Changed Derivation",
            detail: "After",
          },
        },
      ],
    },
    before_topological_order: ["nd_input"],
    after_topological_order: ["nd_input", "nd_added"],
    issues: [],
  };
}

describe("GraphDiffPanel", () => {
  it("shows an explicit empty structural diff", () => {
    const empty = result();
    empty.summary = {
      added_nodes: 0,
      removed_nodes: 0,
      changed_nodes: 0,
      added_derivations: 0,
      removed_derivations: 0,
      changed_derivations: 0,
      topology_changed: false,
    };
    empty.nodes = { added: [], removed: [], changed: [] };
    empty.derivations = { added: [], removed: [], changed: [] };
    context.state.graphDiff = empty;
    context.state.graphDiffCollapsed = false;
    render(<GraphDiffPanel />);

    expect(screen.getByText("No structural graph changes since HEAD.")).toBeTruthy();
    expect(screen.getByText("Topology unchanged.")).toBeTruthy();
  });

  it("shows counts and selects only current added or changed entities", async () => {
    context.state.graphDiff = result();
    context.state.graphDiffCollapsed = false;
    context.selectGraphDiffElement.mockReset();
    const user = userEvent.setup();
    render(<GraphDiffPanel />);

    expect(screen.getByText("baseline graph")).toBeTruthy();
    expect(screen.getByText("Topology changed.")).toBeTruthy();
    for (const label of [
      "Added Nodes",
      "Removed Nodes",
      "Changed Nodes",
      "Added Derivations",
      "Removed Derivations",
      "Changed Derivations",
    ]) {
      expect(screen.getByText(label)).toBeTruthy();
    }

    const addedNodeButton = screen
      .getAllByRole("button")
      .find((button) => button.textContent?.includes("nd_added"));
    const changedNodeButton = screen
      .getAllByRole("button")
      .find((button) => button.textContent?.includes("nd_changed"));
    const addedDerivationButton = screen
      .getAllByRole("button")
      .find((button) => button.textContent?.includes("dv_added"));
    const changedDerivationButton = screen
      .getAllByRole("button")
      .find((button) => button.textContent?.includes("dv_changed"));
    expect(addedNodeButton).toBeDefined();
    expect(changedNodeButton).toBeDefined();
    expect(addedDerivationButton).toBeDefined();
    expect(changedDerivationButton).toBeDefined();
    await user.click(addedNodeButton!);
    await user.click(changedNodeButton!);
    await user.click(addedDerivationButton!);
    await user.click(changedDerivationButton!);
    expect(context.selectGraphDiffElement).toHaveBeenNthCalledWith(1, {
      kind: "knowledge",
      id: "nd_added",
    });
    expect(context.selectGraphDiffElement).toHaveBeenNthCalledWith(2, {
      kind: "knowledge",
      id: "nd_changed",
    });
    expect(context.selectGraphDiffElement).toHaveBeenNthCalledWith(3, {
      kind: "derivation",
      id: "dv_added",
    });
    expect(context.selectGraphDiffElement).toHaveBeenNthCalledWith(4, {
      kind: "derivation",
      id: "dv_changed",
    });
    expect(screen.queryByRole("button", { name: /Removed Node/ })).toBeNull();
    expect(screen.queryByRole("button", { name: /Removed Derivation/ })).toBeNull();
    expect(screen.getByText("removed.md")).toBeTruthy();
    expect(screen.getByText("Removed Derivation")).toBeTruthy();
  });

  it("collapses and isolates unavailable or request-error states", async () => {
    context.state.graphDiff = result();
    context.state.graphDiffCollapsed = false;
    context.state.graphDiffError = null;
    const user = userEvent.setup();
    const rendered = render(<GraphDiffPanel />);
    await user.click(screen.getByRole("button", { name: /Graph Diff vs HEAD/ }));
    expect(context.toggleGraphDiff).toHaveBeenCalled();

    context.state.graphDiffCollapsed = true;
    rendered.rerender(<GraphDiffPanel />);
    expect(screen.queryByText("baseline graph")).toBeNull();

    context.state.graphDiffCollapsed = false;
    context.state.graphDiff = {
      ...result(),
      available: false,
      base: null,
      summary: null,
      nodes: { added: [], removed: [], changed: [] },
      derivations: { added: [], removed: [], changed: [] },
      issues: [
        { code: "git_history_unavailable", message: "No HEAD commit.", references: [] },
      ],
    };
    rendered.rerender(<GraphDiffPanel />);
    expect(screen.getByText("No HEAD commit.")).toBeTruthy();

    context.state.graphDiffError = "Graph Diff request failed.";
    rendered.rerender(<GraphDiffPanel />);
    expect(screen.getByRole("alert").textContent).toBe("Graph Diff request failed.");
  });
});
