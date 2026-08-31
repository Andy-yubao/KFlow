import type {
  ChangedDerivation,
  ChangedNode,
  DerivationResult,
  DerivationRole,
  GraphDiffSummary,
  GitHistoryCommit,
  GitHistoryResult,
  OpenFileResult,
  GraphDiffResult,
  ProjectGraphResult,
  QueryIssue,
  ReviewOrderResult,
  RevisionResult,
  StructuralNode,
} from "../types/projectGraph";

const SUPPORTED_SCHEMA_VERSION = 2;
const REVIEW_ORDER_SCHEMA_VERSION = 3;
const GRAPH_DIFF_SCHEMA_VERSION = 2;
const GIT_HISTORY_SCHEMA_VERSION = 1;

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

function isStringArray(value: unknown): value is string[] {
  return Array.isArray(value) && value.every((item) => typeof item === "string");
}

function isNonEmptyString(value: unknown): value is string {
  return typeof value === "string" && value.trim().length > 0;
}

function isCommitId(value: unknown): value is string {
  return isNonEmptyString(value) && /^[0-9a-f]+$/i.test(value);
}

function isQueryIssue(value: unknown): value is QueryIssue {
  return (
    isRecord(value) &&
    typeof value.code === "string" &&
    typeof value.message === "string" &&
    isStringArray(value.references)
  );
}

function isStructuralNode(value: unknown): value is StructuralNode {
  return (
    isRecord(value) &&
    isNonEmptyString(value.id) &&
    typeof value.name === "string" &&
    isStringArray(value.files)
  );
}

function isDerivationRole(value: unknown): value is DerivationRole {
  return (
    isRecord(value) &&
    isNonEmptyString(value.node) &&
    typeof value.name === "string" &&
    typeof value.short === "string" &&
    typeof value.detail === "string"
  );
}

function isDerivation(value: unknown): value is DerivationResult {
  return (
    isRecord(value) &&
    isNonEmptyString(value.id) &&
    typeof value.short === "string" &&
    typeof value.detail === "string" &&
    Array.isArray(value.inputs) &&
    value.inputs.every(isDerivationRole) &&
    Array.isArray(value.outputs) &&
    value.outputs.every(isDerivationRole)
  );
}

function hasAllowedChangedFields(
  value: unknown,
  allowed: ReadonlySet<string>,
): value is string[] {
  return (
    isStringArray(value) &&
    value.length > 0 &&
    new Set(value).size === value.length &&
    value.every((field) => allowed.has(field))
  );
}

const NODE_CHANGED_FIELDS = new Set(["name", "files"]);
const DERIVATION_CHANGED_FIELDS = new Set([
  "short",
  "detail",
  "inputs",
  "outputs",
]);

function isChangedNode(value: unknown): value is ChangedNode {
  return (
    isRecord(value) &&
    isNonEmptyString(value.id) &&
    hasAllowedChangedFields(value.changed_fields, NODE_CHANGED_FIELDS) &&
    isStructuralNode(value.before) &&
    isStructuralNode(value.after) &&
    value.before.id === value.id &&
    value.after.id === value.id
  );
}

function isChangedDerivation(value: unknown): value is ChangedDerivation {
  return (
    isRecord(value) &&
    isNonEmptyString(value.id) &&
    hasAllowedChangedFields(
      value.changed_fields,
      DERIVATION_CHANGED_FIELDS,
    ) &&
    isDerivation(value.before) &&
    isDerivation(value.after) &&
    value.before.id === value.id &&
    value.after.id === value.id
  );
}

function isNonNegativeInteger(value: unknown): value is number {
  return Number.isInteger(value) && (value as number) >= 0;
}

function isGraphDiffBase(value: unknown): boolean {
  return (
    isRecord(value) &&
    isNonEmptyString(value.reference) &&
    isCommitId(value.commit) &&
    isNonEmptyString(value.short_commit) &&
    typeof value.subject === "string" &&
    typeof value.committed_at === "string"
  );
}

function isGitHistoryCommit(value: unknown): value is GitHistoryCommit {
  return (
    isRecord(value) &&
    isCommitId(value.commit) &&
    isNonEmptyString(value.short_commit) &&
    typeof value.subject === "string" &&
    typeof value.committed_at === "string"
  );
}

function isGraphDiffSummary(value: unknown): value is GraphDiffSummary {
  return (
    isRecord(value) &&
    isNonNegativeInteger(value.added_nodes) &&
    isNonNegativeInteger(value.removed_nodes) &&
    isNonNegativeInteger(value.changed_nodes) &&
    isNonNegativeInteger(value.added_derivations) &&
    isNonNegativeInteger(value.removed_derivations) &&
    isNonNegativeInteger(value.changed_derivations) &&
    typeof value.topology_changed === "boolean"
  );
}

function parseProjectGraph(value: unknown): ProjectGraphResult {
  if (!isRecord(value)) {
    throw new Error("The project endpoint did not return a JSON object.");
  }
  if (value.schema_version !== SUPPORTED_SCHEMA_VERSION) {
    throw new Error(
      `Unsupported KFlow schema version: ${String(value.schema_version)}.`,
    );
  }
  if (!Array.isArray(value.nodes) || !Array.isArray(value.derivations)) {
    throw new Error("The project graph is missing its nodes or derivations array.");
  }
  return value as unknown as ProjectGraphResult;
}

function parseReviewOrder(value: unknown): ReviewOrderResult {
  if (
    !isRecord(value) ||
    value.schema_version !== REVIEW_ORDER_SCHEMA_VERSION ||
    !Array.isArray(value.review_order) ||
    !Array.isArray(value.issues)
  ) {
    throw new Error("The review order endpoint returned an incompatible result.");
  }
  return value as unknown as ReviewOrderResult;
}

export function parseRevision(value: unknown): RevisionResult {
  if (
    !isRecord(value) ||
    value.ok !== true ||
    !isNonEmptyString(value.project_revision) ||
    !isNonEmptyString(value.git_revision)
  ) {
    throw new Error("The revision endpoint returned an incompatible result.");
  }
  return value as unknown as RevisionResult;
}

export function parseGraphDiff(value: unknown): GraphDiffResult {
  if (
    !isRecord(value) ||
    typeof value.ok !== "boolean" ||
    value.schema_version !== GRAPH_DIFF_SCHEMA_VERSION ||
    typeof value.available !== "boolean" ||
    !Array.isArray(value.issues) ||
    !value.issues.every(isQueryIssue) ||
    !isRecord(value.nodes) ||
    !Array.isArray(value.nodes.added) ||
    !value.nodes.added.every(isStructuralNode) ||
    !Array.isArray(value.nodes.removed) ||
    !value.nodes.removed.every(isStructuralNode) ||
    !Array.isArray(value.nodes.changed) ||
    !value.nodes.changed.every(isChangedNode) ||
    !isRecord(value.derivations) ||
    !Array.isArray(value.derivations.added) ||
    !value.derivations.added.every(isDerivation) ||
    !Array.isArray(value.derivations.removed) ||
    !value.derivations.removed.every(isDerivation) ||
    !Array.isArray(value.derivations.changed) ||
    !value.derivations.changed.every(isChangedDerivation) ||
    !isStringArray(value.before_topological_order) ||
    !isStringArray(value.after_topological_order)
  ) {
    throw new Error("The graph diff endpoint returned an incompatible result.");
  }

  if (value.available) {
    if (!isGraphDiffBase(value.base) || !isGraphDiffSummary(value.summary)) {
      throw new Error("The graph diff endpoint returned an incompatible result.");
    }
    if (
      value.summary.added_nodes !== value.nodes.added.length ||
      value.summary.removed_nodes !== value.nodes.removed.length ||
      value.summary.changed_nodes !== value.nodes.changed.length ||
      value.summary.added_derivations !== value.derivations.added.length ||
      value.summary.removed_derivations !== value.derivations.removed.length ||
      value.summary.changed_derivations !== value.derivations.changed.length
    ) {
      throw new Error("The graph diff endpoint returned an incompatible result.");
    }
  } else {
    if (
      value.base !== null ||
      value.summary !== null ||
      value.nodes.added.length > 0 ||
      value.nodes.removed.length > 0 ||
      value.nodes.changed.length > 0 ||
      value.derivations.added.length > 0 ||
      value.derivations.removed.length > 0 ||
      value.derivations.changed.length > 0 ||
      value.before_topological_order.length > 0 ||
      value.after_topological_order.length > 0
    ) {
      throw new Error("The graph diff endpoint returned an incompatible result.");
    }
  }
  return value as unknown as GraphDiffResult;
}

export function parseGitHistory(value: unknown): GitHistoryResult {
  if (
    !isRecord(value) ||
    typeof value.ok !== "boolean" ||
    typeof value.available !== "boolean" ||
    value.schema_version !== GIT_HISTORY_SCHEMA_VERSION ||
    !Array.isArray(value.issues) ||
    !value.issues.every(isQueryIssue) ||
    !Array.isArray(value.commits) ||
    !value.commits.every(isGitHistoryCommit)
  ) {
    throw new Error("The Git history endpoint returned an incompatible result.");
  }
  const commitIds = value.commits.map((commit) => commit.commit);
  if (new Set(commitIds).size !== commitIds.length) {
    throw new Error("The Git history endpoint returned an incompatible result.");
  }
  if (value.available) {
    if (
      !isGitHistoryCommit(value.head) ||
      commitIds.includes(value.head.commit)
    ) {
      throw new Error("The Git history endpoint returned an incompatible result.");
    }
  } else if (value.head !== null || value.commits.length > 0) {
    throw new Error("The Git history endpoint returned an incompatible result.");
  }
  return value as unknown as GitHistoryResult;
}

async function readJson(response: Response, endpoint: string): Promise<unknown> {
  try {
    return await response.json();
  } catch {
    throw new Error(`The ${endpoint} endpoint did not return valid JSON.`);
  }
}

export async function fetchProjectGraph(
  signal?: AbortSignal,
): Promise<ProjectGraphResult> {
  const response = await fetch("/api/project", {
    method: "GET",
    headers: { Accept: "application/json" },
    signal,
  });
  if (!response.ok) {
    throw new Error(`Project request failed with HTTP ${response.status}.`);
  }

  const body = await readJson(response, "project");
  return parseProjectGraph(body);
}

export async function fetchReviewOrder(
  signal?: AbortSignal,
): Promise<ReviewOrderResult> {
  const response = await fetch("/api/review-order", {
    method: "GET",
    headers: { Accept: "application/json" },
    signal,
  });
  if (!response.ok) {
    throw new Error(`Review order request failed with HTTP ${response.status}.`);
  }
  return parseReviewOrder(await readJson(response, "review order"));
}

export async function fetchGraphDiff(
  base?: string,
  signal?: AbortSignal,
): Promise<GraphDiffResult> {
  let endpoint = "/api/graph-diff";
  if (base && base !== "HEAD") {
    const parameters = new URLSearchParams({ base });
    endpoint = `${endpoint}?${parameters.toString()}`;
  }
  const response = await fetch(endpoint, {
    method: "GET",
    headers: { Accept: "application/json" },
    signal,
  });
  if (!response.ok) {
    throw new Error(`Graph Diff request failed with HTTP ${response.status}.`);
  }
  return parseGraphDiff(await readJson(response, "graph diff"));
}

export async function fetchGitHistory(
  signal?: AbortSignal,
): Promise<GitHistoryResult> {
  const response = await fetch("/api/git-history", {
    method: "GET",
    headers: { Accept: "application/json" },
    signal,
  });
  if (!response.ok) {
    throw new Error(`Git history request failed with HTTP ${response.status}.`);
  }
  return parseGitHistory(await readJson(response, "Git history"));
}

export async function fetchRevision(
  signal?: AbortSignal,
): Promise<RevisionResult> {
  const response = await fetch("/api/revision", {
    method: "GET",
    headers: { Accept: "application/json" },
    signal,
  });
  if (!response.ok) {
    throw new Error(`Revision request failed with HTTP ${response.status}.`);
  }
  return parseRevision(await readJson(response, "revision"));
}

export async function openRegisteredFile(
  path: string,
  fetcher: typeof fetch = fetch,
): Promise<OpenFileResult> {
  const response = await fetcher("/api/open-file", {
    method: "POST",
    headers: {
      Accept: "application/json",
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ path }),
  });
  const body = await readJson(response, "open file");
  if (!isRecord(body) || typeof body.ok !== "boolean") {
    throw new Error("The open file endpoint returned an incompatible result.");
  }
  const result = body as unknown as OpenFileResult;
  if (!response.ok || !result.ok) {
    throw new Error(result.issues?.[0]?.message ?? `Unable to open ${path}.`);
  }
  return result;
}
