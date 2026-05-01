import { useState } from 'react';
import { X, Plus, Trash2, ChevronDown, ChevronUp, Zap } from 'lucide-react';
import type { MultiAgentConfig } from '@/api/executions';

const PRESETS: { label: string; mode: string; agents: MultiAgentConfig[] }[] = [
  {
    label: '写作流水线',
    mode: 'sequential',
    agents: [
      { name: 'planner', system_prompt: '你是规划师，将用户任务分解为详细大纲，输出结构化大纲。', output_var: 'outline' },
      { name: 'writer',  system_prompt: '你是写作专家，根据大纲撰写完整高质量文章。', input_var: 'outline' },
    ],
  },
  {
    label: '代码审查',
    mode: 'sequential',
    agents: [
      { name: 'reviewer',   system_prompt: '你是高级工程师，审查代码并列出问题清单。', output_var: 'issues' },
      { name: 'fixer',      system_prompt: '你是代码修复专家，根据问题清单提供修复方案。', input_var: 'issues' },
    ],
  },
  {
    label: '多角度分析',
    mode: 'parallel',
    agents: [
      { name: 'optimist',  system_prompt: '你从乐观角度分析，重点列举有利因素。' },
      { name: 'critic',    system_prompt: '你从批判角度分析，重点列举风险和不足。' },
      { name: 'strategist',system_prompt: '你从战略角度分析，提供可行建议。' },
    ],
  },
  {
    label: 'Supervisor 路由',
    mode: 'supervisor',
    agents: [
      { name: 'coordinator', system_prompt: '你是协调者。分析任务后，用 <route>worker_name: 具体任务</route> 将子任务路由给对应专家。可用 Worker: analyst / coder。完成后汇总结果。' },
      { name: 'analyst',     system_prompt: '你是数据分析专家，负责数据分析和统计。' },
      { name: 'coder',       system_prompt: '你是编程专家，负责代码实现和调试。' },
    ],
  },
];

const MODES = [
  { value: 'sequential', label: '串行', desc: '依次执行，前者输出传给后者' },
  { value: 'parallel',   label: '并行', desc: '同时执行，结果各自独立' },
  { value: 'supervisor', label: 'Supervisor', desc: 'Agent[0] 动态路由任务给其他 Agent' },
];

interface Props {
  open: boolean;
  onClose: () => void;
  onStart: (mode: string, agents: MultiAgentConfig[]) => void;
}

function AgentRow({
  agent,
  index,
  onChange,
  onDelete,
}: {
  agent: MultiAgentConfig;
  index: number;
  onChange: (updated: MultiAgentConfig) => void;
  onDelete: () => void;
}) {
  const [expanded, setExpanded] = useState(index === 0);

  return (
    <div className="border border-gray-200 rounded-xl overflow-hidden">
      <div className="flex items-center gap-2 px-3 py-2 bg-gray-50">
        <span className="w-5 h-5 rounded-full bg-purple-100 text-purple-600 text-[10px] font-bold flex items-center justify-center shrink-0">
          {index + 1}
        </span>
        <input
          value={agent.name}
          onChange={e => onChange({ ...agent, name: e.target.value })}
          placeholder={`agent_${index + 1}`}
          className="flex-1 text-sm bg-transparent border-none outline-none font-medium text-gray-700 placeholder-gray-400"
        />
        <button onClick={() => setExpanded(v => !v)} className="p-1 text-gray-400 hover:text-gray-600">
          {expanded ? <ChevronUp size={13} /> : <ChevronDown size={13} />}
        </button>
        <button onClick={onDelete} className="p-1 text-gray-300 hover:text-red-500">
          <Trash2 size={13} />
        </button>
      </div>

      {expanded && (
        <div className="p-3 space-y-2.5 bg-white">
          <div>
            <label className="text-[11px] text-gray-400 mb-1 block">系统提示词</label>
            <textarea
              value={agent.system_prompt ?? ''}
              onChange={e => onChange({ ...agent, system_prompt: e.target.value })}
              rows={3}
              placeholder="描述该 Agent 的角色和职责…"
              className="w-full text-xs border border-gray-200 rounded-lg px-3 py-2 resize-y focus:outline-none focus:ring-2 focus:ring-purple-300"
            />
          </div>
          <div className="grid grid-cols-2 gap-2">
            <div>
              <label className="text-[11px] text-gray-400 mb-1 block">输入变量</label>
              <input
                value={agent.input_var ?? ''}
                onChange={e => onChange({ ...agent, input_var: e.target.value })}
                placeholder="如 outline"
                className="w-full text-xs border border-gray-200 rounded-lg px-2.5 py-1.5 focus:outline-none focus:ring-2 focus:ring-purple-300"
              />
            </div>
            <div>
              <label className="text-[11px] text-gray-400 mb-1 block">输出变量</label>
              <input
                value={agent.output_var ?? ''}
                onChange={e => onChange({ ...agent, output_var: e.target.value })}
                placeholder="如 result"
                className="w-full text-xs border border-gray-200 rounded-lg px-2.5 py-1.5 focus:outline-none focus:ring-2 focus:ring-purple-300"
              />
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export default function AgentConfigDrawer({ open, onClose, onStart }: Props) {
  const [mode, setMode] = useState('sequential');
  const [agents, setAgents] = useState<MultiAgentConfig[]>([
    { name: 'agent_1', system_prompt: '' },
    { name: 'agent_2', system_prompt: '' },
  ]);

  const applyPreset = (preset: typeof PRESETS[number]) => {
    setMode(preset.mode);
    setAgents(preset.agents.map(a => ({ ...a })));
  };

  const addAgent = () =>
    setAgents(prev => [...prev, { name: `agent_${prev.length + 1}`, system_prompt: '' }]);

  const updateAgent = (idx: number, updated: MultiAgentConfig) =>
    setAgents(prev => prev.map((a, i) => (i === idx ? updated : a)));

  const deleteAgent = (idx: number) =>
    setAgents(prev => prev.filter((_, i) => i !== idx));

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50 flex">
      {/* Backdrop */}
      <div className="flex-1 bg-black/30" onClick={onClose} />

      {/* Drawer */}
      <div className="w-96 bg-white flex flex-col shadow-2xl">
        {/* Header */}
        <div className="flex items-center gap-2 px-5 py-4 border-b border-gray-200">
          <Zap size={16} className="text-purple-500" />
          <h2 className="text-base font-semibold text-gray-800 flex-1">Multi-Agent 配置</h2>
          <button onClick={onClose} className="p-1.5 hover:bg-gray-100 rounded-lg text-gray-400">
            <X size={16} />
          </button>
        </div>

        <div className="flex-1 overflow-y-auto px-5 py-4 space-y-5">
          {/* Presets */}
          <div>
            <p className="text-xs font-medium text-gray-500 mb-2">快捷预设</p>
            <div className="grid grid-cols-2 gap-1.5">
              {PRESETS.map(p => (
                <button
                  key={p.label}
                  onClick={() => applyPreset(p)}
                  className="text-xs px-2.5 py-1.5 border border-gray-200 rounded-lg hover:bg-purple-50 hover:border-purple-300 hover:text-purple-600 transition-colors text-gray-600 text-left"
                >
                  {p.label}
                </button>
              ))}
            </div>
          </div>

          {/* Mode */}
          <div>
            <p className="text-xs font-medium text-gray-500 mb-2">调度模式</p>
            <div className="space-y-1.5">
              {MODES.map(m => (
                <label key={m.value} className="flex items-start gap-2.5 p-2.5 border border-gray-200 rounded-xl cursor-pointer hover:bg-gray-50 transition-colors">
                  <input
                    type="radio"
                    name="mode"
                    value={m.value}
                    checked={mode === m.value}
                    onChange={() => setMode(m.value)}
                    className="mt-0.5 accent-purple-600"
                  />
                  <div>
                    <div className="text-sm font-medium text-gray-700">{m.label}</div>
                    <div className="text-[11px] text-gray-400">{m.desc}</div>
                  </div>
                </label>
              ))}
            </div>
          </div>

          {/* Agent list */}
          <div>
            <div className="flex items-center justify-between mb-2">
              <p className="text-xs font-medium text-gray-500">Agent 配置</p>
              <button
                onClick={addAgent}
                className="flex items-center gap-1 text-xs text-purple-600 hover:text-purple-700"
              >
                <Plus size={12} />添加 Agent
              </button>
            </div>
            <div className="space-y-2">
              {agents.map((a, i) => (
                <AgentRow
                  key={i}
                  agent={a}
                  index={i}
                  onChange={updated => updateAgent(i, updated)}
                  onDelete={() => deleteAgent(i)}
                />
              ))}
            </div>
          </div>
        </div>

        {/* Footer */}
        <div className="px-5 py-4 border-t border-gray-200 flex gap-2">
          <button
            onClick={onClose}
            className="flex-1 py-2 border border-gray-200 rounded-xl text-sm text-gray-600 hover:bg-gray-50"
          >
            取消
          </button>
          <button
            disabled={agents.length < 2 || agents.some(a => !a.name.trim())}
            onClick={() => { onStart(mode, agents); onClose(); }}
            className="flex-2 flex-1 py-2 bg-purple-600 text-white rounded-xl text-sm font-medium hover:bg-purple-700 disabled:opacity-40"
          >
            <Zap size={13} className="inline mr-1" />开始运行
          </button>
        </div>
      </div>
    </div>
  );
}
