import type { NodeProps } from '@xyflow/react';
import { Square } from 'lucide-react';
import BaseNode from './BaseNode';
import type { EndNodeData } from '@/types/workflow';

export default function EndNode({ data, selected }: NodeProps) {
  const d = data as EndNodeData;
  const outputs = d.outputs || [];
  return (
    <BaseNode
      label={d.label}
      icon={<Square size={14} />}
      color="#ef4444"
      selected={selected}
      handles={{ left: true, right: false }}
    >
      <div className="space-y-1">
        <div className="text-gray-400 italic">工作流输出</div>
        {outputs.length > 0 ? (
          <div className="flex flex-wrap gap-1">
            {outputs.map((item) => (
              <span key={item} className="text-[10px] px-1.5 py-0.5 rounded bg-red-50 text-red-700 border border-red-100 font-mono">
                {item}
              </span>
            ))}
          </div>
        ) : (
          <div className="text-[10px] text-gray-300">未声明输出变量</div>
        )}
      </div>
    </BaseNode>
  );
}
