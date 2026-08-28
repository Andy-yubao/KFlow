import { useProject } from "../state/ProjectContext";
import type {
  ChangedDerivation,
  ChangedNode,
  DerivationResult,
  DerivationRole,
  GraphDiffResult,
  StructuralNode,
} from "../types/projectGraph";

function displayValue(value: string) {
  return value || "None";
}

function ScalarChange({
  label,
  before,
  after,
}: {
  label: string;
  before: string;
  after: string;
}) {
  return (
    <div className="scalar-change">
      <h5>{label}</h5>
      <p>
        <span className="change-before">{displayValue(before)}</span>
        <span className="change-arrow" aria-hidden="true">
          →
        </span>
        <span className="change-after">{displayValue(after)}</span>
      </p>
    </div>
  );
}

function FileSetChange({ before, after }: { before: string[]; after: string[] }) {
  const beforeSet = new Set(before);
  const afterSet = new Set(after);
  const removed = before.filter((path) => !afterSet.has(path));
  const added = after.filter((path) => !beforeSet.has(path));
  if (removed.length === 0 && added.length === 0) return null;
  return (
    <section className="collection-change">
      <h5>Files</h5>
      <ul className="set-change-list">
        {removed.map((path) => (
          <li className="removed" key={`removed:${path}`}>
            <span aria-hidden="true">-</span>
            <code>{path}</code>
          </li>
        ))}
        {added.map((path) => (
          <li className="added" key={`added:${path}`}>
            <span aria-hidden="true">+</span>
            <code>{path}</code>
          </li>
        ))}
      </ul>
    </section>
  );
}

function RoleItem({
  role,
  marker,
}: {
  role: DerivationRole;
  marker: "+" | "-";
}) {
  return (
    <li className={marker === "+" ? "added" : "removed"}>
      <span aria-hidden="true">{marker}</span>
      <div>
        <strong>{role.name}</strong>
        <code>{role.node}</code>
        <p>{role.short}</p>
        {role.detail && <small>{role.detail}</small>}
      </div>
    </li>
  );
}

function ChangedRole({
  before,
  after,
}: {
  before: DerivationRole;
  after: DerivationRole;
}) {
  return (
    <article className="changed-role">
      <h6>Changed: {before.node}</h6>
      {before.name !== after.name && (
        <ScalarChange label="Name" before={before.name} after={after.name} />
      )}
      {before.short !== after.short && (
        <ScalarChange label="Short" before={before.short} after={after.short} />
      )}
      {before.detail !== after.detail && (
        <ScalarChange label="Detail" before={before.detail} after={after.detail} />
      )}
    </article>
  );
}

function RoleCollectionChange({
  title,
  before,
  after,
}: {
  title: "Inputs" | "Outputs";
  before: DerivationRole[];
  after: DerivationRole[];
}) {
  const beforeByNode = new Map(before.map((role) => [role.node, role]));
  const afterByNode = new Map(after.map((role) => [role.node, role]));
  const removed = before.filter((role) => !afterByNode.has(role.node));
  const added = after.filter((role) => !beforeByNode.has(role.node));
  const changed = before.flatMap((role) => {
    const current = afterByNode.get(role.node);
    return current &&
      (role.name !== current.name ||
        role.short !== current.short ||
        role.detail !== current.detail)
      ? [{ before: role, after: current }]
      : [];
  });
  return (
    <section className="role-collection-change">
      <h5>{title}</h5>
      {added.length > 0 && (
        <div className="role-change-group">
          <h6>Added</h6>
          <ul>
            {added.map((role) => (
              <RoleItem key={role.node} role={role} marker="+" />
            ))}
          </ul>
        </div>
      )}
      {removed.length > 0 && (
        <div className="role-change-group">
          <h6>Removed</h6>
          <ul>
            {removed.map((role) => (
              <RoleItem key={role.node} role={role} marker="-" />
            ))}
          </ul>
        </div>
      )}
      {changed.map((change) => (
        <ChangedRole key={change.before.node} {...change} />
      ))}
    </section>
  );
}

function ChangedNodeItem({ change }: { change: ChangedNode }) {
  const { selectGraphDiffElement } = useProject();
  return (
    <article className="changed-diff-item">
      <button
        className="current-diff-select"
        type="button"
        aria-label={`Select current Node ${change.after.name}`}
        onClick={() =>
          selectGraphDiffElement({ kind: "knowledge", id: change.id })
        }
      >
        <strong>Select current Node</strong>
        <code>{change.id}</code>
      </button>
      <div className="structural-changes">
        <h4>Structural changes</h4>
        {change.changed_fields.includes("name") && (
          <ScalarChange
            label="Name"
            before={change.before.name}
            after={change.after.name}
          />
        )}
        {change.changed_fields.includes("files") && (
          <FileSetChange
            before={change.before.files}
            after={change.after.files}
          />
        )}
      </div>
    </article>
  );
}

function ChangedDerivationItem({ change }: { change: ChangedDerivation }) {
  const { selectGraphDiffElement } = useProject();
  return (
    <article className="changed-diff-item">
      <button
        className="current-diff-select"
        type="button"
        aria-label={`Select current Derivation ${change.after.short}`}
        onClick={() =>
          selectGraphDiffElement({ kind: "derivation", id: change.id })
        }
      >
        <strong>Select current Derivation</strong>
        <code>{change.id}</code>
      </button>
      <div className="structural-changes">
        <h4>Structural changes</h4>
        {change.changed_fields.includes("short") && (
          <ScalarChange
            label="Short"
            before={change.before.short}
            after={change.after.short}
          />
        )}
        {change.changed_fields.includes("detail") && (
          <ScalarChange
            label="Detail"
            before={change.before.detail}
            after={change.after.detail}
          />
        )}
        {change.changed_fields.includes("inputs") && (
          <RoleCollectionChange
            title="Inputs"
            before={change.before.inputs}
            after={change.after.inputs}
          />
        )}
        {change.changed_fields.includes("outputs") && (
          <RoleCollectionChange
            title="Outputs"
            before={change.before.outputs}
            after={change.after.outputs}
          />
        )}
      </div>
    </article>
  );
}

function NodeItem({
  node,
  selectable,
}: {
  node: StructuralNode;
  selectable: boolean;
}) {
  const { selectGraphDiffElement } = useProject();
  const content = (
    <>
      <strong>{node.name}</strong>
      <code>{node.id}</code>
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
}: {
  derivation: DerivationResult;
  selectable: boolean;
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
          <ChangedNodeItem key={change.id} change={change} />
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
          <ChangedDerivationItem key={change.id} change={change} />
        ))}
      </DiffGroup>
      <p className={`topology-state ${summary.topology_changed ? "changed" : ""}`}>
        Topological order {summary.topology_changed ? "changed" : "unchanged"}.
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
