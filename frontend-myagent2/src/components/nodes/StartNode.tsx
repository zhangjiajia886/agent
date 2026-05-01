import type { NodeProps } from '@xyflow/react';
import { Play } from 'lucide-react';
import BaseNode from './BaseNode';
import type { StartNodeData } from '@/types/workflow';

export default function StartNode({ data, selected }: NodeProps) {
  const d = data as StartNodeData;
  const outputs = d.outputs || [];
  return (
    <BaseNode
      label={d.label}
      icon={<Play size={14} />}
      color="#22c55e"
      selected={selected}
      handles={{ left: false, right: true }}
    >
      <div className="space-y-1">
        <div className="text-gray-400 italic">工作流输入</div>
        {outputs.length > 0 ? (
          <div className="flex flex-wrap gap-1">
            {outputs.map((item) => (
              <span key={item} className="text-[10px] px-1.5 py-0.5 rounded bg-green-50 text-green-700 border border-green-100 font-mono">
                {item}
              </span>
            ))}
          </div>
        ) : (
          <div className="text-[10px] text-gray-300">未声明输入变量</div>
        )}
      </div>
    </BaseNode>
  );
}
