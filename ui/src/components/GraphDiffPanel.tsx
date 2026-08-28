import { useProject } from "../state/ProjectContext";
import type {
  ChangedDerivation,
  ChangedNode,
  DerivationResult,
  GraphDiffResult,
  StructuralNode,
} from "../types/projectGraph";

function NodeItem({
  node,
  selectable,
  fields,
}: {
  node: StructuralNode;
  selectable: boolean;
  fields?: string[];
}) {
  const { selectGraphDiffElement } = useProject();
  const content = (
    <>
      <strong>{node.name}</strong>
      <code>{node.id}</code>
      {fields && <small>Changed: {fields.join(", ")}</small>}
      <small>{node.files.join(", ")}</small>
    </>
  );
  return selectable ? (
    <button
      type="button"
      onClick={() => selectGraphDiffElement({ kind: "knowledge", id: node.id })}
    >
      {content}
    </button>
  ) : (
    <div className="historical-diff-item">{content}</div>
  );
}

function DerivationItem({
  derivation,
  selectable,
  fields,
}: {
  derivation: DerivationResult;
  selectable: boolean;
  fields?: string[];
}) {
  const { selectGraphDiffElement } = useProject();
  const endpoints = [
    derivation.inputs.map((role) => role.name).join(" + "),
    derivation.outputs.map((role) => role.name).join(" + "),
  ].join(" → ");
  const content = (
    <>
      <strong>{derivation.short}</strong>
      <code>{derivation.id}</code>
      {fields && <small>Changed: {fields.join(", ")}</small>}
      {derivation.detail && <small>{derivation.detail}</small>}
      <small>{endpoints}</small>
    </>
  );
  return selectable ? (
    <button
      type="button"
      onClick={() =>
        selectGraphDiffElement({ kind: "derivation", id: derivation.id })
      }
    >
      {content}
    </button>
  ) : (
    <div className="historical-diff-item">{content}</div>
  );
}

function DiffGroup({
  title,
  count,
  children,
}: {
  title: string;
  count: number;
  children: React.ReactNode;
}) {
  return (
    <section className="diff-group">
      <h3>{title} <small>{count}</small></h3>
      {count > 0 && <div className="diff-list">{children}</div>}
    </section>
  );
}

function AvailableDiff({ result }: { result: GraphDiffResult }) {
  const summary = result.summary;
  const base = result.base;
  if (summary === null || base === null) return null;
  const changeCount =
    summary.added_nodes +
    summary.removed_nodes +
    summary.changed_nodes +
    summary.added_derivations +
    summary.removed_derivations +
    summary.changed_derivations;
  return (
    <div className="graph-diff-content">
      <div className="diff-base">
        <code>{base.short_commit}</code>
        <span>{base.subject}</span>
      </div>
      {changeCount === 0 && !summary.topology_changed && (
        <p className="muted">No structural graph changes since HEAD.</p>
      )}
      <DiffGroup title="Added Nodes" count={summary.added_nodes}>
        {result.nodes.added.map((node) => (
          <NodeItem key={node.id} node={node} selectable />
        ))}
      </DiffGroup>
      <DiffGroup title="Removed Nodes" count={summary.removed_nodes}>
        {result.nodes.removed.map((node) => (
          <NodeItem key={node.id} node={node} selectable={false} />
        ))}
      </DiffGroup>
      <DiffGroup title="Changed Nodes" count={summary.changed_nodes}>
        {result.nodes.changed.map((change: ChangedNode) => (
          <NodeItem
            key={change.id}
            node={change.after}
            fields={change.changed_fields}
            selectable
          />
        ))}
      </DiffGroup>
      <DiffGroup title="Added Derivations" count={summary.added_derivations}>
        {result.derivations.added.map((derivation) => (
          <DerivationItem key={derivation.id} derivation={derivation} selectable />
        ))}
      </DiffGroup>
      <DiffGroup title="Removed Derivations" count={summary.removed_derivations}>
        {result.derivations.removed.map((derivation) => (
          <DerivationItem
            key={derivation.id}
            derivation={derivation}
            selectable={false}
          />
        ))}
      </DiffGroup>
      <DiffGroup title="Changed Derivations" count={summary.changed_derivations}>
        {result.derivations.changed.map((change: ChangedDerivation) => (
          <DerivationItem
            key={change.id}
            derivation={change.after}
            fields={change.changed_fields}
            selectable
          />
        ))}
      </DiffGroup>
      <p className={`topology-state ${summary.topology_changed ? "changed" : ""}`}>
        Topology {summary.topology_changed ? "changed" : "unchanged"}.
      </p>
    </div>
  );
}

export function GraphDiffPanel() {
  const { state, toggleGraphDiff } = useProject();
  const result = state.graphDiff;
  return (
    <aside className="graph-diff">
      <button
        className="graph-diff-heading"
        type="button"
        aria-expanded={!state.graphDiffCollapsed}
        onClick={toggleGraphDiff}
      >
        <span>Graph Diff vs HEAD</span>
        <small>{result?.available ? result.base?.short_commit : "Git"}</small>
      </button>
      {!state.graphDiffCollapsed && (
        state.graphDiffLoading && result === null ? (
          <p className="muted">Loading HEAD graph…</p>
        ) : state.graphDiffError ? (
          <p className="diff-error" role="alert">{state.graphDiffError}</p>
        ) : result?.available ? (
          <AvailableDiff result={result} />
        ) : (
          <p className="muted">
            {result?.issues[0]?.message ?? "Graph Diff is unavailable."}
          </p>
        )
      )}
    </aside>
  );
}
