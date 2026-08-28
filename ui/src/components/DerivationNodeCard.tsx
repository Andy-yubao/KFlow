import { Handle, Position, type NodeProps } from "@xyflow/react";
import { useState } from "react";

import type { DerivationFlowNode } from "../graph/buildFlowGraph";

export function DerivationNodeCard({
  data,
  selected,
}: NodeProps<DerivationFlowNode>) {
  const [tooltipVisible, setTooltipVisible] = useState(false);
  const { derivation } = data;
  return (
    <div
      className={`graph-node derivation-node ${selected ? "selected" : ""}`}
      title={derivation.short}
      aria-label={`Derivation: ${derivation.short}`}
      tabIndex={0}
      onMouseEnter={() => setTooltipVisible(true)}
      onMouseLeave={() => setTooltipVisible(false)}
      onFocus={() => setTooltipVisible(true)}
      onBlur={() => setTooltipVisible(false)}
    >
      <Handle type="target" position={Position.Left} />
      <span className="derivation-mark" aria-hidden="true">◆</span>
      {tooltipVisible && (
        <span className="derivation-tooltip" role="tooltip">
          {derivation.short}
        </span>
      )}
      <Handle type="source" position={Position.Right} />
    </div>
  );
}
