import { describe, expect, it } from "vitest";

import type { StatusNode } from "../types/projectGraph";
import { nodeVisualState } from "./nodeVisualState";

function statusNode(overrides: Partial<StatusNode> = {}): StatusNode {
  return {
    id: "nd_architecture",
    name: "Architecture",
    files: ["docs/architecture.md"],
    changed_files: [],
    status: "valid",
    reasons: [],
    ...overrides,
  };
}

describe("nodeVisualState", () => {
  it("treats a null domain status as unknown before considering reasons", () => {
    expect(nodeVisualState(statusNode({ status: null, reasons: [] }))).toBe(
      "unknown",
    );
    expect(
      nodeVisualState(statusNode({ status: null, reasons: ["unconfirmed"] })),
    ).toBe("unknown");
  });

  it("keeps known nodes without reasons current", () => {
    expect(nodeVisualState(statusNode())).toBe("current");
  });

  it("marks known nodes with reasons for attention", () => {
    expect(nodeVisualState(statusNode({ reasons: ["unconfirmed"] }))).toBe(
      "attention",
    );
  });
});
