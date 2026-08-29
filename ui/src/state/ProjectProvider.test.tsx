import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type { GitHistoryResult, GraphDiffResult } from "../types/projectGraph";
import { ProjectProvider, useProject } from "./ProjectContext";

const api = vi.hoisted(() => ({
  fetchProjectGraph: vi.fn(),
  fetchReviewOrder: vi.fn(),
  fetchGitHistory: vi.fn(),
  fetchGraphDiff: vi.fn(),
}));

vi.mock("../api/project", () => api);

const firstCommit = "a".repeat(40);
const secondCommit = "c".repeat(40);

function history(commits = [firstCommit, secondCommit]): GitHistoryResult {
  return {
    ok: true,
    available: true,
    schema_version: 1,
    head: {
      commit: "b".repeat(40),
      short_commit: "bbbbbbb",
      subject: "HEAD",
      committed_at: "2026-08-29T10:00:00+08:00",
    },
    commits: commits.map((commit, index) => ({
      commit,
      short_commit: commit.slice(0, 7),
      subject: `Commit ${index + 1}`,
      committed_at: `2026-08-${28 - index}T10:00:00+08:00`,
    })),
    issues: [],
  };
}

function diff(reference: string): GraphDiffResult {
  return {
    ok: true,
    available: true,
    schema_version: 2,
    base: {
      reference,
      commit: reference === "HEAD" ? "b".repeat(40) : reference,
      short_commit: reference === "HEAD" ? "bbbbbbb" : reference.slice(0, 7),
      subject: reference,
      committed_at: "2026-08-29T10:00:00+08:00",
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
    nodes: { added: [], removed: [], changed: [] },
    derivations: { added: [], removed: [], changed: [] },
    before_topological_order: [],
    after_topological_order: [],
    issues: [],
  };
}

function Probe() {
  const { state, reload, selectGraphDiffBase } = useProject();
  return (
    <div>
      <output aria-label="selected base">{state.selectedGraphDiffBase}</output>
      <output aria-label="loaded diff">{state.graphDiff?.base?.reference ?? "none"}</output>
      <button type="button" onClick={() => selectGraphDiffBase(firstCommit)}>
        Select first
      </button>
      <button type="button" onClick={() => selectGraphDiffBase(secondCommit)}>
        Select second
      </button>
      <button type="button" onClick={() => void reload()}>
        Reload
      </button>
    </div>
  );
}

beforeEach(() => {
  api.fetchProjectGraph.mockReset().mockResolvedValue({ schema_version: 2 });
  api.fetchReviewOrder.mockReset().mockResolvedValue({ review_order: [] });
  api.fetchGitHistory.mockReset().mockResolvedValue(history());
  api.fetchGraphDiff
    .mockReset()
    .mockImplementation(async (base = "HEAD") => diff(base));
});

describe("ProjectProvider Graph Diff history requests", () => {
  it("defaults to HEAD and selecting a commit refreshes only Graph Diff", async () => {
    const user = userEvent.setup();
    render(
      <ProjectProvider>
        <Probe />
      </ProjectProvider>,
    );
    await waitFor(() => expect(screen.getByLabelText("loaded diff").textContent).toBe("HEAD"));

    await user.click(screen.getByRole("button", { name: "Select first" }));
    await waitFor(() =>
      expect(screen.getByLabelText("loaded diff").textContent).toBe(firstCommit),
    );

    expect(api.fetchGraphDiff.mock.calls.map(([base]) => base)).toEqual([
      "HEAD",
      firstCommit,
    ]);
    expect(api.fetchProjectGraph).toHaveBeenCalledTimes(1);
    expect(api.fetchReviewOrder).toHaveBeenCalledTimes(1);
  });

  it("reload preserves a listed commit and falls back to HEAD after it disappears", async () => {
    const user = userEvent.setup();
    render(
      <ProjectProvider>
        <Probe />
      </ProjectProvider>,
    );
    await waitFor(() => expect(screen.getByLabelText("loaded diff").textContent).toBe("HEAD"));
    await user.click(screen.getByRole("button", { name: "Select first" }));
    await waitFor(() =>
      expect(screen.getByLabelText("loaded diff").textContent).toBe(firstCommit),
    );

    await user.click(screen.getByRole("button", { name: "Reload" }));
    await waitFor(() =>
      expect(screen.getByLabelText("loaded diff").textContent).toBe(firstCommit),
    );

    api.fetchGitHistory.mockResolvedValue(history([secondCommit]));
    await user.click(screen.getByRole("button", { name: "Reload" }));
    await waitFor(() => expect(screen.getByLabelText("loaded diff").textContent).toBe("HEAD"));
    expect(screen.getByLabelText("selected base").textContent).toBe("HEAD");
  });
});
