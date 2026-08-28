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
});
