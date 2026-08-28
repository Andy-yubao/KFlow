import { useProject } from "../state/ProjectContext";

export function GraphToolbar() {
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
          <option value="attention">Needs attention</option>
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
