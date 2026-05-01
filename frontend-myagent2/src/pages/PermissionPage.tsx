import { useState } from 'react';
import { Shield, Plus, Trash2, RotateCcw, AlertTriangle } from 'lucide-react';
import PageHeader from '@/components/layout/PageHeader';

interface ToolPermission {
  toolName: string;
  level: 'auto_allow' | 'always_ask' | 'deny';
  riskLevel: 'high' | 'medium' | 'low';
}

const LEVEL_META: Record<string, { label: string; color: string; bgColor: string; emoji: string }> = {
  auto_allow: { label: '自动放行', color: 'text-green-700', bgColor: 'bg-green-50 border-green-200', emoji: '🟢' },
  always_ask: { label: '每次确认', color: 'text-amber-700', bgColor: 'bg-amber-50 border-amber-200', emoji: '🟡' },
  deny: { label: '完全禁止', color: 'text-red-700', bgColor: 'bg-red-50 border-red-200', emoji: '🔴' },
};

const RISK_LABELS: Record<string, { label: string; color: string }> = {
  high: { label: '⚠️ 高', color: 'text-red-600' },
  medium: { label: '⚠️ 中', color: 'text-amber-600' },
  low: { label: '✅ 低', color: 'text-green-600' },
};

const DEFAULT_PERMISSIONS: ToolPermission[] = [
  { toolName: 'bash', level: 'always_ask', riskLevel: 'high' },
  { toolName: 'python_exec', level: 'always_ask', riskLevel: 'high' },
  { toolName: 'write_file', level: 'always_ask', riskLevel: 'high' },
  { toolName: 'http_request', level: 'always_ask', riskLevel: 'medium' },
  { toolName: 'sql_query', level: 'always_ask', riskLevel: 'medium' },
  { toolName: 'read_file', level: 'auto_allow', riskLevel: 'low' },
  { toolName: 'grep_search', level: 'auto_allow', riskLevel: 'low' },
];

const DEFAULT_BLACKLIST = [
  'rm -rf /',
  'mkfs',
  'dd if=/dev/zero',
  ':(){:|:&};:',
  'chmod -R 777 /',
];

export default function PermissionPage() {
  const [permissions, setPermissions] = useState<ToolPermission[]>(DEFAULT_PERMISSIONS);
  const [blacklist, setBlacklist] = useState<string[]>(DEFAULT_BLACKLIST);
  const [newRule, setNewRule] = useState('');

  function updateLevel(toolName: string, level: ToolPermission['level']) {
    setPermissions((prev) => prev.map((p) => p.toolName === toolName ? { ...p, level } : p));
  }

  function addBlacklistRule() {
    if (newRule.trim() && !blacklist.includes(newRule.trim())) {
      setBlacklist([...blacklist, newRule.trim()]);
      setNewRule('');
    }
  }

  return (
    <div className="flex flex-col h-full">
      <PageHeader
        title="权限策略"
        description="对标 Claude Code 三级权限控制"
        icon={<Shield size={24} />}
        actions={
          <button
            onClick={() => setPermissions(DEFAULT_PERMISSIONS)}
            className="flex items-center gap-1.5 px-3 py-2 text-sm bg-gray-100 hover:bg-gray-200 rounded-lg text-gray-700 transition-colors"
          >
            <RotateCcw size={14} />
            恢复默认
          </button>
        }
      />

      <div className="flex-1 overflow-y-auto p-6 space-y-6">
        {/* 策略说明 */}
        <div className="grid grid-cols-3 gap-3">
          {Object.entries(LEVEL_META).map(([key, meta]) => (
            <div key={key} className={`rounded-xl border p-4 ${meta.bgColor}`}>
              <div className="flex items-center gap-2 mb-1">
                <span className="text-lg">{meta.emoji}</span>
                <span className={`text-sm font-semibold ${meta.color}`}>{meta.label}</span>
              </div>
              <p className="text-xs text-gray-600">
                {key === 'auto_allow' && '自动放行，不需用户确认。适用于低风险只读操作。'}
                {key === 'always_ask' && '每次执行前通过 HumanNode 确认。适用于有副作用的操作。'}
                {key === 'deny' && '完全禁止执行，即使工作流包含该工具也会拒绝。'}
              </p>
            </div>
          ))}
        </div>

        {/* 全局工具权限 */}
        <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
          <div className="px-5 py-3 border-b border-gray-100">
            <h3 className="text-sm font-semibold text-gray-700">全局工具权限</h3>
          </div>
          <table className="w-full">
            <thead>
              <tr className="border-b border-gray-50 bg-gray-50/50">
                <th className="text-left text-[11px] font-medium text-gray-400 px-5 py-2">工具名称</th>
                <th className="text-center text-[11px] font-medium text-gray-400 px-5 py-2">危险等级</th>
                <th className="text-center text-[11px] font-medium text-gray-400 px-5 py-2">当前策略</th>
                <th className="text-center text-[11px] font-medium text-gray-400 px-5 py-2">修改</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-50">
              {permissions.map((perm) => {
                const risk = RISK_LABELS[perm.riskLevel];
                const lvl = LEVEL_META[perm.level];
                return (
                  <tr key={perm.toolName} className="hover:bg-gray-50/50 transition-colors">
                    <td className="px-5 py-3">
                      <span className="font-mono text-sm font-medium text-gray-900">{perm.toolName}</span>
                    </td>
                    <td className="px-5 py-3 text-center">
                      <span className={`text-xs ${risk.color}`}>{risk.label}</span>
                    </td>
                    <td className="px-5 py-3 text-center">
                      <span className={`text-xs font-medium ${lvl.color}`}>{lvl.emoji} {lvl.label}</span>
                    </td>
                    <td className="px-5 py-3 text-center">
                      <select
                        className="text-xs border border-gray-200 rounded px-2 py-1 outline-none focus:border-purple-400"
                        value={perm.level}
                        onChange={(e) => updateLevel(perm.toolName, e.target.value as ToolPermission['level'])}
                      >
                        <option value="auto_allow">🟢 自动放行</option>
                        <option value="always_ask">🟡 每次确认</option>
                        <option value="deny">🔴 完全禁止</option>
                      </select>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>

        {/* 命令黑名单 */}
        <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
          <div className="px-5 py-3 border-b border-gray-100 flex items-center gap-2">
            <AlertTriangle size={16} className="text-red-500" />
            <h3 className="text-sm font-semibold text-gray-700">命令黑名单</h3>
            <span className="text-xs text-gray-400">以下命令在任何情况下都不允许执行</span>
          </div>
          <div className="p-5 space-y-2">
            {blacklist.map((rule, i) => (
              <div key={i} className="flex items-center gap-2 bg-red-50 border border-red-100 rounded-lg px-3 py-2">
                <code className="flex-1 text-sm font-mono text-red-700">{rule}</code>
                <button
                  onClick={() => setBlacklist(blacklist.filter((_, j) => j !== i))}
                  className="p-1 text-red-300 hover:text-red-500 transition-colors"
                >
                  <Trash2 size={14} />
                </button>
              </div>
            ))}
            <div className="flex items-center gap-2 mt-3">
              <input
                className="input-base flex-1 font-mono text-sm"
                value={newRule}
                onChange={(e) => setNewRule(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && addBlacklistRule()}
                placeholder="输入危险命令模式..."
              />
              <button
                onClick={addBlacklistRule}
                disabled={!newRule.trim()}
                className="flex items-center gap-1 px-3 py-1.5 text-sm bg-red-50 text-red-600 hover:bg-red-100 rounded-lg transition-colors disabled:opacity-50"
              >
                <Plus size={14} />
                添加
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
