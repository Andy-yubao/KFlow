import type { StatusNode } from "../types/projectGraph";

export type NodeVisualState = "current" | "attention" | "unknown";

export function nodeVisualState(node: StatusNode): NodeVisualState {
  if (node.status === null) {
    return "unknown";
  }
  if (node.reasons.length > 0) {
    return "attention";
  }
  return "current";
}
