import { useProject } from "../state/ProjectContext";
import type { GraphView } from "../graph/graphView";

export function GraphToolbar({ view }: { view: GraphView }) {
  const {
    state,
    setSearchText,
    setStatusFilter,
    setOnlyNeedsReview,
    select,
  } = useProject();

  return (
    <section className="graph-toolbar" aria-label="Graph search and filters">
      <label className="search-control">
        <span>Search</span>
        <input
          type="search"
          value={state.searchText}
          placeholder="Node, file, or Derivation"
          onChange={(event) => setSearchText(event.target.value)}
        />
        {view.searchActive && view.searchMatchCount === 0 && (
          <small className="search-no-results" role="status">
            No matching Nodes or Derivations.
          </small>
        )}
      </label>
      <label className="filter-control">
        <span>Status</span>
        <select
          value={state.statusFilter}
          onChange={(event) =>
            setStatusFilter(
              event.target.value as "all" | "current" | "attention" | "unknown",
            )
          }
        >
          <option value="all">All</option>
          <option value="current">Current</option>
          <option value="attention">Needs review</option>
          <option value="unknown">Unknown</option>
        </select>
      </label>
      <label className="toggle-control">
        <input
          type="checkbox"
          checked={state.onlyNeedsReview}
          onChange={(event) => setOnlyNeedsReview(event.target.checked)}
        />
        <span>Only needs review</span>
      </label>
      <button className="clear-button" type="button" onClick={() => select(null)}>
        Clear selection
      </button>
      <div className="graph-legend" aria-label="Graph legend">
        <span><strong>Structure</strong></span>
        <span className="legend-role source">Source</span>
        <span className="legend-role intermediate">Intermediate</span>
        <span className="legend-role terminal">Terminal</span>
        <span className="legend-role isolated">Isolated</span>
        <span className="legend-derivation">◆ Derivation</span>
        <span className="legend-divider" aria-hidden="true" />
        <span><strong>Status</strong></span>
        <span className="legend-status current">✓ Current</span>
        <span className="legend-status attention">! Needs review</span>
        <span className="legend-status unknown">? Unknown</span>
      </div>
    </section>
  );
}
