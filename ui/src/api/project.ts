import type { ProjectGraphResult } from "../types/projectGraph";

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

  let body: unknown;
  try {
    body = await response.json();
  } catch {
    throw new Error("The project endpoint did not return valid JSON.");
  }
  return parseProjectGraph(body);
}
