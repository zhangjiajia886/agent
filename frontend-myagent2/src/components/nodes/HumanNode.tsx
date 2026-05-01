import type { NodeProps } from '@xyflow/react';
import { UserCheck } from 'lucide-react';
import BaseNode from './BaseNode';
import type { HumanNodeData } from '@/types/workflow';

export default function HumanNode({ data, selected }: NodeProps) {
  const d = data as HumanNodeData;
  const typeLabel = {
    approve: '确认审批',
    input: '用户输入',
    select: '用户选择',
  };
  return (
    <BaseNode
      label={d.label}
      icon={<UserCheck size={14} />}
      color="#14b8a6"
      selected={selected}
    >
      <div className="space-y-1">
        <div className="bg-teal-50 text-teal-700 px-1.5 py-0.5 rounded text-[10px] inline-block">
          {typeLabel[d.interactionType] || '审批'}
        </div>
        {d.displayTemplate && (
          <div className="text-gray-500 truncate">{d.displayTemplate.slice(0, 40)}</div>
        )}
      </div>
    </BaseNode>
  );
}
