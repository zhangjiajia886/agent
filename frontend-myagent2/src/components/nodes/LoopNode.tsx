import type { NodeProps } from '@xyflow/react';
import { RefreshCw } from 'lucide-react';
import BaseNode from './BaseNode';
import type { LoopNodeData } from '@/types/workflow';

export default function LoopNode({ data, selected }: NodeProps) {
  const d = data as LoopNodeData;
  return (
    <BaseNode
      label={d.label}
      icon={<RefreshCw size={14} />}
      color="#ec4899"
      selected={selected}
    >
      <div className="space-y-1">
        <div className="flex items-center justify-between">
          <span className="text-gray-400">最大轮次</span>
          <span className="font-mono">{d.maxIterations || 10}</span>
        </div>
        {d.exitCondition && (
          <div className="text-gray-500 truncate text-[10px] font-mono bg-pink-50 px-1.5 py-0.5 rounded">
            exit: {d.exitCondition}
          </div>
        )}
      </div>
    </BaseNode>
  );
}
