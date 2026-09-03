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
    selectedGraphDiffBase: "HEAD",
    gitHistoryLoading: false,
    gitHistoryError: null as string | null,
    gitHistory: {
      ok: true,
      available: true,
      schema_version: 1 as const,
      head: {
        commit: "b2c3d4e5",
        short_commit: "bbbbbbb",
        subject: "Current tip",
        committed_at: "2026-08-29T10:00:00+08:00",
      },
      commits: [
        {
          commit: "a1b2c3d4",
          short_commit: "aaaaaaa",
          subject: "Earlier structure",
          committed_at: "2026-08-28T10:00:00+08:00",
        },
      ],
      issues: [],
    },
  },
  toggleGraphDiff: vi.fn(),
  selectGraphDiffElement: vi.fn(),
  selectGraphDiffBase: vi.fn(),
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
    name: "added-derivation",
    short: "Added Derivation",
    detail: "Added detail",
    inputs: [role],
    outputs: [{ ...role, node: "nd_added", name: "Added Node" }],
  };
  return {
    ok: true,
    available: true,
    schema_version: 3,
    base: {
      reference: "HEAD",
      commit: "a1b2c3d4",
      short_commit: "aaaaaaa",
      subject: "baseline graph",
      committed_at: "2026-08-28T10:00:00+08:00",
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
          changed_fields: ["name", "files"],
          before: {
            id: "nd_changed",
            name: "Legacy Architecture",
            files: ["docs/old.md", "docs/shared.md"],
          },
          after: {
            id: "nd_changed",
            name: "System Architecture",
            files: ["docs/new.md", "docs/shared.md"],
          },
        },
      ],
    },
    derivations: {
      added: [derivation],
      removed: [{ ...derivation, id: "dv_removed", short: "Removed Derivation" }],
      changed: [
        {
          id: "dv_changed",
          changed_fields: ["name", "short", "detail", "inputs", "outputs"],
          before: {
            id: "dv_changed",
            name: "legacy-api",
            short: "Legacy API derivation",
            detail: "",
            inputs: [
              {
                node: "nd_requirements",
                name: "Requirements",
                short: "Provides goals",
                detail: "",
              },
              {
                node: "nd_legacy_input",
                name: "Legacy input",
                short: "Provides old limits",
                detail: "Old detail",
              },
            ],
            outputs: [
              {
                node: "nd_api",
                name: "API",
                short: "Defines endpoints",
                detail: "",
              },
              {
                node: "nd_legacy_output",
                name: "Legacy output",
                short: "Records old API",
                detail: "Old output detail",
              },
            ],
          },
          after: {
            id: "dv_changed",
            name: "validated-api",
            short: "Validated API derivation",
            detail: "Produces the current API contract.",
            inputs: [
              {
                node: "nd_requirements",
                name: "Product Requirements",
                short: "Provides validated goals",
                detail: "Includes acceptance criteria",
              },
              {
                node: "nd_constraints",
                name: "Constraints",
                short: "Provides operating limits",
                detail: "",
              },
            ],
            outputs: [
              {
                node: "nd_api",
                name: "Public API",
                short: "Defines validated endpoints",
                detail: "Includes response contracts",
              },
              {
                node: "nd_release_notes",
                name: "Release notes",
                short: "Records current API",
                detail: "",
              },
            ],
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
    expect(screen.getByText("Topological order unchanged.")).toBeTruthy();
  });

  it("shows counts and selects only current added or changed entities", async () => {
    context.state.graphDiff = result();
    context.state.graphDiffCollapsed = false;
    context.selectGraphDiffElement.mockReset();
    const user = userEvent.setup();
    render(<GraphDiffPanel />);

    expect(screen.getByText("baseline graph")).toBeTruthy();
    expect(screen.getAllByText(/2026/).length).toBeGreaterThan(0);
    expect(screen.getByText("Topological order changed.")).toBeTruthy();
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

    for (const text of [
      "Legacy Architecture",
      "System Architecture",
      "docs/old.md",
      "docs/new.md",
      "Legacy API derivation",
      "Validated API derivation",
      "legacy-api",
      "validated-api",
      "Produces the current API contract.",
      "Legacy input",
      "Constraints",
      "Requirements",
      "Product Requirements",
      "Provides goals",
      "Provides validated goals",
      "Legacy output",
      "Release notes",
      "API",
      "Public API",
      "Defines endpoints",
      "Defines validated endpoints",
    ]) {
      expect(screen.getByText(text)).toBeTruthy();
    }
    expect(screen.getAllByText("None").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Inputs")).toHaveLength(1);
    expect(screen.getAllByText("Outputs")).toHaveLength(1);
    expect(screen.queryByText("docs/shared.md")).toBeNull();
    expect(screen.getByText("docs/old.md").closest("li")?.textContent).toContain("-");
    expect(screen.getByText("docs/new.md").closest("li")?.textContent).toContain("+");
    expect(screen.queryByRole("button", { name: /Removed Node/ })).toBeNull();
    expect(screen.queryByRole("button", { name: /Removed Derivation/ })).toBeNull();
    expect(screen.getByText("removed.md")).toBeTruthy();
    expect(screen.getByText("Removed Derivation")).toBeTruthy();
  });

  it("selects an earlier structural commit and updates the title", async () => {
    context.state.graphDiff = result();
    context.state.selectedGraphDiffBase = "a1b2c3d4";
    context.selectGraphDiffBase.mockReset();
    const user = userEvent.setup();
    render(<GraphDiffPanel />);

    expect(
      screen.getByRole("button", { name: /Graph Diff vs aaaaaaa/ }),
    ).toBeTruthy();
    const selector = screen.getByRole("combobox", {
      name: /Compare current working tree against/i,
    });
    expect(screen.getByRole("option", { name: /HEAD.*Current tip/ })).toBeTruthy();
    expect(
      screen.getByRole("option", { name: /aaaaaaa.*Earlier structure.*2026/ }),
    ).toBeTruthy();
    await user.selectOptions(selector, "HEAD");
    expect(context.selectGraphDiffBase).toHaveBeenCalledWith("HEAD");
  });

  it("collapses and isolates unavailable or request-error states", async () => {
    context.state.graphDiff = result();
    context.state.selectedGraphDiffBase = "HEAD";
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
    context.state.graphDiff = null;
    context.state.graphDiffLoading = true;
    rendered.rerender(<GraphDiffPanel />);
    expect(screen.getByText("Loading HEAD graph…")).toBeTruthy();

    context.state.graphDiffLoading = false;
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
