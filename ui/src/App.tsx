import { useMemo } from "react";

import { GraphCanvas } from "./components/GraphCanvas";
import { GraphToolbar } from "./components/GraphToolbar";
import { GraphDiffPanel } from "./components/GraphDiffPanel";
import { InspectorPanel } from "./components/InspectorPanel";
import { ProjectSummary } from "./components/ProjectSummary";
import { ReviewOrderPanel } from "./components/ReviewOrderPanel";
import { buildGraphView } from "./graph/graphView";
import { useProject } from "./state/ProjectContext";

function ReloadButton({ busy = false }: { busy?: boolean }) {
  const { reload } = useProject();
  return (
    <button className="reload-button" type="button" onClick={() => void reload()} disabled={busy}>
      {busy ? "Loading…" : "Reload"}
    </button>
  );
}

export default function App() {
  const { state } = useProject();
  const {
    projectGraph,
    loading,
    initialLoadError,
    reloadError,
    automaticRefreshError,
    selectedElement,
  } = state;
  const view = useMemo(
    () =>
      projectGraph === null
        ? null
        : buildGraphView(projectGraph, {
            searchText: state.searchText,
            statusFilter: state.statusFilter,
            onlyNeedsReview: state.onlyNeedsReview,
            selectedElement: state.selectedElement,
          }),
    [
      projectGraph,
      state.onlyNeedsReview,
      state.searchText,
      state.selectedElement,
      state.statusFilter,
    ],
  );

  if (loading && projectGraph === null) {
    return (
      <main className="centered-state" aria-live="polite">
        <div className="loading-mark" aria-hidden="true" />
        <h1>Loading KFlow project…</h1>
        <p>Reading the current public project graph.</p>
      </main>
    );
  }

  if (initialLoadError && projectGraph === null) {
    return (
      <main className="centered-state error-state" role="alert">
        <span className="error-symbol" aria-hidden="true">!</span>
        <h1>Unable to load the project graph</h1>
        <p>{initialLoadError}</p>
        <ReloadButton />
      </main>
    );
  }

  if (projectGraph === null || view === null) return null;

  return (
    <main className="app-shell">
      <ProjectSummary project={projectGraph.project} />
      <div className="toolbar">
        <p>Knowledge Nodes and complete Derivations from <code>query_project_graph()</code></p>
        <ReloadButton busy={loading} />
      </div>
      <GraphToolbar view={view} />
      {!projectGraph.ok && (
        <section className="issues-banner" role="alert">
          <div>
            <span className="eyebrow">Validation issues</span>
            <h2>项目图不可正常使用</h2>
          </div>
          <ul>
            {projectGraph.issues.map((issue, index) => (
              <li key={`${issue.code}:${index}`}>
                <strong>{issue.code}</strong>: {issue.message}
                {issue.references.length > 0 && <small>{issue.references.join(", ")}</small>}
              </li>
            ))}
          </ul>
        </section>
      )}
      {reloadError && (
        <div className="inline-error" role="alert">
          Reload failed: {reloadError}
        </div>
      )}
      {automaticRefreshError && (
        <div className="inline-error" role="status">
          Automatic update temporarily unavailable: {automaticRefreshError}
        </div>
      )}
      <div className="workspace">
        <GraphCanvas graph={projectGraph} view={view} />
        <div className="side-panels">
          <InspectorPanel graph={projectGraph} selected={selectedElement} />
          <ReviewOrderPanel graph={projectGraph} />
          <GraphDiffPanel />
        </div>
      </div>
    </main>
  );
}
