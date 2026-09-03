import { act, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import App from "./App";
import { ProjectProvider } from "./state/ProjectContext";

const api = vi.hoisted(() => ({
  fetchProjectGraph: vi.fn(),
  fetchReviewOrder: vi.fn(),
  fetchGitHistory: vi.fn(),
  fetchGraphDiff: vi.fn(),
  fetchRevision: vi.fn(),
}));

vi.mock("./api/project", () => api);
vi.mock("./components/GraphCanvas", () => ({
  GraphCanvas: () => <div>Loaded graph</div>,
}));
vi.mock("./components/GraphToolbar", () => ({
  GraphToolbar: () => <div />,
}));
vi.mock("./components/GraphDiffPanel", () => ({
  GraphDiffPanel: () => <div />,
}));
vi.mock("./components/InspectorPanel", () => ({
  InspectorPanel: () => <div />,
}));
vi.mock("./components/ProjectSummary", () => ({
  ProjectSummary: () => <div />,
}));
vi.mock("./components/ReviewOrderPanel", () => ({
  ReviewOrderPanel: () => <div />,
}));

const graph = {
  ok: true,
  schema_version: 3,
  project: {
    status: "current",
    node_count: 0,
    derivation_count: 0,
    needs_review_count: 0,
    issue_count: 0,
  },
  nodes: [],
  derivations: [],
  topological_order: [],
  issues: [],
};
const revision = {
  ok: true,
  project_revision: "project-1",
  git_revision: "git-1",
};

async function settle() {
  await act(async () => {
    await Promise.resolve();
    await Promise.resolve();
    await Promise.resolve();
  });
}

beforeEach(() => {
  api.fetchProjectGraph.mockReset().mockResolvedValue(graph);
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
    schema_version: 3,
    base: null,
  });
  api.fetchRevision.mockReset().mockResolvedValue(revision);
});

afterEach(() => {
  vi.useRealTimers();
});

describe("App refresh error semantics", () => {
  it("uses the blocking initial-load page when no old graph exists", async () => {
    api.fetchProjectGraph.mockRejectedValueOnce(new Error("initial unavailable"));
    const rendered = render(<ProjectProvider><App /></ProjectProvider>);

    expect(
      await screen.findByRole("heading", {
        name: "Unable to load the project graph",
      }),
    ).toBeTruthy();
    expect(screen.getByText("initial unavailable")).toBeTruthy();
    expect(screen.queryByText(/Reload failed/)).toBeNull();
    rendered.unmount();
  });

  it("keeps the old graph and labels a manual failure as Reload failed", async () => {
    const rendered = render(<ProjectProvider><App /></ProjectProvider>);
    await screen.findByText("Loaded graph");
    api.fetchProjectGraph.mockRejectedValueOnce(new Error("manual unavailable"));

    fireEvent.click(screen.getByRole("button", { name: "Reload" }));

    expect(await screen.findByText("Reload failed: manual unavailable")).toBeTruthy();
    expect(screen.getByText("Loaded graph")).toBeTruthy();
    expect(
      screen.queryByText(/Automatic update temporarily unavailable/),
    ).toBeNull();
    rendered.unmount();
  });

  it("shows a temporary automatic label and clears it after unchanged success", async () => {
    vi.useFakeTimers();
    api.fetchRevision
      .mockResolvedValueOnce(revision)
      .mockRejectedValueOnce(new Error("poll unavailable"))
      .mockResolvedValue(revision);
    const rendered = render(<ProjectProvider><App /></ProjectProvider>);
    await settle();

    await act(async () => {
      await vi.advanceTimersByTimeAsync(1000);
    });
    expect(
      screen.getByText(
        "Automatic update temporarily unavailable: poll unavailable",
      ),
    ).toBeTruthy();
    expect(screen.queryByText(/Reload failed/)).toBeNull();
    expect(screen.getByText("Loaded graph")).toBeTruthy();

    await act(async () => {
      await vi.advanceTimersByTimeAsync(1000);
    });
    expect(
      screen.queryByText(/Automatic update temporarily unavailable/),
    ).toBeNull();
    rendered.unmount();
  });
});
