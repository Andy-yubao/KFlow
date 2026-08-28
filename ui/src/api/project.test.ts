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
    const available = {
      ...unavailableDiff,
      available: true,
      base: {
        revision: "HEAD",
        commit: "a".repeat(40),
        short_commit: "aaaaaaa",
        subject: "baseline",
      },
      summary: {
        added_nodes: 0,
        removed_nodes: 0,
        changed_nodes: 0,
        added_derivations: 0,
        removed_derivations: 0,
        changed_derivations: 0,
        topology_changed: false,
      },
    };
    expect(parseGraphDiff(available)).toEqual(available);
  });

  it("rejects incompatible Graph Diff schema and malformed availability", () => {
    expect(() => parseGraphDiff({ ...unavailableDiff, schema_version: 2 })).toThrow(
      "incompatible",
    );
    expect(() =>
      parseGraphDiff({ ...unavailableDiff, available: true }),
    ).toThrow("missing its base or summary");
  });
});
