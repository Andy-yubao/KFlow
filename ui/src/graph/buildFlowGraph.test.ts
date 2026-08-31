import { describe, expect, it } from "vitest";

import type { ProjectGraphResult } from "../types/projectGraph";
import {
  buildFlowGraph,
  derivationFlowId,
  knowledgeFlowId,
} from "./buildFlowGraph";
import {
  DERIVATION_NODE_SIZE,
  KNOWLEDGE_NODE_SIZE,
  layoutProjectGraph,
} from "./layoutGraph";

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

function projectShape(inputCount: number, outputCount: number): ProjectGraphResult {
  const inputs = Array.from({ length: inputCount }, (_, index) => `i${index + 1}`);
  const outputs = Array.from({ length: outputCount }, (_, index) => `o${index + 1}`);
  const ids = [...inputs, ...outputs];
  return {
    ...manyToManyProject(),
    project: {
      ...manyToManyProject().project,
      node_count: ids.length,
      needs_review_count: ids.length,
    },
    nodes: ids.map((id) => ({
      id: `nd_${id}`,
      name: id.toUpperCase(),
      files: [`docs/${id}.md`],
      changed_files: [],
      status: "valid",
      reasons: ["unconfirmed"],
    })),
    derivations: [
      {
        ...manyToManyProject().derivations[0],
        inputs: inputs.map((id) => ({
          node: `nd_${id}`,
          name: id.toUpperCase(),
          short: `Input ${id}`,
          detail: "",
        })),
        outputs: outputs.map((id) => ({
          node: `nd_${id}`,
          name: id.toUpperCase(),
          short: `Output ${id}`,
          detail: "",
        })),
      },
    ],
    topological_order: ids.map((id) => `nd_${id}`),
  };
}

describe("buildFlowGraph", () => {
  it("keeps Dagre dimensions aligned with the fixed card sizes", () => {
    expect(KNOWLEDGE_NODE_SIZE).toEqual({ width: 240, height: 120 });
    expect(DERIVATION_NODE_SIZE).toEqual({ width: 32, height: 32 });
    expect(DERIVATION_NODE_SIZE.width).toBeLessThanOrEqual(48);
    expect(DERIVATION_NODE_SIZE.width).toBeLessThan(
      KNOWLEDGE_NODE_SIZE.width / 4,
    );
  });

  it.each([
    ["1-to-1", 1, 1],
    ["1-to-N", 1, 2],
    ["N-to-1", 2, 1],
    ["N-to-M", 2, 2],
  ])(
    "keeps %s as one Derivation with role edges rather than Cartesian edges",
    (_label, inputCount, outputCount) => {
      const graph = buildFlowGraph(projectShape(inputCount, outputCount));

      expect(
        graph.nodes.filter((node) => node.type === "derivationNode"),
      ).toHaveLength(1);
      expect(graph.edges.filter((edge) => edge.data?.kind === "input")).toHaveLength(
        inputCount,
      );
      expect(
        graph.edges.filter((edge) => edge.data?.kind === "output"),
      ).toHaveLength(outputCount);
      expect(graph.edges).toHaveLength(inputCount + outputCount);
    },
  );

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

  it("derives Source, Intermediate, Terminal, and Isolated roles from the bipartite graph", () => {
    const project = manyToManyProject();
    project.nodes.push({
      id: "nd_isolated",
      name: "Isolated",
      files: ["docs/isolated.md"],
      changed_files: [],
      status: "valid",
      reasons: [],
    });
    project.nodes.push({
      id: "nd_final",
      name: "Final",
      files: ["docs/final.md"],
      changed_files: [],
      status: "valid",
      reasons: [],
    });
    project.derivations.push({
      id: "dv_publish",
      short: "Publish output",
      detail: "",
      inputs: [
        { node: "nd_c", name: "C", short: "Input C", detail: "" },
      ],
      outputs: [
        { node: "nd_final", name: "Final", short: "Final", detail: "" },
      ],
    });
    project.topological_order.push("nd_final", "nd_isolated");

    const knowledge = buildFlowGraph(project).nodes.filter(
      (node) => node.data.kind === "knowledge",
    );
    const roleById = new Map(
      knowledge.map((node) => [
        node.id,
        node.data.kind === "knowledge" ? node.data.role : "",
      ]),
    );

    expect(roleById).toEqual(
      new Map([
        ["node:nd_a", "source"],
        ["node:nd_b", "source"],
        ["node:nd_c", "intermediate"],
        ["node:nd_d", "terminal"],
        ["node:nd_final", "terminal"],
        ["node:nd_isolated", "isolated"],
      ]),
    );
  });

  it("uses the maximum input layer through forks and joins", () => {
    const project = manyToManyProject();
    project.nodes.push(
      {
        id: "nd_e",
        name: "E",
        files: ["docs/e.md"],
        changed_files: [],
        status: "valid",
        reasons: [],
      },
      {
        id: "nd_isolated",
        name: "Isolated",
        files: ["docs/isolated.md"],
        changed_files: [],
        status: "valid",
        reasons: [],
      },
    );
    project.derivations.push({
      id: "dv_join",
      short: "Join branches",
      detail: "",
      inputs: [
        { node: "nd_a", name: "A", short: "Direct", detail: "" },
        { node: "nd_c", name: "C", short: "Derived", detail: "" },
      ],
      outputs: [{ node: "nd_e", name: "E", short: "Joined", detail: "" }],
    });
    project.topological_order.push("nd_e", "nd_isolated");

    const layerById = new Map(
      buildFlowGraph(project).nodes.flatMap((node) =>
        node.data.kind === "knowledge"
          ? [[node.data.node.id, node.data.layer] as const]
          : [],
      ),
    );

    expect(layerById.get("nd_a")).toBe(0);
    expect(layerById.get("nd_c")).toBe(1);
    expect(layerById.get("nd_d")).toBe(1);
    expect(layerById.get("nd_e")).toBe(2);
    expect(layerById.get("nd_isolated")).toBe(0);
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
