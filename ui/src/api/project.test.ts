import { describe, expect, it, vi } from "vitest";

import {
  fetchGraphDiff,
  fetchGitHistory,
  fetchProjectGraph,
  fetchRevision,
  fetchReviewOrder,
  openRegisteredFile,
  parseGitHistory,
  parseGraphDiff,
  parseRevision,
} from "./project";

const headObjectId = "b2c3d4e5";
const earlierObjectId = "a1b2c3d4";

const unavailableDiff = {
  ok: true,
  available: false,
  schema_version: 2,
  base: null,
  summary: null,
  nodes: { added: [], removed: [], changed: [] },
  derivations: { added: [], removed: [], changed: [] },
  before_topological_order: [],
  after_topological_order: [],
  issues: [],
};

describe("read request cancellation", () => {
  it("passes the caller AbortSignal to every read endpoint", async () => {
    const history = {
      ok: true,
      available: false,
      schema_version: 1,
      head: null,
      commits: [],
      issues: [],
    };
    const bodies = new Map<string, object>([
      ["/api/project", { schema_version: 2, nodes: [], derivations: [] }],
      [
        "/api/review-order",
        { schema_version: 3, review_order: [], issues: [] },
      ],
      ["/api/git-history", history],
      ["/api/graph-diff", unavailableDiff],
      [
        "/api/revision",
        { ok: true, project_revision: "project-1", git_revision: "git-1" },
      ],
    ]);
    const fetcher = vi.fn(async (url: string, _options?: RequestInit) =>
      new Response(JSON.stringify(bodies.get(url)), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );
    vi.stubGlobal("fetch", fetcher);
    const controller = new AbortController();

    await Promise.all([
      fetchProjectGraph(controller.signal),
      fetchReviewOrder(controller.signal),
      fetchGitHistory(controller.signal),
      fetchGraphDiff("HEAD", controller.signal),
      fetchRevision(controller.signal),
    ]);

    expect(fetcher).toHaveBeenCalledTimes(5);
    for (const [, options] of fetcher.mock.calls) {
      expect(options?.signal).toBe(controller.signal);
    }
    vi.unstubAllGlobals();
  });
});

describe("parseRevision", () => {
  it("accepts opaque non-empty project and Git tokens", () => {
    const revision = {
      ok: true,
      project_revision: "opaque-project-token",
      git_revision: "opaque-git-token",
    };
    expect(parseRevision(revision)).toEqual(revision);
  });

  it.each([
    { ok: false, project_revision: "p", git_revision: "g" },
    { ok: true, project_revision: "", git_revision: "g" },
    { ok: true, project_revision: "p", git_revision: 3 },
  ])("rejects incompatible revision results", (revision) => {
    expect(() => parseRevision(revision)).toThrow("incompatible result");
  });
});

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
    schema_version: 2,
    base: {
      reference: "HEAD",
      commit: earlierObjectId,
      short_commit: "aaaaaaa",
      subject: "baseline",
      committed_at: "2026-08-29T10:00:00+08:00",
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
    ["empty reference", (value: any) => { value.base.reference = ""; }],
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

  it.each([
    ["added Nodes", (value: any) => { value.nodes.added = [{ id: "nd_x", name: "X", files: [] }]; }],
    ["removed Nodes", (value: any) => { value.nodes.removed = [{ id: "nd_x", name: "X", files: [] }]; }],
    ["changed Nodes", (value: any) => { value.nodes.changed = availableDiff().nodes.changed; }],
    ["added Derivations", (value: any) => { value.derivations.added = availableDiff().derivations.added; }],
    ["removed Derivations", (value: any) => { value.derivations.removed = availableDiff().derivations.removed; }],
    ["changed Derivations", (value: any) => { value.derivations.changed = availableDiff().derivations.changed; }],
    ["before order", (value: any) => { value.before_topological_order = ["nd_x"]; }],
    ["after order", (value: any) => { value.after_topological_order = ["nd_x"]; }],
  ])("rejects unavailable results containing %s", (_label, mutate) => {
    const invalid = structuredClone(unavailableDiff);
    mutate(invalid);
    expect(() => parseGraphDiff(invalid)).toThrow("incompatible result");
  });
});

describe("parseGitHistory", () => {
  function history() {
    return {
      ok: true,
      available: true,
      schema_version: 1,
      head: {
        commit: headObjectId,
        short_commit: "bbbbbbb",
        subject: "Current tip",
        committed_at: "2026-08-29T10:00:00+08:00",
      },
      commits: [
        {
          commit: earlierObjectId,
          short_commit: "aaaaaaa",
          subject: "Structural change",
          committed_at: "2026-08-28T10:00:00+08:00",
        },
      ],
      issues: [],
    };
  }

  it("accepts available and unavailable history", () => {
    expect(parseGitHistory(history())).toEqual(history());
    const unavailable = {
      ok: true,
      available: false,
      schema_version: 1,
      head: null,
      commits: [],
      issues: [
        { code: "git_history_unavailable", message: "No Git.", references: [] },
      ],
    };
    expect(parseGitHistory(unavailable)).toEqual(unavailable);
  });

  it.each([
    ["wrong schema", (value: any) => { value.schema_version = 2; }],
    ["invalid SHA", (value: any) => { value.commits[0].commit = "HEAD~3"; }],
    ["missing time", (value: any) => { delete value.commits[0].committed_at; }],
    ["duplicate commit", (value: any) => { value.commits.push(value.commits[0]); }],
    ["HEAD duplicated", (value: any) => { value.commits[0].commit = value.head.commit; }],
  ])("rejects %s", (_label, mutate) => {
    const invalid = history();
    mutate(invalid);
    expect(() => parseGitHistory(invalid)).toThrow("incompatible result");
  });
});

describe("fetchGraphDiff", () => {
  it("uses the default endpoint for HEAD and URLSearchParams for a commit", async () => {
    const fetcher = vi.fn(async (_url: string) =>
      new Response(JSON.stringify(availableDiff()), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );
    vi.stubGlobal("fetch", fetcher);

    await fetchGraphDiff();
    await fetchGraphDiff("HEAD");
    await fetchGraphDiff(earlierObjectId);

    expect(fetcher.mock.calls.map(([url]) => url)).toEqual([
      "/api/graph-diff",
      "/api/graph-diff",
      `/api/graph-diff?base=${earlierObjectId}`,
    ]);
    vi.unstubAllGlobals();
  });

  it("requests Git history from its dedicated endpoint", async () => {
    const body = {
      ok: true,
      available: false,
      schema_version: 1,
      head: null,
      commits: [],
      issues: [],
    };
    const fetcher = vi.fn(async (_url: string) =>
      new Response(JSON.stringify(body), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );
    vi.stubGlobal("fetch", fetcher);

    await expect(fetchGitHistory()).resolves.toEqual(body);
    expect(fetcher).toHaveBeenCalledWith("/api/git-history", {
      method: "GET",
      headers: { Accept: "application/json" },
      signal: undefined,
    });
    vi.unstubAllGlobals();
  });
});
