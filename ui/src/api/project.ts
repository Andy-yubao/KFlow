import type {
  OpenFileResult,
  ProjectGraphResult,
  ReviewOrderResult,
} from "../types/projectGraph";

const SUPPORTED_SCHEMA_VERSION = 2;

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
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
    value.schema_version !== SUPPORTED_SCHEMA_VERSION ||
    !Array.isArray(value.review_order) ||
    !Array.isArray(value.issues)
  ) {
    throw new Error("The review order endpoint returned an incompatible result.");
  }
  return value as unknown as ReviewOrderResult;
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
