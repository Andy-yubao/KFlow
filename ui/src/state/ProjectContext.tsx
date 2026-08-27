import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useReducer,
  type ReactNode,
} from "react";

import { fetchProjectGraph } from "../api/project";
import type { ProjectGraphResult } from "../types/projectGraph";

export type SelectedElement =
  | { kind: "knowledge"; id: string }
  | { kind: "derivation"; id: string }
  | null;

interface ProjectState {
  projectGraph: ProjectGraphResult | null;
  loading: boolean;
  error: string | null;
  selectedElement: SelectedElement;
}

type Action =
  | { type: "loading" }
  | { type: "loaded"; graph: ProjectGraphResult }
  | { type: "failed"; message: string }
  | { type: "selected"; element: SelectedElement };

const initialState: ProjectState = {
  projectGraph: null,
  loading: true,
  error: null,
  selectedElement: null,
};

function reducer(state: ProjectState, action: Action): ProjectState {
  switch (action.type) {
    case "loading":
      return { ...state, loading: true, error: null };
    case "loaded":
      return {
        projectGraph: action.graph,
        loading: false,
        error: null,
        selectedElement: null,
      };
    case "failed":
      return { ...state, loading: false, error: action.message };
    case "selected":
      return { ...state, selectedElement: action.element };
  }
}

interface ProjectContextValue {
  state: ProjectState;
  reload: () => Promise<void>;
  select: (element: SelectedElement) => void;
}

const ProjectContext = createContext<ProjectContextValue | null>(null);

export function ProjectProvider({ children }: { children: ReactNode }) {
  const [state, dispatch] = useReducer(reducer, initialState);

  const reload = useCallback(async () => {
    dispatch({ type: "loading" });
    try {
      const graph = await fetchProjectGraph();
      dispatch({ type: "loaded", graph });
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

  return (
    <ProjectContext.Provider value={{ state, reload, select }}>
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
