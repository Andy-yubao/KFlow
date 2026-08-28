export interface QueryIssue {
  code: string;
  message: string;
  references: string[];
}

export interface ProjectSummary {
  status: "current" | "attention_required" | "invalid" | string;
  node_count: number;
  derivation_count: number;
  needs_review_count: number;
  issue_count: number;
}

export interface StatusNode {
  id: string;
  name: string;
  files: string[];
  changed_files: string[];
  status: string | null;
  reasons: string[];
}

export interface DerivationRole {
  node: string;
  name: string;
  short: string;
  detail: string;
}

export interface DerivationResult {
  id: string;
  short: string;
  detail: string;
  inputs: DerivationRole[];
  outputs: DerivationRole[];
}

export interface ProjectGraphResult {
  ok: boolean;
  schema_version: number;
  project: ProjectSummary;
  nodes: StatusNode[];
  derivations: DerivationResult[];
  topological_order: string[];
  issues: QueryIssue[];
}

export interface ReviewOrderResult {
  ok: boolean;
  schema_version: number;
  review_order: string[];
  issues: QueryIssue[];
}

export interface OpenFileResult {
  ok: boolean;
  path: string | null;
  issues?: QueryIssue[];
}

export interface StructuralNode {
  id: string;
  name: string;
  files: string[];
}

export interface ChangedNode {
  id: string;
  changed_fields: Array<"name" | "files">;
  before: StructuralNode;
  after: StructuralNode;
}

export interface ChangedDerivation {
  id: string;
  changed_fields: Array<"short" | "detail" | "inputs" | "outputs">;
  before: DerivationResult;
  after: DerivationResult;
}

export interface GraphDiffSummary {
  added_nodes: number;
  removed_nodes: number;
  changed_nodes: number;
  added_derivations: number;
  removed_derivations: number;
  changed_derivations: number;
  topology_changed: boolean;
}

export interface GraphDiffResult {
  ok: boolean;
  available: boolean;
  schema_version: 1;
  base: {
    revision: "HEAD";
    commit: string;
    short_commit: string;
    subject: string;
  } | null;
  summary: GraphDiffSummary | null;
  nodes: {
    added: StructuralNode[];
    removed: StructuralNode[];
    changed: ChangedNode[];
  };
  derivations: {
    added: DerivationResult[];
    removed: DerivationResult[];
    changed: ChangedDerivation[];
  };
  before_topological_order: string[];
  after_topological_order: string[];
  issues: QueryIssue[];
}
