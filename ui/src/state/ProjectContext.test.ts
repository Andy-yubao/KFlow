import { describe, expect, it } from "vitest";

import { initialProjectState, projectReducer } from "./ProjectContext";

describe("projectReducer", () => {
  it("review-order selection reveals, selects, and allows locating the Node", () => {
    const filtered = {
      ...initialProjectState,
      searchText: "unrelated",
      statusFilter: "current" as const,
      onlyNeedsReview: true,
    };

    expect(
      projectReducer(filtered, {
        type: "reviewSelected",
        nodeId: "nd_architecture",
      }),
    ).toMatchObject({
      searchText: "",
      statusFilter: "all",
      onlyNeedsReview: false,
      selectedElement: { kind: "knowledge", id: "nd_architecture" },
    });
  });

  it("clears graph highlighting when selection is cleared", () => {
    const selected = {
      ...initialProjectState,
      selectedElement: { kind: "derivation" as const, id: "dv_design" },
    };
    expect(
      projectReducer(selected, { type: "selected", element: null }).selectedElement,
    ).toBeNull();
  });

  it("reuses graph selection and reveal state for current Graph Diff entities", () => {
    const filtered = {
      ...initialProjectState,
      searchText: "unrelated",
      statusFilter: "current" as const,
      onlyNeedsReview: true,
    };
    expect(
      projectReducer(filtered, {
        type: "graphDiffSelected",
        element: { kind: "derivation", id: "dv_changed" },
      }),
    ).toMatchObject({
      searchText: "",
      statusFilter: "all",
      onlyNeedsReview: false,
      selectedElement: { kind: "derivation", id: "dv_changed" },
    });
  });

  it("keeps Graph Diff request failures isolated from the loaded project graph", () => {
    const graph = { schema_version: 2 } as never;
    const loaded = { ...initialProjectState, projectGraph: graph, loading: false };
    const failed = projectReducer(loaded, {
      type: "graphDiffFailed",
      message: "Git unavailable",
      requestId: 0,
    });
    expect(failed.projectGraph).toBe(graph);
    expect(failed.error).toBeNull();
    expect(failed.graphDiffError).toBe("Git unavailable");
  });

  it("toggles the Graph Diff panel independently", () => {
    expect(
      projectReducer(initialProjectState, { type: "graphDiffToggled" })
        .graphDiffCollapsed,
    ).toBe(true);
  });

  it("tracks Graph Diff requests and ignores an older response", () => {
    const selectedCommit = "a1b2c3d4";
    const loading = projectReducer(initialProjectState, {
      type: "graphDiffLoading",
      base: selectedCommit,
      requestId: 2,
    });
    const staleResult = { schema_version: 2 } as never;
    const stale = projectReducer(loading, {
      type: "graphDiffLoaded",
      result: staleResult,
      requestId: 1,
    });
    expect(stale.graphDiff).toBeNull();
    expect(stale.selectedGraphDiffBase).toBe(selectedCommit);
    expect(stale.graphDiffLoading).toBe(true);

    const latestResult = { schema_version: 2 } as never;
    const latest = projectReducer(stale, {
      type: "graphDiffLoaded",
      result: latestResult,
      requestId: 2,
    });
    expect(latest.graphDiff).toBe(latestResult);
    expect(latest.graphDiffLoading).toBe(false);
  });

  it("stores history separately from the main project error", () => {
    const history = { schema_version: 1 } as never;
    const loaded = projectReducer(initialProjectState, {
      type: "gitHistoryLoaded",
      result: history,
      selectedBase: "HEAD",
    });
    expect(loaded.gitHistory).toBe(history);
    expect(loaded.selectedGraphDiffBase).toBe("HEAD");
    expect(loaded.error).toBeNull();
  });

  it("preserves an existing selection and clears only a removed entity", () => {
    const selected = {
      ...initialProjectState,
      selectedElement: { kind: "knowledge" as const, id: "nd_keep" },
    };
    const graph = {
      nodes: [{ id: "nd_keep" }],
      derivations: [],
    } as never;
    const kept = projectReducer(selected, {
      type: "loaded",
      graph,
      reviewOrder: [],
    });
    expect(kept.selectedElement).toEqual({ kind: "knowledge", id: "nd_keep" });

    const removed = projectReducer(kept, {
      type: "loaded",
      graph: { nodes: [], derivations: [] } as never,
      reviewOrder: [],
    });
    expect(removed.selectedElement).toBeNull();
  });

  it("keeps old graph diff visible while a new request is loading", () => {
    const oldDiff = { schema_version: 2 } as never;
    const state = { ...initialProjectState, graphDiff: oldDiff };
    const loading = projectReducer(state, {
      type: "graphDiffLoading",
      base: "HEAD",
      requestId: 1,
    });
    expect(loading.graphDiff).toBe(oldDiff);
    expect(loading.graphDiffLoading).toBe(true);
  });
});
