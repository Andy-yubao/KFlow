import { useProject } from "../state/ProjectContext";
import type { ProjectGraphResult } from "../types/projectGraph";

export function ReviewOrderPanel({ graph }: { graph: ProjectGraphResult }) {
  const { state, selectReviewNode, toggleReviewOrder } = useProject();
  const orderedNodes = state.reviewOrder.flatMap((nodeId) => {
    const node = graph.nodes.find((candidate) => candidate.id === nodeId);
    return node ? [node] : [];
  });

  return (
    <aside className="review-order">
      <button
        className="review-order-heading"
        type="button"
        aria-expanded={!state.reviewOrderCollapsed}
        onClick={toggleReviewOrder}
      >
        <span>Review Order</span>
        <small>{orderedNodes.length}</small>
      </button>
      {!state.reviewOrderCollapsed && (
        orderedNodes.length ? (
          <ol>
            {orderedNodes.map((node) => (
              <li key={node.id}>
                <button type="button" onClick={() => selectReviewNode(node.id)}>
                  <strong>{node.name}</strong>
                  <code>{node.id}</code>
                  <span>{node.status ?? "unknown"}</span>
                  <small>{node.reasons.join(", ") || "No reasons"}</small>
                  <small>{node.files.join(", ")}</small>
                </button>
              </li>
            ))}
          </ol>
        ) : (
          <p className="muted">No Nodes currently need review in the affected scope.</p>
        )
      )}
    </aside>
  );
}
