import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useReducer,
  type ReactNode,
} from "react";

import { fetchProjectGraph, fetchReviewOrder } from "../api/project";
import type { StatusFilter } from "../graph/graphView";
import type { ProjectGraphResult } from "../types/projectGraph";

export type SelectedElement =
  | { kind: "knowledge"; id: string }
  | { kind: "derivation"; id: string }
  | null;

export interface ProjectState {
  projectGraph: ProjectGraphResult | null;
  reviewOrder: string[];
  loading: boolean;
  error: string | null;
  selectedElement: SelectedElement;
  searchText: string;
  statusFilter: StatusFilter;
  onlyNeedsReview: boolean;
  reviewOrderCollapsed: boolean;
}

export type ProjectAction =
  | { type: "loading" }
  | { type: "loaded"; graph: ProjectGraphResult; reviewOrder: string[] }
  | { type: "failed"; message: string }
  | { type: "selected"; element: SelectedElement }
  | { type: "reviewSelected"; nodeId: string }
  | { type: "searchChanged"; value: string }
  | { type: "statusChanged"; value: StatusFilter }
  | { type: "needsReviewChanged"; value: boolean }
  | { type: "reviewOrderToggled" };

export const initialProjectState: ProjectState = {
  projectGraph: null,
  reviewOrder: [],
  loading: true,
  error: null,
  selectedElement: null,
  searchText: "",
  statusFilter: "all",
  onlyNeedsReview: false,
  reviewOrderCollapsed: false,
};

export function projectReducer(
  state: ProjectState,
  action: ProjectAction,
): ProjectState {
  switch (action.type) {
    case "loading":
      return { ...state, loading: true, error: null };
    case "loaded":
      return {
        ...state,
        projectGraph: action.graph,
        reviewOrder: action.reviewOrder,
        loading: false,
        error: null,
        selectedElement: null,
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
    case "searchChanged":
      return { ...state, searchText: action.value };
    case "statusChanged":
      return { ...state, statusFilter: action.value };
    case "needsReviewChanged":
      return { ...state, onlyNeedsReview: action.value };
    case "reviewOrderToggled":
      return { ...state, reviewOrderCollapsed: !state.reviewOrderCollapsed };
  }
}

interface ProjectContextValue {
  state: ProjectState;
  reload: () => Promise<void>;
  select: (element: SelectedElement) => void;
  selectReviewNode: (nodeId: string) => void;
  setSearchText: (value: string) => void;
  setStatusFilter: (value: StatusFilter) => void;
  setOnlyNeedsReview: (value: boolean) => void;
  toggleReviewOrder: () => void;
}

const ProjectContext = createContext<ProjectContextValue | null>(null);

export function ProjectProvider({ children }: { children: ReactNode }) {
  const [state, dispatch] = useReducer(projectReducer, initialProjectState);

  const reload = useCallback(async () => {
    dispatch({ type: "loading" });
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

  return (
    <ProjectContext.Provider
      value={{
        state,
        reload,
        select,
        selectReviewNode,
        setSearchText,
        setStatusFilter,
        setOnlyNeedsReview,
        toggleReviewOrder,
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
