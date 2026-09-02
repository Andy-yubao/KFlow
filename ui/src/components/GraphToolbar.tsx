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
    </section>
  );
}
