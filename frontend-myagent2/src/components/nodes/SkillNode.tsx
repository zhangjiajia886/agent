import type { NodeProps } from '@xyflow/react';
import { BrainCircuit } from 'lucide-react';
import BaseNode from './BaseNode';
import type { SkillNodeData } from '@/types/workflow';

const SOURCE_BADGE: Record<string, { label: string; cls: string }> = {
  bundled:        { label: 'Bundled',  cls: 'bg-blue-50 text-blue-700' },
  file:           { label: 'File',     cls: 'bg-green-50 text-green-700' },
  legacy_command: { label: 'Legacy',   cls: 'bg-gray-100 text-gray-600' },
  community:      { label: 'Community',cls: 'bg-orange-50 text-orange-700' },
  user:           { label: 'User',     cls: 'bg-purple-50 text-purple-700' },
};

const STATUS_DOT: Record<string, string> = {
  full:     'bg-green-500',
  partial:  'bg-yellow-500',
  degraded: 'bg-red-500',
  pending:  'bg-gray-400',
};

export default function SkillNode({ data, selected }: NodeProps) {
  const d = data as SkillNodeData;
  const source = SOURCE_BADGE[d.sourceType] || SOURCE_BADGE.user;
  const statusColor = STATUS_DOT[d.migrationStatus] || '';

  return (
    <BaseNode
      label={d.label}
      icon={<BrainCircuit size={14} />}
      color="#a855f7"
      selected={selected}
    >
      <div className="space-y-1.5">
        {/* Skill 名称 + 来源徽章 */}
        <div className="flex items-center gap-1.5 flex-wrap">
          {d.skillName && (
            <span className="font-mono text-[10px] bg-purple-50 text-purple-700 px-1.5 py-0.5 rounded">
              {d.skillName}
            </span>
          )}
          <span className={`text-[9px] px-1.5 py-0.5 rounded ${source.cls}`}>
            {source.label}
          </span>
          {statusColor && (
            <span className={`inline-block w-1.5 h-1.5 rounded-full ${statusColor}`} />
          )}
        </div>

        {/* 执行模式 */}
        <div className="flex items-center justify-between">
          <span className="text-gray-400">模式</span>
          <span className={`text-[10px] px-1.5 py-0.5 rounded ${
            d.contextMode === 'fork'
              ? 'bg-cyan-50 text-cyan-700'
              : 'bg-gray-100 text-gray-600'
          }`}>
            {d.contextMode === 'fork' ? 'Fork' : 'Inline'}
          </span>
        </div>

        {/* 工具权限 */}
        {d.allowedTools && d.allowedTools.length > 0 && (
          <div className="flex items-center gap-1 flex-wrap border-t border-gray-100 pt-1">
            {d.allowedTools.slice(0, 4).map((t) => (
              <span key={t} className="text-[9px] bg-amber-50 text-amber-700 px-1 py-0.5 rounded">
                {t}
              </span>
            ))}
            {d.allowedTools.length > 4 && (
              <span className="text-[9px] text-gray-400">+{d.allowedTools.length - 4}</span>
            )}
          </div>
        )}

        {/* 输出变量 */}
        {d.outputVariable && (
          <div className="flex items-center justify-between text-gray-400">
            <span>输出</span>
            <code className="font-mono text-[10px]">{d.outputVariable}</code>
          </div>
        )}
      </div>
    </BaseNode>
  );
}
