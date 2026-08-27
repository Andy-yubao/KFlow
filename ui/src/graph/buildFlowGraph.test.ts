import { describe, expect, it } from "vitest";

import type { ProjectGraphResult } from "../types/projectGraph";
import {
  buildFlowGraph,
  derivationFlowId,
  knowledgeFlowId,
} from "./buildFlowGraph";
import { layoutProjectGraph } from "./layoutGraph";

function manyToManyProject(): ProjectGraphResult {
  return {
    ok: true,
    schema_version: 2,
    project: {
      status: "attention_required",
      node_count: 4,
      derivation_count: 1,
      needs_review_count: 4,
      issue_count: 0,
    },
    nodes: ["a", "b", "c", "d"].map((id) => ({
      id: `nd_${id}`,
      name: id.toUpperCase(),
      files: [`docs/${id}.md`],
      changed_files: [],
      status: "valid",
      reasons: ["unconfirmed"],
    })),
    derivations: [
      {
        id: "dv_design",
        short: "Combine inputs into outputs",
        detail: "A single multi-input, multi-output derivation.",
        inputs: ["a", "b"].map((id) => ({
          node: `nd_${id}`,
          name: id.toUpperCase(),
          short: `Input ${id}`,
          detail: "",
        })),
        outputs: ["c", "d"].map((id) => ({
          node: `nd_${id}`,
          name: id.toUpperCase(),
          short: `Output ${id}`,
          detail: "",
        })),
      },
    ],
    topological_order: ["nd_a", "nd_b", "nd_c", "nd_d"],
    issues: [],
  };
}

describe("buildFlowGraph", () => {
  it("keeps a many-to-many Derivation as one first-class node", () => {
    const graph = buildFlowGraph(manyToManyProject());

    expect(graph.nodes.filter((node) => node.type === "knowledgeNode")).toHaveLength(
      4,
    );
    expect(
      graph.nodes.filter((node) => node.type === "derivationNode"),
    ).toHaveLength(1);
    expect(graph.edges.filter((edge) => edge.data?.kind === "input")).toHaveLength(
      2,
    );
    expect(
      graph.edges.filter((edge) => edge.data?.kind === "output"),
    ).toHaveLength(2);
    expect(graph.edges).toHaveLength(4);
  });

  it("prefixes UI identities so domain IDs cannot collide", () => {
    expect(knowledgeFlowId("same")).toBe("node:same");
    expect(derivationFlowId("same")).toBe("derivation:same");
    expect(knowledgeFlowId("same")).not.toBe(derivationFlowId("same"));
  });

  it("returns deterministic node and edge ordering", () => {
    const project = manyToManyProject();
    expect(buildFlowGraph(project)).toEqual(buildFlowGraph(project));
    expect(buildFlowGraph(project).nodes.map((node) => node.id)).toEqual([
      "node:nd_a",
      "node:nd_b",
      "node:nd_c",
      "node:nd_d",
      "derivation:dv_design",
    ]);
  });

  it("lays inputs, one Derivation, and outputs out without overlap", () => {
    const graph = layoutProjectGraph(buildFlowGraph(manyToManyProject()));
    const positions = new Map(graph.nodes.map((node) => [node.id, node.position]));
    const derivationX = positions.get("derivation:dv_design")?.x ?? 0;

    expect(
      new Set(graph.nodes.map((node) => `${node.position.x}:${node.position.y}`))
        .size,
    ).toBe(5);
    expect(positions.get("node:nd_a")?.x).toBeLessThan(derivationX);
    expect(positions.get("node:nd_b")?.x).toBeLessThan(derivationX);
    expect(positions.get("node:nd_c")?.x).toBeGreaterThan(derivationX);
    expect(positions.get("node:nd_d")?.x).toBeGreaterThan(derivationX);
  });
});
