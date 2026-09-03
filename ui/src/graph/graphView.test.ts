import { describe, expect, it } from "vitest";

import type { ProjectGraphResult, StatusNode } from "../types/projectGraph";
import { buildGraphView } from "./graphView";

function node(
  id: string,
  overrides: Partial<StatusNode> = {},
): StatusNode {
  return {
    id,
    name: id.replace("nd_", ""),
    files: [`docs/${id}.md`],
    changed_files: [],
    status: "confirmed",
    reasons: [],
    ...overrides,
  };
}

function project(): ProjectGraphResult {
  const nodes = [
    node("nd_requirements", { status: "valid", reasons: ["unconfirmed"] }),
    node("nd_constraints", { status: null }),
    node("nd_architecture", {
      files: ["docs/system-architecture.md"],
      status: "affected",
      reasons: ["input_changed"],
    }),
    node("nd_api"),
    node("nd_deployment"),
  ];
  return {
    ok: true,
    schema_version: 3,
    project: {
      status: "attention_required",
      node_count: nodes.length,
      derivation_count: 3,
      needs_review_count: 2,
      issue_count: 0,
    },
    nodes,
    derivations: [
      {
        id: "dv_architecture",
        name: "architecture-design",
        short: "Synthesize architecture",
        detail: "Requirements and constraints shape the architecture.",
        inputs: ["nd_requirements", "nd_constraints"].map((id) => ({
          node: id,
          name: id,
          short: "input",
          detail: "",
        })),
        outputs: [
          {
            node: "nd_architecture",
            name: "architecture",
            short: "output",
            detail: "",
          },
        ],
      },
      {
        id: "dv_api",
        name: "api-design",
        short: "Define public API",
        detail: "",
        inputs: [
          {
            node: "nd_architecture",
            name: "architecture",
            short: "input",
            detail: "",
          },
        ],
        outputs: [
          { node: "nd_api", name: "api", short: "output", detail: "" },
        ],
      },
      {
        id: "dv_deploy",
        name: "deployment-planning",
        short: "Plan deployment",
        detail: "",
        inputs: [
          {
            node: "nd_architecture",
            name: "architecture",
            short: "input",
            detail: "",
          },
        ],
        outputs: [
          {
            node: "nd_deployment",
            name: "deployment",
            short: "output",
            detail: "",
          },
        ],
      },
    ],
    topological_order: nodes.map(({ id }) => id),
    issues: [],
  };
}

const defaults = {
  searchText: "",
  statusFilter: "all" as const,
  onlyNeedsReview: false,
  selectedElement: null,
};

describe("buildGraphView", () => {
  it.each([
    ["architecture", "node:nd_architecture"],
    ["docs/system-architecture.md", "node:nd_architecture"],
    ["nd_require", "node:nd_requirements"],
    ["public api", "derivation:dv_api"],
    ["requirements and constraints", "derivation:dv_architecture"],
    ["dv_deploy", "derivation:dv_deploy"],
  ])("searches all public Node and Derivation text fields", (searchText, hit) => {
    const view = buildGraphView(project(), { ...defaults, searchText });
    expect(view.emphasizedNodeIds).toContain(hit);
    expect(view.hasFocus).toBe(true);
    expect(view.searchActive).toBe(true);
    expect(view.searchMatchCount).toBeGreaterThan(0);
  });

  it("treats search as case-insensitive and whitespace-only input as inactive", () => {
    const matched = buildGraphView(project(), {
      ...defaults,
      searchText: "SYSTEM-ARCH",
    });
    expect(matched.emphasizedNodeIds).toContain("node:nd_architecture");

    const whitespace = buildGraphView(project(), {
      ...defaults,
      searchText: "   ",
    });
    expect(whitespace.searchActive).toBe(false);
    expect(whitespace.searchMatchCount).toBe(0);
    expect(whitespace.hasFocus).toBe(false);
  });

  it("keeps normal opacity and reports zero matches for an unmatched search", () => {
    const view = buildGraphView(project(), {
      ...defaults,
      searchText: "does-not-exist",
    });
    expect(view.searchActive).toBe(true);
    expect(view.searchMatchCount).toBe(0);
    expect(view.hasFocus).toBe(false);
    expect(view.visibleKnowledgeNodeIds).toHaveLength(project().nodes.length);

    const filtered = buildGraphView(project(), {
      ...defaults,
      searchText: "does-not-exist",
      onlyNeedsReview: true,
    });
    expect(filtered.hasFocus).toBe(false);
    expect(filtered.visibleKnowledgeNodeIds.sort()).toEqual([
      "node:nd_architecture",
      "node:nd_requirements",
    ]);
  });

  it.each([
    ["current", ["node:nd_api", "node:nd_deployment"]],
    ["attention", ["node:nd_requirements", "node:nd_architecture"]],
    ["unknown", ["node:nd_constraints"]],
  ] as const)("applies the %s status filter through nodeVisualState", (statusFilter, visible) => {
    const view = buildGraphView(project(), { ...defaults, statusFilter });
    expect(view.visibleKnowledgeNodeIds.sort()).toEqual([...visible].sort());
  });

  it("shows only nodes whose public reasons require review", () => {
    const view = buildGraphView(project(), {
      ...defaults,
      onlyNeedsReview: true,
    });
    expect(view.visibleKnowledgeNodeIds.sort()).toEqual([
      "node:nd_architecture",
      "node:nd_requirements",
    ]);
  });

  it("keeps a Derivation only while at least one related Node is visible", () => {
    const view = buildGraphView(project(), {
      ...defaults,
      statusFilter: "current",
    });
    expect(view.visibleFlowNodeIds).toContain("derivation:dv_api");
    expect(view.visibleFlowNodeIds).toContain("derivation:dv_deploy");
    expect(view.visibleFlowNodeIds).not.toContain("derivation:dv_architecture");
  });

  it("highlights a Knowledge Node, producer/consumers, and direct neighbors", () => {
    const view = buildGraphView(project(), {
      ...defaults,
      selectedElement: { kind: "knowledge", id: "nd_architecture" },
    });
    expect(view.emphasizedNodeIds.sort()).toEqual([
      "derivation:dv_api",
      "derivation:dv_architecture",
      "derivation:dv_deploy",
      "node:nd_api",
      "node:nd_architecture",
      "node:nd_constraints",
      "node:nd_deployment",
      "node:nd_requirements",
    ]);
    expect(view.emphasizedEdgeIds).toHaveLength(7);
  });

  it("highlights a Derivation, all inputs/outputs, and only its role edges", () => {
    const view = buildGraphView(project(), {
      ...defaults,
      selectedElement: { kind: "derivation", id: "dv_architecture" },
    });
    expect(view.emphasizedNodeIds.sort()).toEqual([
      "derivation:dv_architecture",
      "node:nd_architecture",
      "node:nd_constraints",
      "node:nd_requirements",
    ]);
    expect(view.emphasizedEdgeIds).toHaveLength(3);
  });

  it("restores every visible element after selection and search are cleared", () => {
    const view = buildGraphView(project(), defaults);
    expect(view.hasFocus).toBe(false);
    expect(view.emphasizedNodeIds.sort()).toEqual(
      [...view.visibleFlowNodeIds].sort(),
    );
  });
});
