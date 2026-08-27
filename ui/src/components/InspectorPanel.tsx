import type { ProjectGraphResult } from "../types/projectGraph";
import type { SelectedElement } from "../state/ProjectContext";

interface InspectorProps {
  graph: ProjectGraphResult;
  selected: SelectedElement;
}

function TextList({ items, empty = "None" }: { items: string[]; empty?: string }) {
  if (!items.length) {
    return <p className="muted">{empty}</p>;
  }
  return <ul>{items.map((item) => <li key={item}>{item}</li>)}</ul>;
}

export function InspectorPanel({ graph, selected }: InspectorProps) {
  if (selected === null) {
    return (
      <aside className="inspector">
        <div className="panel-heading">
          <span className="eyebrow">Inspector</span>
          <h2>Select an element</h2>
        </div>
        <p className="muted">
          Choose a Knowledge Node or Derivation to inspect its complete public facts.
        </p>
      </aside>
    );
  }

  if (selected.kind === "knowledge") {
    const node = graph.nodes.find((candidate) => candidate.id === selected.id);
    if (!node) return null;
    return (
      <aside className="inspector">
        <div className="panel-heading">
          <span className="eyebrow">Knowledge Node</span>
          <h2>{node.name}</h2>
          <code>{node.id}</code>
        </div>
        <section><h3>Status</h3><p>{node.status ?? "unknown"}</p></section>
        <section><h3>Reasons</h3><TextList items={node.reasons} /></section>
        <section><h3>Files</h3><TextList items={node.files} /></section>
        <section><h3>Changed files</h3><TextList items={node.changed_files} /></section>
      </aside>
    );
  }

  const derivation = graph.derivations.find(
    (candidate) => candidate.id === selected.id,
  );
  if (!derivation) return null;
  return (
    <aside className="inspector">
      <div className="panel-heading">
        <span className="eyebrow">Derivation</span>
        <h2>{derivation.short}</h2>
        <code>{derivation.id}</code>
      </div>
      {derivation.detail && <section><h3>Detail</h3><p>{derivation.detail}</p></section>}
      <section>
        <h3>Inputs</h3>
        <div className="role-list">
          {derivation.inputs.map((role) => (
            <article className="role-card" key={role.node}>
              <strong>{role.name}</strong><code>{role.node}</code>
              <p>{role.short}</p>{role.detail && <small>{role.detail}</small>}
            </article>
          ))}
        </div>
      </section>
      <section>
        <h3>Outputs</h3>
        <div className="role-list">
          {derivation.outputs.map((role) => (
            <article className="role-card" key={role.node}>
              <strong>{role.name}</strong><code>{role.node}</code>
              <p>{role.short}</p>{role.detail && <small>{role.detail}</small>}
            </article>
          ))}
        </div>
      </section>
    </aside>
  );
}
