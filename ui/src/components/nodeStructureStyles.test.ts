import { describe, expect, it } from "vitest";

import { NODE_STRUCTURE_STYLES } from "./KnowledgeNodeCard";

describe("Knowledge Node structure styles", () => {
  it.each([
    ["source", "#3b82f6", "#eff6ff"],
    ["intermediate", "#8b5cf6", "#f5f3ff"],
    ["terminal", "#0f766e", "#f0fdfa"],
    ["isolated", "#94a3b8", "#f8fafc"],
  ])("gives %s an independent categorical accent and light background", (role, accent, background) => {
    const style = NODE_STRUCTURE_STYLES[role as keyof typeof NODE_STRUCTURE_STYLES];

    expect(style["--role-color"]).toBe(accent);
    expect(style["--role-background"]).toBe(background);
  });

  it("uses four distinct accents without encoding status in the structure theme", () => {
    expect(
      new Set(
        Object.values(NODE_STRUCTURE_STYLES).map(
          (style) => style["--role-color"],
        ),
      ).size,
    ).toBe(4);
    expect(
      Object.keys(NODE_STRUCTURE_STYLES).some((key) => key.includes("status")),
    ).toBe(false);
  });
});
