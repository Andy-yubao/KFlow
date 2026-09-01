import { act, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { ProjectProvider, useProject } from "./ProjectContext";

const api = vi.hoisted(() => ({
  fetchProjectGraph: vi.fn(),
  fetchReviewOrder: vi.fn(),
  fetchGitHistory: vi.fn(),
  fetchGraphDiff: vi.fn(),
  fetchRevision: vi.fn(),
}));

vi.mock("../api/project", () => api);

const firstRevision = {
  ok: true as const,
  project_revision: "project-1",
  git_revision: "git-1",
};

function deferred<T>() {
  let resolve!: (value: T | PromiseLike<T>) => void;
  let reject!: (reason?: unknown) => void;
  const promise = new Promise<T>((resolvePromise, rejectPromise) => {
    resolve = resolvePromise;
    reject = rejectPromise;
  });
  return { promise, resolve, reject };
}

function PollingProbe() {
  const { state, reload } = useProject();
  return (
    <div>
      <output aria-label="initial error">
        {state.initialLoadError ?? "none"}
      </output>
      <output aria-label="reload error">{state.reloadError ?? "none"}</output>
      <output aria-label="automatic error">
        {state.automaticRefreshError ?? "none"}
      </output>
      <button type="button" onClick={() => void reload()}>
        Reload
      </button>
    </div>
  );
}

async function settle() {
  await act(async () => {
    await Promise.resolve();
    await Promise.resolve();
    await Promise.resolve();
  });
}

beforeEach(() => {
  vi.useFakeTimers();
  api.fetchProjectGraph.mockReset().mockResolvedValue({
    ok: true,
    schema_version: 2,
    nodes: [],
    derivations: [],
    topological_order: [],
  });
  api.fetchReviewOrder.mockReset().mockResolvedValue({ review_order: [] });
  api.fetchGitHistory.mockReset().mockResolvedValue({
    ok: true,
    available: false,
    schema_version: 1,
    head: null,
    commits: [],
    issues: [],
  });
  api.fetchGraphDiff.mockReset().mockResolvedValue({
    ok: true,
    available: false,
    schema_version: 2,
    base: null,
  });
  api.fetchRevision.mockReset().mockResolvedValue(firstRevision);
});

afterEach(() => {
  vi.restoreAllMocks();
  vi.useRealTimers();
});

describe("ProjectProvider revision polling", () => {
  it("does not reload full data while revisions remain unchanged", async () => {
    const rendered = render(<ProjectProvider><div /></ProjectProvider>);
    await settle();

    await act(async () => {
      await vi.advanceTimersByTimeAsync(1000);
    });

    expect(api.fetchRevision).toHaveBeenCalledTimes(2);
    expect(api.fetchProjectGraph).toHaveBeenCalledTimes(1);
    expect(api.fetchReviewOrder).toHaveBeenCalledTimes(1);
    expect(api.fetchGitHistory).toHaveBeenCalledTimes(1);
    expect(api.fetchGraphDiff).toHaveBeenCalledTimes(1);
    rendered.unmount();
  });

  it("refreshes only core data and Graph Diff for a project revision", async () => {
    api.fetchRevision
      .mockResolvedValueOnce(firstRevision)
      .mockResolvedValue({ ...firstRevision, project_revision: "project-2" });
    const rendered = render(<ProjectProvider><div /></ProjectProvider>);
    await settle();

    await act(async () => {
      await vi.advanceTimersByTimeAsync(1200);
    });

    expect(api.fetchProjectGraph).toHaveBeenCalledTimes(2);
    expect(api.fetchReviewOrder).toHaveBeenCalledTimes(2);
    expect(api.fetchGitHistory).toHaveBeenCalledTimes(1);
    expect(api.fetchGraphDiff).toHaveBeenCalledTimes(2);
    rendered.unmount();
  });

  it("debounces a detected change and never overlaps revision requests", async () => {
    api.fetchRevision
      .mockResolvedValueOnce(firstRevision)
      .mockResolvedValueOnce({
        ...firstRevision,
        project_revision: "project-2",
      })
      .mockResolvedValueOnce({
        ...firstRevision,
        project_revision: "project-2",
      })
      .mockImplementation(() => new Promise(() => undefined));
    const rendered = render(<ProjectProvider><div /></ProjectProvider>);
    await settle();

    await act(async () => {
      await vi.advanceTimersByTimeAsync(1000);
    });
    expect(api.fetchProjectGraph).toHaveBeenCalledTimes(1);
    await act(async () => {
      await vi.advanceTimersByTimeAsync(149);
    });
    expect(api.fetchProjectGraph).toHaveBeenCalledTimes(1);
    await act(async () => {
      await vi.advanceTimersByTimeAsync(1);
    });
    expect(api.fetchProjectGraph).toHaveBeenCalledTimes(2);

    await act(async () => {
      await vi.advanceTimersByTimeAsync(1000);
      await vi.advanceTimersByTimeAsync(5000);
    });
    expect(api.fetchRevision).toHaveBeenCalledTimes(4);
    rendered.unmount();
  });

  it("refreshes Git History and Graph Diff for a Git-only revision", async () => {
    api.fetchRevision
      .mockResolvedValueOnce(firstRevision)
      .mockResolvedValue({ ...firstRevision, git_revision: "git-2" });
    const rendered = render(<ProjectProvider><div /></ProjectProvider>);
    await settle();

    await act(async () => {
      await vi.advanceTimersByTimeAsync(1200);
    });

    expect(api.fetchProjectGraph).toHaveBeenCalledTimes(1);
    expect(api.fetchReviewOrder).toHaveBeenCalledTimes(1);
    expect(api.fetchGitHistory).toHaveBeenCalledTimes(2);
    expect(api.fetchGraphDiff).toHaveBeenCalledTimes(2);
    rendered.unmount();
  });

  it("keeps the old revision baseline after a failed automatic refresh", async () => {
    const changed = { ...firstRevision, project_revision: "project-2" };
    api.fetchRevision
      .mockResolvedValueOnce(firstRevision)
      .mockResolvedValue(changed);
    api.fetchProjectGraph
      .mockResolvedValueOnce({
        ok: true,
        schema_version: 2,
        nodes: [],
        derivations: [],
        topological_order: [],
      })
      .mockRejectedValueOnce(new Error("temporary failure"))
      .mockResolvedValue({
        ok: true,
        schema_version: 2,
        nodes: [],
        derivations: [],
        topological_order: [],
      });
    const rendered = render(<ProjectProvider><PollingProbe /></ProjectProvider>);
    await settle();

    await act(async () => {
      await vi.advanceTimersByTimeAsync(1200);
    });
    expect(api.fetchProjectGraph).toHaveBeenCalledTimes(2);
    expect(screen.getByLabelText("automatic error").textContent).toBe(
      "temporary failure",
    );
    expect(screen.getByLabelText("reload error").textContent).toBe("none");

    await act(async () => {
      await vi.advanceTimersByTimeAsync(1200);
    });
    expect(api.fetchProjectGraph).toHaveBeenCalledTimes(3);
    expect(screen.getByLabelText("automatic error").textContent).toBe("none");
    rendered.unmount();
  });

  it("clears a polling error after the next unchanged successful check", async () => {
    api.fetchRevision
      .mockResolvedValueOnce(firstRevision)
      .mockRejectedValueOnce(new Error("poll unavailable"))
      .mockResolvedValue(firstRevision);
    const rendered = render(<ProjectProvider><PollingProbe /></ProjectProvider>);
    await settle();

    await act(async () => {
      await vi.advanceTimersByTimeAsync(1000);
    });
    expect(screen.getByLabelText("automatic error").textContent).toBe(
      "poll unavailable",
    );
    expect(screen.getByLabelText("reload error").textContent).toBe("none");

    await act(async () => {
      await vi.advanceTimersByTimeAsync(1000);
    });
    expect(screen.getByLabelText("automatic error").textContent).toBe("none");
    rendered.unmount();
  });

  it("clears an automatic error after a successful manual reload", async () => {
    api.fetchRevision
      .mockResolvedValueOnce(firstRevision)
      .mockRejectedValueOnce(new Error("poll unavailable"))
      .mockResolvedValue(firstRevision);
    const rendered = render(<ProjectProvider><PollingProbe /></ProjectProvider>);
    await settle();

    await act(async () => {
      await vi.advanceTimersByTimeAsync(1000);
    });
    expect(screen.getByLabelText("automatic error").textContent).toBe(
      "poll unavailable",
    );

    fireEvent.click(screen.getByRole("button", { name: "Reload" }));
    await settle();
    expect(screen.getByLabelText("automatic error").textContent).toBe("none");
    expect(screen.getByLabelText("reload error").textContent).toBe("none");
    rendered.unmount();
  });

  it("shows a manual failure only as Reload failed and clears it on success", async () => {
    api.fetchProjectGraph
      .mockResolvedValueOnce({
        ok: true,
        schema_version: 2,
        nodes: [],
        derivations: [],
        topological_order: [],
      })
      .mockRejectedValueOnce(new Error("manual failure"))
      .mockResolvedValue({
        ok: true,
        schema_version: 2,
        nodes: [],
        derivations: [],
        topological_order: [],
      });
    const rendered = render(<ProjectProvider><PollingProbe /></ProjectProvider>);
    await settle();

    fireEvent.click(screen.getByRole("button", { name: "Reload" }));
    await settle();
    expect(screen.getByLabelText("reload error").textContent).toBe(
      "manual failure",
    );
    expect(screen.getByLabelText("automatic error").textContent).toBe("none");

    fireEvent.click(screen.getByRole("button", { name: "Reload" }));
    await settle();
    expect(screen.getByLabelText("reload error").textContent).toBe("none");
    rendered.unmount();
  });

  it("does not let an aborted old automatic failure overwrite manual success", async () => {
    const currentGraph = {
      ok: true,
      schema_version: 2,
      nodes: [],
      derivations: [],
      topological_order: [],
    };
    const staleAutomaticGraph = deferred<typeof currentGraph>();
    api.fetchRevision
      .mockResolvedValueOnce(firstRevision)
      .mockResolvedValue({ ...firstRevision, project_revision: "project-2" });
    api.fetchProjectGraph
      .mockResolvedValueOnce(currentGraph)
      .mockImplementationOnce(() => staleAutomaticGraph.promise)
      .mockResolvedValue(currentGraph);
    const rendered = render(<ProjectProvider><PollingProbe /></ProjectProvider>);
    await settle();

    await act(async () => {
      await vi.advanceTimersByTimeAsync(1200);
    });
    expect(api.fetchProjectGraph).toHaveBeenCalledTimes(2);

    fireEvent.click(screen.getByRole("button", { name: "Reload" }));
    await settle();
    expect(api.fetchProjectGraph).toHaveBeenCalledTimes(3);
    expect(screen.getByLabelText("reload error").textContent).toBe("none");

    await act(async () => {
      staleAutomaticGraph.reject(new Error("stale automatic failure"));
      await Promise.allSettled([staleAutomaticGraph.promise]);
    });
    expect(screen.getByLabelText("automatic error").textContent).toBe("none");
    expect(screen.getByLabelText("reload error").textContent).toBe("none");
    rendered.unmount();
  });

  it("slows down while hidden and checks immediately on focus", async () => {
    let hidden = false;
    vi.spyOn(document, "hidden", "get").mockImplementation(() => hidden);
    const rendered = render(<ProjectProvider><div /></ProjectProvider>);
    await settle();

    hidden = true;
    document.dispatchEvent(new Event("visibilitychange"));
    await act(async () => {
      await vi.advanceTimersByTimeAsync(0);
    });
    const afterHiddenCheck = api.fetchRevision.mock.calls.length;
    await act(async () => {
      await vi.advanceTimersByTimeAsync(4999);
    });
    expect(api.fetchRevision).toHaveBeenCalledTimes(afterHiddenCheck);
    await act(async () => {
      await vi.advanceTimersByTimeAsync(1);
    });
    expect(api.fetchRevision).toHaveBeenCalledTimes(afterHiddenCheck + 1);

    window.dispatchEvent(new Event("focus"));
    await act(async () => {
      await vi.advanceTimersByTimeAsync(0);
    });
    expect(api.fetchRevision).toHaveBeenCalledTimes(afterHiddenCheck + 2);
    rendered.unmount();
  });

  it("aborts the active revision request and clears timers on unmount", async () => {
    let pollingSignal: AbortSignal | undefined;
    api.fetchRevision
      .mockResolvedValueOnce(firstRevision)
      .mockImplementation((_signal?: AbortSignal) => {
        pollingSignal = _signal;
        return new Promise(() => undefined);
      });
    const rendered = render(<ProjectProvider><div /></ProjectProvider>);
    await settle();
    await act(async () => {
      await vi.advanceTimersByTimeAsync(1000);
    });
    expect(pollingSignal?.aborted).toBe(false);

    rendered.unmount();

    expect(pollingSignal?.aborted).toBe(true);
    expect(vi.getTimerCount()).toBe(0);
  });
});
