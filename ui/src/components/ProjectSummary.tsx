import type { ProjectSummary as Summary } from "../types/projectGraph";

const labels: Record<string, string> = {
  current: "Current",
  attention_required: "Attention required",
  invalid: "Invalid",
};

export function ProjectSummary({ project }: { project: Summary }) {
  return (
    <header className="project-summary">
      <div className="brand-block">
        <div className="brand-mark" aria-hidden="true">K</div>
        <div>
          <h1>KFlow Project Graph</h1>
          <p>Local, read-only knowledge topology</p>
        </div>
      </div>
      <dl className="summary-metrics">
        <div>
          <dt>Status</dt>
          <dd className={`project-status status-${project.status}`}>
            {labels[project.status] ?? project.status}
          </dd>
        </div>
        <div><dt>Nodes</dt><dd>{project.node_count}</dd></div>
        <div><dt>Derivations</dt><dd>{project.derivation_count}</dd></div>
        <div><dt>Need review</dt><dd>{project.needs_review_count}</dd></div>
        <div><dt>Issues</dt><dd>{project.issue_count}</dd></div>
      </dl>
    </header>
  );
}
