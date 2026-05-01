import type { NodeProps } from '@xyflow/react';
import { Bot } from 'lucide-react';
import BaseNode from './BaseNode';
import type { LLMNodeData } from '@/types/workflow';

export default function LLMNode({ data, selected }: NodeProps) {
  const d = data as LLMNodeData;
  return (
    <BaseNode
      label={d.label}
      icon={<Bot size={14} />}
      color="#8b5cf6"
      selected={selected}
    >
      <div className="space-y-1">
        <div className="flex items-center justify-between">
          <span className="text-gray-400">模型</span>
          <span className="font-mono bg-purple-50 text-purple-700 px-1.5 py-0.5 rounded text-[10px]">
            {d.model || 'qwen3-32b'}
          </span>
        </div>
        <div className="flex items-center justify-between">
          <span className="text-gray-400">温度</span>
          <span>{d.temperature ?? 0.7}</span>
        </div>
        {d.systemPrompt && (
          <div className="text-gray-500 truncate border-t border-gray-100 pt-1 mt-1">
            {d.systemPrompt.slice(0, 50)}…
          </div>
        )}
        {d.enableTools && (
          <div className="text-amber-600 text-[10px]">
            🔧 工具已启用 ({d.allowedTools?.length || 0})
          </div>
        )}
      </div>
    </BaseNode>
  );
}
