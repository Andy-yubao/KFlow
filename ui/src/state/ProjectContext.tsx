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
  fetchReviewOrder,
} from "../api/project";
import type { StatusFilter } from "../graph/graphView";
import type {
  GitHistoryResult,
  GraphDiffResult,
  ProjectGraphResult,
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
        selectedElement: null,
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
        gitHistory: null,
        gitHistoryLoading: false,
        gitHistoryError: action.message,
        selectedGraphDiffBase: "HEAD",
      };
    case "graphDiffLoading":
      return {
        ...state,
        selectedGraphDiffBase: action.base,
        graphDiff: null,
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

  const loadGraphDiff = useCallback(async (base: string) => {
    selectedBase.current = base;
    graphDiffController.current?.abort();
    const controller = new AbortController();
    graphDiffController.current = controller;
    const requestId = ++graphDiffRequestId.current;
    dispatch({ type: "graphDiffLoading", base, requestId });
    try {
      const result = await fetchGraphDiff(base, controller.signal);
      if (controller.signal.aborted) return;
      dispatch({ type: "graphDiffLoaded", result, requestId });
    } catch (error: unknown) {
      if (controller.signal.aborted) return;
      const message =
        error instanceof Error ? error.message : "Unknown Graph Diff error.";
      dispatch({ type: "graphDiffFailed", message, requestId });
    }
  }, []);

  const reload = useCallback(async () => {
    const generation = ++reloadGeneration.current;
    reloadController.current?.abort();
    graphDiffController.current?.abort();
    const controller = new AbortController();
    reloadController.current = controller;
    const isCurrent = () =>
      generation === reloadGeneration.current && !controller.signal.aborted;

    dispatch({ type: "loading" });
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
        const message =
          error instanceof Error ? error.message : "Unknown Git history error.";
        selectedBase.current = "HEAD";
        dispatch({ type: "gitHistoryFailed", message });
      }
      if (!isCurrent()) return;
      await loadGraphDiff(base);
    })();

    await Promise.all([coreRequest, historyRequest]);
  }, [loadGraphDiff]);

  useEffect(() => {
    void reload();
    return () => {
      reloadController.current?.abort();
      graphDiffController.current?.abort();
    };
  }, [reload]);

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
