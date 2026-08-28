import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useReducer,
  type ReactNode,
} from "react";

import {
  fetchGraphDiff,
  fetchProjectGraph,
  fetchReviewOrder,
} from "../api/project";
import type { StatusFilter } from "../graph/graphView";
import type { GraphDiffResult, ProjectGraphResult } from "../types/projectGraph";

export type SelectedElement =
  | { kind: "knowledge"; id: string }
  | { kind: "derivation"; id: string }
  | null;

export interface ProjectState {
  projectGraph: ProjectGraphResult | null;
  reviewOrder: string[];
  graphDiff: GraphDiffResult | null;
  graphDiffLoading: boolean;
  graphDiffError: string | null;
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
  | { type: "graphDiffLoaded"; result: GraphDiffResult }
  | { type: "graphDiffFailed"; message: string }
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
  graphDiffLoading: true,
  graphDiffError: null,
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
        graphDiffLoading: true,
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
    case "graphDiffLoaded":
      return {
        ...state,
        graphDiff: action.result,
        graphDiffLoading: false,
        graphDiffError: null,
      };
    case "graphDiffFailed":
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
  setSearchText: (value: string) => void;
  setStatusFilter: (value: StatusFilter) => void;
  setOnlyNeedsReview: (value: boolean) => void;
  toggleReviewOrder: () => void;
  toggleGraphDiff: () => void;
}

const ProjectContext = createContext<ProjectContextValue | null>(null);

export function ProjectProvider({ children }: { children: ReactNode }) {
  const [state, dispatch] = useReducer(projectReducer, initialProjectState);

  const reload = useCallback(async () => {
    dispatch({ type: "loading" });
    const diffRequest = fetchGraphDiff()
      .then((result) => dispatch({ type: "graphDiffLoaded", result }))
      .catch((error: unknown) => {
        const message =
          error instanceof Error ? error.message : "Unknown Graph Diff error.";
        dispatch({ type: "graphDiffFailed", message });
      });
    try {
      const [graph, review] = await Promise.all([
        fetchProjectGraph(),
        fetchReviewOrder(),
      ]);
      dispatch({ type: "loaded", graph, reviewOrder: review.review_order });
    } catch (error) {
      const message = error instanceof Error ? error.message : "Unknown network error.";
      dispatch({ type: "failed", message });
    }
    await diffRequest;
  }, []);

  useEffect(() => {
    void reload();
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
