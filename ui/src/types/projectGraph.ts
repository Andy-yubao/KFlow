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
