import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import type { GraphView } from "../graph/graphView";
import { GraphToolbar } from "./GraphToolbar";

const context = vi.hoisted(() => ({
  state: {
    searchText: "",
    statusFilter: "all",
    onlyNeedsReview: false,
  },
  setSearchText: vi.fn(),
  setStatusFilter: vi.fn(),
  setOnlyNeedsReview: vi.fn(),
  select: vi.fn(),
}));

vi.mock("../state/ProjectContext", () => ({ useProject: () => context }));

function view(searchActive: boolean, searchMatchCount: number): GraphView {
  return {
    visibleKnowledgeNodeIds: [],
    visibleFlowNodeIds: [],
    visibleEdgeIds: [],
    emphasizedNodeIds: [],
    emphasizedEdgeIds: [],
    hasFocus: searchActive && searchMatchCount > 0,
    searchActive,
    searchMatchCount,
  };
}

describe("GraphToolbar search feedback", () => {
  it("keeps actionable controls without duplicate structure or status legends", () => {
    render(<GraphToolbar view={view(false, 0)} />);

    expect(screen.getByRole("searchbox")).toBeTruthy();
    expect(screen.getByRole("combobox", { name: "Status" })).toBeTruthy();
    expect(screen.getByRole("checkbox", { name: "Only needs review" })).toBeTruthy();
    expect(screen.getByRole("button", { name: "Clear selection" })).toBeTruthy();
    expect(screen.queryByLabelText("Graph legend")).toBeNull();
    expect(screen.queryByText("Structure")).toBeNull();
  });

  it("shows the no-match message only for an active search with zero results", async () => {
    const user = userEvent.setup();
    const rendered = render(<GraphToolbar view={view(false, 0)} />);
    expect(screen.queryByRole("status")).toBeNull();

    await user.type(screen.getByRole("searchbox"), "missing");
    expect(context.setSearchText).toHaveBeenCalled();

    context.state.searchText = "missing";
    rendered.rerender(<GraphToolbar view={view(true, 0)} />);
    expect(screen.getByRole("status").textContent).toContain(
      "No matching Nodes or Derivations.",
    );

    rendered.rerender(<GraphToolbar view={view(true, 1)} />);
    expect(screen.queryByRole("status")).toBeNull();
    rendered.rerender(<GraphToolbar view={view(false, 0)} />);
    expect(screen.queryByRole("status")).toBeNull();
  });
});
