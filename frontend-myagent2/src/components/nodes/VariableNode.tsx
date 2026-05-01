import type { NodeProps } from '@xyflow/react';
import { Variable } from 'lucide-react';
import BaseNode from './BaseNode';
import type { VariableNodeData } from '@/types/workflow';

export default function VariableNode({ data, selected }: NodeProps) {
  const d = data as VariableNodeData;
  return (
    <BaseNode
      label={d.label}
      icon={<Variable size={14} />}
      color="#64748b"
      selected={selected}
    >
      <div className="space-y-1">
        {d.outputVariable && (
          <div className="font-mono text-[10px] text-gray-500">
            → {d.outputVariable}
          </div>
        )}
        {d.expression && (
          <div className="font-mono text-[10px] bg-slate-50 px-1.5 py-0.5 rounded truncate">
            {d.expression}
          </div>
        )}
      </div>
    </BaseNode>
  );
}
