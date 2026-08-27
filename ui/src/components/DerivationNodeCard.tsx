import { Handle, Position, type NodeProps } from "@xyflow/react";

import type { DerivationFlowNode } from "../graph/buildFlowGraph";

export function DerivationNodeCard({
  data,
  selected,
}: NodeProps<DerivationFlowNode>) {
  return (
    <div className={`graph-node derivation-node ${selected ? "selected" : ""}`}>
      <Handle type="target" position={Position.Left} />
      <div className="node-kicker">Derivation</div>
      <strong title={data.derivation.short}>{data.derivation.short}</strong>
      <div className="node-meta">
        {data.derivation.inputs.length} in · {data.derivation.outputs.length} out
      </div>
      <Handle type="source" position={Position.Right} />
    </div>
  );
}
