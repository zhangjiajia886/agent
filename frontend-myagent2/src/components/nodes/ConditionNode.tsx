import { Handle, Position } from '@xyflow/react';
import type { NodeProps } from '@xyflow/react';
import { GitBranch } from 'lucide-react';
import type { ConditionNodeData } from '@/types/workflow';

export default function ConditionNode({ data, selected }: NodeProps) {
  const d = data as ConditionNodeData;
  const branches = d.branches || [];

  return (
    <div
      className={`
        relative bg-white rounded-xl shadow-md border-2 min-w-[180px] max-w-[260px]
        transition-all duration-150
        ${selected ? 'shadow-lg ring-2 ring-blue-400' : 'hover:shadow-lg'}
      `}
      style={{ borderColor: selected ? '#3b82f6' : '#06b6d4' }}
    >
      {/* 输入 handle — 左侧 */}
      <Handle
        type="target"
        position={Position.Left}
        id="target"
        className="!w-3 !h-3 !bg-gray-400 !border-2 !border-white"
      />

      {/* 标题 */}
      <div className="flex items-center gap-2 px-3 py-2 rounded-t-lg text-white text-sm font-medium bg-cyan-500">
        <GitBranch size={14} />
        <span className="truncate">{d.label}</span>
      </div>

      {/* 分支列表 — 每行右侧有对应 handle */}
      <div className="px-3 py-2 text-xs space-y-1 pr-5">
        {branches.map((branch, i) => (
          <div key={branch.id} className="flex items-center gap-1 text-gray-600 relative h-5">
            <span className="w-3 h-3 rounded-full bg-cyan-100 text-cyan-700 text-[9px] flex items-center justify-center font-bold shrink-0">
              {i + 1}
            </span>
            <span className="truncate">{branch.label}</span>
            {/* 每个分支的 output handle — 右侧，与行对齐 */}
            <Handle
              key={branch.id}
              type="source"
              position={Position.Right}
              id={branch.targetHandle}
              className="!w-2.5 !h-2.5 !bg-cyan-400 !border-2 !border-white !-right-4"
            />
          </div>
        ))}
      </div>
    </div>
  );
}
