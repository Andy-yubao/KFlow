import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useReducer,
  useRef,
  type ReactNode,
} from "react";

import {
  fetchGraphDiff,
  fetchGitHistory,
  fetchProjectGraph,
  fetchRevision,
  fetchReviewOrder,
} from "../api/project";
import type { StatusFilter } from "../graph/graphView";
import type {
  GitHistoryResult,
  GraphDiffResult,
  ProjectGraphResult,
  RevisionResult,
} from "../types/projectGraph";

export type SelectedElement =
  | { kind: "knowledge"; id: string }
  | { kind: "derivation"; id: string }
  | null;

export interface ProjectState {
  projectGraph: ProjectGraphResult | null;
  reviewOrder: string[];
  graphDiff: GraphDiffResult | null;
  gitHistory: GitHistoryResult | null;
  gitHistoryLoading: boolean;
  gitHistoryError: string | null;
  selectedGraphDiffBase: string;
  graphDiffLoading: boolean;
  graphDiffError: string | null;
  graphDiffRequestId: number;
  loading: boolean;
  error: string | null;
  selectedElement: SelectedElement;
  searchText: string;
  statusFilter: StatusFilter;
  onlyNeedsReview: boolean;
  reviewOrderCollapsed: boolean;
  graphDiffCollapsed: boolean;
}

export type ProjectAction =
  | { type: "loading" }
  | { type: "loaded"; graph: ProjectGraphResult; reviewOrder: string[] }
  | {
      type: "gitHistoryLoaded";
      result: GitHistoryResult;
      selectedBase: string;
    }
  | { type: "gitHistoryFailed"; message: string }
  | { type: "graphDiffLoading"; base: string; requestId: number }
  | { type: "graphDiffLoaded"; result: GraphDiffResult; requestId: number }
  | { type: "graphDiffFailed"; message: string; requestId: number }
  | { type: "failed"; message: string }
  | { type: "selected"; element: SelectedElement }
  | { type: "reviewSelected"; nodeId: string }
  | { type: "graphDiffSelected"; element: Exclude<SelectedElement, null> }
  | { type: "searchChanged"; value: string }
  | { type: "statusChanged"; value: StatusFilter }
  | { type: "needsReviewChanged"; value: boolean }
  | { type: "reviewOrderToggled" }
  | { type: "graphDiffToggled" };

export const initialProjectState: ProjectState = {
  projectGraph: null,
  reviewOrder: [],
  graphDiff: null,
  gitHistory: null,
  gitHistoryLoading: true,
  gitHistoryError: null,
  selectedGraphDiffBase: "HEAD",
  graphDiffLoading: true,
  graphDiffError: null,
  graphDiffRequestId: 0,
  loading: true,
  error: null,
  selectedElement: null,
  searchText: "",
  statusFilter: "all",
  onlyNeedsReview: false,
  reviewOrderCollapsed: false,
  graphDiffCollapsed: false,
};

export function projectReducer(
  state: ProjectState,
  action: ProjectAction,
): ProjectState {
  switch (action.type) {
    case "loading":
      return {
        ...state,
        loading: true,
        error: null,
        gitHistoryLoading: true,
        gitHistoryError: null,
        graphDiffError: null,
      };
    case "loaded":
      return {
        ...state,
        projectGraph: action.graph,
        reviewOrder: action.reviewOrder,
        loading: false,
        error: null,
        selectedElement: selectionStillExists(
          action.graph,
          state.selectedElement,
        )
          ? state.selectedElement
          : null,
      };
    case "gitHistoryLoaded":
      return {
        ...state,
        gitHistory: action.result,
        gitHistoryLoading: false,
        gitHistoryError: null,
        selectedGraphDiffBase: action.selectedBase,
      };
    case "gitHistoryFailed":
      return {
        ...state,
        gitHistoryLoading: false,
        gitHistoryError: action.message,
      };
    case "graphDiffLoading":
      return {
        ...state,
        selectedGraphDiffBase: action.base,
        graphDiffLoading: true,
        graphDiffError: null,
        graphDiffRequestId: action.requestId,
      };
    case "graphDiffLoaded":
      if (action.requestId !== state.graphDiffRequestId) return state;
      return {
        ...state,
        graphDiff: action.result,
        graphDiffLoading: false,
        graphDiffError: null,
      };
    case "graphDiffFailed":
      if (action.requestId !== state.graphDiffRequestId) return state;
      return {
        ...state,
        graphDiffLoading: false,
        graphDiffError: action.message,
      };
    case "failed":
      return { ...state, loading: false, error: action.message };
    case "selected":
      return { ...state, selectedElement: action.element };
    case "reviewSelected":
      return {
        ...state,
        searchText: "",
        statusFilter: "all",
        onlyNeedsReview: false,
        selectedElement: { kind: "knowledge", id: action.nodeId },
      };
    case "graphDiffSelected":
      return {
        ...state,
        searchText: "",
        statusFilter: "all",
        onlyNeedsReview: false,
        selectedElement: action.element,
      };
    case "searchChanged":
      return { ...state, searchText: action.value };
    case "statusChanged":
      return { ...state, statusFilter: action.value };
    case "needsReviewChanged":
      return { ...state, onlyNeedsReview: action.value };
    case "reviewOrderToggled":
      return { ...state, reviewOrderCollapsed: !state.reviewOrderCollapsed };
    case "graphDiffToggled":
      return { ...state, graphDiffCollapsed: !state.graphDiffCollapsed };
  }
}

function selectionStillExists(
  graph: ProjectGraphResult,
  selection: SelectedElement,
): boolean {
  if (selection === null) return true;
  return selection.kind === "knowledge"
    ? graph.nodes.some((node) => node.id === selection.id)
    : graph.derivations.some((derivation) => derivation.id === selection.id);
}

interface ProjectContextValue {
  state: ProjectState;
  reload: () => Promise<void>;
  select: (element: SelectedElement) => void;
  selectReviewNode: (nodeId: string) => void;
  selectGraphDiffElement: (element: Exclude<SelectedElement, null>) => void;
  selectGraphDiffBase: (base: string) => void;
  setSearchText: (value: string) => void;
  setStatusFilter: (value: StatusFilter) => void;
  setOnlyNeedsReview: (value: boolean) => void;
  toggleReviewOrder: () => void;
  toggleGraphDiff: () => void;
}

const ProjectContext = createContext<ProjectContextValue | null>(null);

export function ProjectProvider({ children }: { children: ReactNode }) {
  const [state, dispatch] = useReducer(projectReducer, initialProjectState);
  const selectedBase = useRef("HEAD");
  const graphDiffRequestId = useRef(0);
  const graphDiffController = useRef<AbortController | null>(null);
  const reloadGeneration = useRef(0);
  const reloadController = useRef<AbortController | null>(null);
  const revisionController = useRef<AbortController | null>(null);
  const revisionBaseline = useRef<RevisionResult | null>(null);

  const loadGraphDiff = useCallback(async (base: string): Promise<boolean> => {
    selectedBase.current = base;
    graphDiffController.current?.abort();
    const controller = new AbortController();
    graphDiffController.current = controller;
    const requestId = ++graphDiffRequestId.current;
    dispatch({ type: "graphDiffLoading", base, requestId });
    try {
      const result = await fetchGraphDiff(base, controller.signal);
      if (controller.signal.aborted) return false;
      dispatch({ type: "graphDiffLoaded", result, requestId });
      return true;
    } catch (error: unknown) {
      if (controller.signal.aborted) return false;
      const message =
        error instanceof Error ? error.message : "Unknown Graph Diff error.";
      dispatch({ type: "graphDiffFailed", message, requestId });
      return false;
    }
  }, []);

  const reload = useCallback(async () => {
    const generation = ++reloadGeneration.current;
    reloadController.current?.abort();
    graphDiffController.current?.abort();
    revisionController.current?.abort();
    revisionController.current = null;
    const controller = new AbortController();
    reloadController.current = controller;
    const isCurrent = () =>
      generation === reloadGeneration.current && !controller.signal.aborted;

    dispatch({ type: "loading" });
    let refreshFailed = false;
    const coreRequest = (async () => {
      try {
        const [graph, review] = await Promise.all([
          fetchProjectGraph(controller.signal),
          fetchReviewOrder(controller.signal),
        ]);
        if (!isCurrent()) return;
        dispatch({ type: "loaded", graph, reviewOrder: review.review_order });
      } catch (error: unknown) {
        if (!isCurrent()) return;
        refreshFailed = true;
        const message =
          error instanceof Error ? error.message : "Unknown network error.";
        dispatch({ type: "failed", message });
      }
    })();

    const historyRequest = (async () => {
      let base = "HEAD";
      try {
        const history = await fetchGitHistory(controller.signal);
        if (!isCurrent()) return;
        const availableCommits = new Set(
          history.available ? history.commits.map((commit) => commit.commit) : [],
        );
        if (
          selectedBase.current !== "HEAD" &&
          availableCommits.has(selectedBase.current)
        ) {
          base = selectedBase.current;
        }
        dispatch({
          type: "gitHistoryLoaded",
          result: history,
          selectedBase: base,
        });
      } catch (error: unknown) {
        if (!isCurrent()) return;
        refreshFailed = true;
        const message =
          error instanceof Error ? error.message : "Unknown Git history error.";
        selectedBase.current = "HEAD";
        dispatch({ type: "gitHistoryFailed", message });
      }
      if (!isCurrent()) return;
      if (!(await loadGraphDiff(base))) refreshFailed = true;
    })();

    await Promise.all([coreRequest, historyRequest]);
    if (!isCurrent() || refreshFailed) return;
    try {
      revisionBaseline.current = await fetchRevision(controller.signal);
    } catch (error: unknown) {
      if (!isCurrent()) return;
      const message =
        error instanceof Error ? error.message : "Unknown revision error.";
      dispatch({ type: "failed", message });
    }
  }, [loadGraphDiff]);

  const refreshAutomatically = useCallback(
    async (
      nextRevision: RevisionResult,
      projectChanged: boolean,
      gitChanged: boolean,
    ) => {
      const generation = ++reloadGeneration.current;
      reloadController.current?.abort();
      graphDiffController.current?.abort();
      const controller = new AbortController();
      reloadController.current = controller;
      const isCurrent = () =>
        generation === reloadGeneration.current && !controller.signal.aborted;

      let refreshFailed = false;
      const coreRequest = projectChanged
        ? (async () => {
            try {
              const [graph, review] = await Promise.all([
                fetchProjectGraph(controller.signal),
                fetchReviewOrder(controller.signal),
              ]);
              if (!isCurrent()) return;
              dispatch({
                type: "loaded",
                graph,
                reviewOrder: review.review_order,
              });
            } catch (error: unknown) {
              if (!isCurrent()) return;
              refreshFailed = true;
              const message =
                error instanceof Error
                  ? error.message
                  : "Unknown automatic refresh error.";
              dispatch({ type: "failed", message });
            }
          })()
        : Promise.resolve();

      const historyAndDiffRequest = (async () => {
        let base = selectedBase.current;
        if (gitChanged) {
          try {
            const history = await fetchGitHistory(controller.signal);
            if (!isCurrent()) return;
            base = selectedBase.current;
            const availableCommits = new Set(
              history.available
                ? history.commits.map((commit) => commit.commit)
                : [],
            );
            if (base !== "HEAD" && !availableCommits.has(base)) {
              base = "HEAD";
              selectedBase.current = base;
            }
            dispatch({
              type: "gitHistoryLoaded",
              result: history,
              selectedBase: base,
            });
          } catch (error: unknown) {
            if (!isCurrent()) return;
            refreshFailed = true;
            const message =
              error instanceof Error
                ? error.message
                : "Unknown Git history error.";
            dispatch({ type: "gitHistoryFailed", message });
          }
        }
        if (!isCurrent()) return;
        if (!(await loadGraphDiff(selectedBase.current))) refreshFailed = true;
      })();

      await Promise.all([coreRequest, historyAndDiffRequest]);
      if (!isCurrent() || refreshFailed) return;
      if (projectChanged) {
        try {
          revisionBaseline.current = await fetchRevision(controller.signal);
        } catch {
          if (isCurrent()) revisionBaseline.current = nextRevision;
        }
      } else {
        revisionBaseline.current = nextRevision;
      }
    },
    [loadGraphDiff],
  );

  useEffect(() => {
    void reload();
    return () => {
      reloadController.current?.abort();
      graphDiffController.current?.abort();
      revisionController.current?.abort();
    };
  }, [reload]);

  useEffect(() => {
    let timer: number | undefined;
    let debounceTimer: number | undefined;
    let disposed = false;

    const schedule = (delay?: number) => {
      if (disposed) return;
      window.clearTimeout(timer);
      timer = window.setTimeout(
        () => void checkRevision(),
        delay ?? (document.hidden ? 5000 : 1000),
      );
    };
    const checkRevision = async () => {
      if (disposed || revisionController.current !== null) return;
      const controller = new AbortController();
      revisionController.current = controller;
      try {
        const next = await fetchRevision(controller.signal);
        if (disposed || controller.signal.aborted) return;
        const previous = revisionBaseline.current;
        if (previous === null) {
          revisionBaseline.current = next;
        } else {
          const projectChanged =
            next.project_revision !== previous.project_revision;
          const gitChanged = next.git_revision !== previous.git_revision;
          if (projectChanged || gitChanged) {
            await new Promise<void>((resolve) => {
              debounceTimer = window.setTimeout(resolve, 150);
            });
            if (!disposed && !controller.signal.aborted) {
              await refreshAutomatically(next, projectChanged, gitChanged);
            }
          }
        }
      } catch (error: unknown) {
        if (!disposed && !controller.signal.aborted) {
          const message =
            error instanceof Error
              ? error.message
              : "Unknown automatic update error.";
          dispatch({ type: "failed", message });
        }
      } finally {
        if (revisionController.current === controller) {
          revisionController.current = null;
        }
        schedule();
      }
    };
    const checkNow = () => schedule(0);
    document.addEventListener("visibilitychange", checkNow);
    window.addEventListener("focus", checkNow);
    schedule();
    return () => {
      disposed = true;
      window.clearTimeout(timer);
      window.clearTimeout(debounceTimer);
      revisionController.current?.abort();
      revisionController.current = null;
      document.removeEventListener("visibilitychange", checkNow);
      window.removeEventListener("focus", checkNow);
    };
  }, [refreshAutomatically]);

  const select = useCallback((element: SelectedElement) => {
    dispatch({ type: "selected", element });
  }, []);

  const selectReviewNode = useCallback((nodeId: string) => {
    dispatch({ type: "reviewSelected", nodeId });
  }, []);
  const selectGraphDiffElement = useCallback(
    (element: Exclude<SelectedElement, null>) => {
      dispatch({ type: "graphDiffSelected", element });
    },
    [],
  );
  const selectGraphDiffBase = useCallback(
    (base: string) => {
      void loadGraphDiff(base);
    },
    [loadGraphDiff],
  );
  const setSearchText = useCallback((value: string) => {
    dispatch({ type: "searchChanged", value });
  }, []);
  const setStatusFilter = useCallback((value: StatusFilter) => {
    dispatch({ type: "statusChanged", value });
  }, []);
  const setOnlyNeedsReview = useCallback((value: boolean) => {
    dispatch({ type: "needsReviewChanged", value });
  }, []);
  const toggleReviewOrder = useCallback(() => {
    dispatch({ type: "reviewOrderToggled" });
  }, []);
  const toggleGraphDiff = useCallback(() => {
    dispatch({ type: "graphDiffToggled" });
  }, []);

  return (
    <ProjectContext.Provider
      value={{
        state,
        reload,
        select,
        selectReviewNode,
        selectGraphDiffElement,
        selectGraphDiffBase,
        setSearchText,
        setStatusFilter,
        setOnlyNeedsReview,
        toggleReviewOrder,
        toggleGraphDiff,
      }}
    >
      {children}
    </ProjectContext.Provider>
  );
}

export function useProject(): ProjectContextValue {
  const context = useContext(ProjectContext);
  if (context === null) {
    throw new Error("useProject must be used inside ProjectProvider");
  }
  return context;
}
