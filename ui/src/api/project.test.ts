import { describe, expect, it, vi } from "vitest";

import { openRegisteredFile, parseGraphDiff } from "./project";

const unavailableDiff = {
  ok: true,
  available: false,
  schema_version: 1,
  base: null,
  summary: null,
  nodes: { added: [], removed: [], changed: [] },
  derivations: { added: [], removed: [], changed: [] },
  before_topological_order: [],
  after_topological_order: [],
  issues: [],
};

function availableDiff() {
  const node = { id: "nd_node", name: "Node", files: ["docs/node.md"] };
  const role = {
    node: "nd_node",
    name: "Node",
    short: "Provides facts",
    detail: "",
  };
  const derivation = {
    id: "dv_derivation",
    short: "Derives facts",
    detail: "",
    inputs: [role],
    outputs: [{ ...role, node: "nd_output" }],
  };
  return {
    ok: true,
    available: true,
    schema_version: 1,
    base: {
      revision: "HEAD",
      commit: "commit-object-id",
      short_commit: "commit",
      subject: "baseline",
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
      added: [node],
      removed: [{ ...node, id: "nd_removed" }],
      changed: [
        {
          id: "nd_changed",
          changed_fields: ["name"],
          before: { ...node, id: "nd_changed", name: "Before" },
          after: { ...node, id: "nd_changed", name: "After" },
        },
      ],
    },
    derivations: {
      added: [derivation],
      removed: [{ ...derivation, id: "dv_removed" }],
      changed: [
        {
          id: "dv_changed",
          changed_fields: ["detail"],
          before: { ...derivation, id: "dv_changed", detail: "Before" },
          after: { ...derivation, id: "dv_changed", detail: "After" },
        },
      ],
    },
    before_topological_order: ["nd_node"],
    after_topological_order: ["nd_node", "nd_output"],
    issues: [
      { code: "example", message: "Example issue", references: ["nd_node"] },
    ],
  };
}

describe("openRegisteredFile", () => {
  it("calls the restricted local API with the registered path", async () => {
    const fetcher = vi.fn(async () =>
      new Response(JSON.stringify({ ok: true, path: "docs/architecture.md" }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );

    await expect(
      openRegisteredFile("docs/architecture.md", fetcher),
    ).resolves.toEqual({ ok: true, path: "docs/architecture.md" });
    expect(fetcher).toHaveBeenCalledWith("/api/open-file", {
      method: "POST",
      headers: {
        Accept: "application/json",
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ path: "docs/architecture.md" }),
    });
  });
});

describe("parseGraphDiff", () => {
  it("accepts available, unavailable, and empty diff results", () => {
    expect(parseGraphDiff(unavailableDiff)).toEqual(unavailableDiff);
    const available = availableDiff();
    expect(parseGraphDiff(available)).toEqual(available);
    const empty = {
      ...available,
      summary: {
        added_nodes: 0,
        removed_nodes: 0,
        changed_nodes: 0,
        added_derivations: 0,
        removed_derivations: 0,
        changed_derivations: 0,
        topology_changed: false,
      },
      nodes: { added: [], removed: [], changed: [] },
      derivations: { added: [], removed: [], changed: [] },
    };
    expect(parseGraphDiff(empty)).toEqual(empty);
  });

  it.each([
    ["non-boolean ok", (value: any) => { value.ok = "yes"; }],
    ["non-HEAD revision", (value: any) => { value.base.revision = "main"; }],
    ["non-string commit", (value: any) => { value.base.commit = 42; }],
    ["non-integer summary count", (value: any) => { value.summary.added_nodes = 1.5; }],
    ["negative summary count", (value: any) => { value.summary.added_nodes = -1; }],
    ["non-boolean topology", (value: any) => { value.summary.topology_changed = "yes"; }],
    ["Node without files", (value: any) => { delete value.nodes.added[0].files; }],
    ["role without node", (value: any) => { delete value.derivations.added[0].inputs[0].node; }],
    ["unknown changed Node field", (value: any) => { value.nodes.changed[0].changed_fields = ["status"]; }],
    ["mismatched Changed Node id", (value: any) => { value.nodes.changed[0].before.id = "other"; }],
    ["Changed Derivation without after", (value: any) => { delete value.derivations.changed[0].after; }],
    ["mismatched summary count", (value: any) => { value.summary.added_nodes = 2; }],
    ["available without summary", (value: any) => { value.summary = null; }],
  ])("rejects %s", (_label, mutate) => {
    const invalid = structuredClone(availableDiff());
    mutate(invalid);
    expect(() => parseGraphDiff(invalid)).toThrow("incompatible result");
  });

  it("rejects an unavailable result with a non-null base", () => {
    expect(() =>
      parseGraphDiff({
        ...unavailableDiff,
        base: availableDiff().base,
      }),
    ).toThrow("incompatible result");
  });
});
