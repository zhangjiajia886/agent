import type { NodeProps } from '@xyflow/react';
import { Wrench } from 'lucide-react';
import BaseNode from './BaseNode';
import type { ToolNodeData } from '@/types/workflow';

export default function ToolNode({ data, selected }: NodeProps) {
  const d = data as ToolNodeData;
  return (
    <BaseNode
      label={d.label}
      icon={<Wrench size={14} />}
      color="#f59e0b"
      selected={selected}
    >
      <div className="space-y-1">
        {d.toolName ? (
          <div className="font-mono bg-amber-50 text-amber-700 px-1.5 py-0.5 rounded text-[10px] inline-block">
            {d.toolName}
          </div>
        ) : (
          <div className="text-gray-400 italic">未选择工具</div>
        )}
        {d.outputVariable && (
          <div className="text-gray-400">
            → <span className="font-mono">{d.outputVariable}</span>
          </div>
        )}
      </div>
    </BaseNode>
  );
}
