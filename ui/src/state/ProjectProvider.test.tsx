import { act, render, screen, waitFor } from "@testing-library/react";
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

const headCommit = "b2c3d4e5";
const firstCommit = "a1b2c3d4";
const secondCommit = "c3d4e5f6";

function history(commits = [firstCommit, secondCommit]): GitHistoryResult {
  return {
    ok: true,
    available: true,
    schema_version: 1,
    head: {
      commit: headCommit,
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
      commit: reference === "HEAD" ? headCommit : reference,
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

function deferred<T>() {
  let resolve!: (value: T | PromiseLike<T>) => void;
  let reject!: (reason?: unknown) => void;
  const promise = new Promise<T>((resolvePromise, rejectPromise) => {
    resolve = resolvePromise;
    reject = rejectPromise;
  });
  return { promise, resolve, reject };
}

function Probe() {
  const { state, reload, selectGraphDiffBase } = useProject();
  return (
    <div>
      <output aria-label="selected base">{state.selectedGraphDiffBase}</output>
      <output aria-label="loaded diff">{state.graphDiff?.base?.reference ?? "none"}</output>
      <output aria-label="project marker">
        {(state.projectGraph as { marker?: string } | null)?.marker ?? "none"}
      </output>
      <output aria-label="review order">{state.reviewOrder.join(",")}</output>
      <output aria-label="history head">
        {state.gitHistory?.head?.commit ?? "none"}
      </output>
      <output aria-label="history loading">{String(state.gitHistoryLoading)}</output>
      <output aria-label="history error">{state.gitHistoryError ?? "none"}</output>
      <output aria-label="core loading">{String(state.loading)}</output>
      <output aria-label="core error">{state.error ?? "none"}</output>
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
  it("loads core project data without waiting for pending Git history", async () => {
    const historyRequest = deferred<GitHistoryResult>();
    api.fetchProjectGraph.mockResolvedValue({ schema_version: 2, marker: "core" });
    api.fetchReviewOrder.mockResolvedValue({ review_order: ["nd_core"] });
    api.fetchGitHistory.mockReturnValue(historyRequest.promise);

    render(
      <ProjectProvider>
        <Probe />
      </ProjectProvider>,
    );

    await waitFor(() =>
      expect(screen.getByLabelText("project marker").textContent).toBe("core"),
    );
    expect(screen.getByLabelText("review order").textContent).toBe("nd_core");
    expect(screen.getByLabelText("core loading").textContent).toBe("false");
    expect(screen.getByLabelText("history loading").textContent).toBe("true");
    expect(api.fetchGraphDiff).not.toHaveBeenCalled();

    historyRequest.resolve(history());
    await waitFor(() =>
      expect(screen.getByLabelText("loaded diff").textContent).toBe("HEAD"),
    );
    expect(screen.getByLabelText("history loading").textContent).toBe("false");
  });

  it("keeps loaded core data when Git history fails", async () => {
    api.fetchProjectGraph.mockResolvedValue({ schema_version: 2, marker: "core" });
    api.fetchReviewOrder.mockResolvedValue({ review_order: ["nd_core"] });
    api.fetchGitHistory.mockRejectedValue(new Error("History unavailable"));

    render(
      <ProjectProvider>
        <Probe />
      </ProjectProvider>,
    );

    await waitFor(() =>
      expect(screen.getByLabelText("loaded diff").textContent).toBe("HEAD"),
    );
    expect(screen.getByLabelText("project marker").textContent).toBe("core");
    expect(screen.getByLabelText("review order").textContent).toBe("nd_core");
    expect(screen.getByLabelText("core error").textContent).toBe("none");
    expect(screen.getByLabelText("history error").textContent).toBe(
      "History unavailable",
    );
    expect(screen.getByLabelText("selected base").textContent).toBe("HEAD");
    expect(api.fetchGraphDiff).toHaveBeenCalledTimes(1);
  });

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

  it("keeps the latest commit when rapid selections resolve out of order", async () => {
    const user = userEvent.setup();
    const firstRequest = deferred<GraphDiffResult>();
    const secondRequest = deferred<GraphDiffResult>();
    let firstSignal: AbortSignal | undefined;
    api.fetchGraphDiff.mockImplementation(
      async (base = "HEAD", signal?: AbortSignal) => {
        if (base === firstCommit) {
          firstSignal = signal;
          return firstRequest.promise;
        }
        if (base === secondCommit) return secondRequest.promise;
        return diff(base);
      },
    );
    render(
      <ProjectProvider>
        <Probe />
      </ProjectProvider>,
    );
    await waitFor(() =>
      expect(screen.getByLabelText("loaded diff").textContent).toBe("HEAD"),
    );

    await user.click(screen.getByRole("button", { name: "Select first" }));
    await waitFor(() => expect(firstSignal).toBeDefined());
    await user.click(screen.getByRole("button", { name: "Select second" }));
    expect(firstSignal?.aborted).toBe(true);

    secondRequest.resolve(diff(secondCommit));
    await waitFor(() =>
      expect(screen.getByLabelText("loaded diff").textContent).toBe(secondCommit),
    );
    await act(async () => {
      firstRequest.resolve(diff(firstCommit));
      await firstRequest.promise;
    });
    expect(screen.getByLabelText("loaded diff").textContent).toBe(secondCommit);

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
      expect(api.fetchGitHistory).toHaveBeenCalledTimes(2),
    );
    await waitFor(() =>
      expect(api.fetchGraphDiff).toHaveBeenCalledTimes(3),
    );
    expect(api.fetchGraphDiff).toHaveBeenLastCalledWith(
      firstCommit,
      expect.any(AbortSignal),
    );
    expect(screen.getByLabelText("selected base").textContent).toBe(firstCommit);
    expect(screen.getByLabelText("loaded diff").textContent).toBe(firstCommit);

    api.fetchGitHistory.mockResolvedValue(history([secondCommit]));
    await user.click(screen.getByRole("button", { name: "Reload" }));
    await waitFor(() =>
      expect(api.fetchGitHistory).toHaveBeenCalledTimes(3),
    );
    await waitFor(() =>
      expect(api.fetchGraphDiff).toHaveBeenCalledTimes(4),
    );
    expect(api.fetchGraphDiff).toHaveBeenLastCalledWith(
      "HEAD",
      expect.any(AbortSignal),
    );
    await waitFor(() =>
      expect(screen.getByLabelText("loaded diff").textContent).toBe("HEAD"),
    );
    expect(screen.getByLabelText("selected base").textContent).toBe("HEAD");
  });

  it("ignores every stale result from an older overlapping reload", async () => {
    const user = userEvent.setup();
    render(
      <ProjectProvider>
        <Probe />
      </ProjectProvider>,
    );
    await waitFor(() =>
      expect(screen.getByLabelText("loaded diff").textContent).toBe("HEAD"),
    );
    await user.click(screen.getByRole("button", { name: "Select second" }));
    await waitFor(() =>
      expect(screen.getByLabelText("loaded diff").textContent).toBe(secondCommit),
    );

    const firstProject = deferred<{ schema_version: number; marker: string }>();
    const secondProject = deferred<{ schema_version: number; marker: string }>();
    const firstReview = deferred<{ review_order: string[] }>();
    const secondReview = deferred<{ review_order: string[] }>();
    const firstHistory = deferred<GitHistoryResult>();
    const secondHistory = deferred<GitHistoryResult>();
    const secondDiff = deferred<GraphDiffResult>();
    let firstProjectSignal: AbortSignal | undefined;
    let firstHistorySignal: AbortSignal | undefined;

    api.fetchProjectGraph.mockReset()
      .mockImplementationOnce((signal?: AbortSignal) => {
        firstProjectSignal = signal;
        return firstProject.promise;
      })
      .mockImplementationOnce(() => secondProject.promise);
    api.fetchReviewOrder.mockReset()
      .mockImplementationOnce(() => firstReview.promise)
      .mockImplementationOnce(() => secondReview.promise);
    api.fetchGitHistory.mockReset()
      .mockImplementationOnce((signal?: AbortSignal) => {
        firstHistorySignal = signal;
        return firstHistory.promise;
      })
      .mockImplementationOnce(() => secondHistory.promise);
    api.fetchGraphDiff.mockReset().mockReturnValue(secondDiff.promise);

    await user.click(screen.getByRole("button", { name: "Reload" }));
    await waitFor(() => expect(api.fetchProjectGraph).toHaveBeenCalledTimes(1));
    await user.click(screen.getByRole("button", { name: "Reload" }));
    await waitFor(() => expect(api.fetchProjectGraph).toHaveBeenCalledTimes(2));
    expect(firstProjectSignal?.aborted).toBe(true);
    expect(firstHistorySignal?.aborted).toBe(true);

    await act(async () => {
      secondProject.resolve({ schema_version: 2, marker: "reload-2" });
      secondReview.resolve({ review_order: ["nd_reload_2"] });
      secondHistory.resolve(history([secondCommit]));
    });
    await waitFor(() => expect(api.fetchGraphDiff).toHaveBeenCalledTimes(1));
    secondDiff.resolve(diff(secondCommit));
    await waitFor(() =>
      expect(screen.getByLabelText("loaded diff").textContent).toBe(secondCommit),
    );

    await act(async () => {
      firstProject.reject(new Error("stale core failure"));
      firstReview.resolve({ review_order: ["nd_reload_1"] });
      firstHistory.resolve(history([firstCommit]));
      await Promise.allSettled([
        firstProject.promise,
        firstReview.promise,
        firstHistory.promise,
      ]);
    });

    expect(screen.getByLabelText("project marker").textContent).toBe("reload-2");
    expect(screen.getByLabelText("review order").textContent).toBe("nd_reload_2");
    expect(screen.getByLabelText("history head").textContent).toBe(headCommit);
    expect(screen.getByLabelText("selected base").textContent).toBe(secondCommit);
    expect(screen.getByLabelText("loaded diff").textContent).toBe(secondCommit);
    expect(screen.getByLabelText("core loading").textContent).toBe("false");
    expect(screen.getByLabelText("core error").textContent).toBe("none");
    expect(api.fetchGraphDiff).toHaveBeenCalledTimes(1);
  });
});
