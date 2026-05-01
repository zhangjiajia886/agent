import { useState } from 'react';
import { Settings, Save, RotateCcw } from 'lucide-react';
import PageHeader from '@/components/layout/PageHeader';
import type { SystemSettings } from '@/types/entities';

const DEFAULT_SETTINGS: SystemSettings = {
  maxConcurrentWorkflows: 3,
  maxConcurrentLLMCalls: 2,
  maxConcurrentTools: 10,
  llmTimeoutSeconds: 120,
  toolTimeoutSeconds: 60,
  workflowTimeoutSeconds: 600,
  sandboxMode: 'subprocess',
  sandboxWorkDir: '/tmp/agent-sandbox',
  maxOutputSize: 100000,
  compressionStrategy: 'auto',
  compressionThreshold: 80,
  compressionModel: 'qwen3-7b',
};

const SECTIONS = [
  {
    id: 'resource',
    title: '资源限制',
    icon: '🔧',
    description: '控制并发数量，防止 GPU/CPU 资源耗尽',
  },
  {
    id: 'timeout',
    title: '默认超时',
    icon: '⏱️',
    description: '各类操作的最大执行时间',
  },
  {
    id: 'sandbox',
    title: '沙箱模式',
    icon: '🛡️',
    description: '工具执行的隔离方式',
  },
  {
    id: 'compression',
    title: '上下文压缩',
    icon: '📦',
    description: '当上下文接近窗口限制时自动压缩',
  },
];

export default function SettingsPage() {
  const [settings, setSettings] = useState<SystemSettings>({ ...DEFAULT_SETTINGS });
  const [activeSection, setActiveSection] = useState('resource');
  const [hasChanges, setHasChanges] = useState(false);

  const set = (partial: Partial<SystemSettings>) => {
    setSettings((prev) => ({ ...prev, ...partial }));
    setHasChanges(true);
  };

  function handleSave() {
    // 实际应发送到后端
    setHasChanges(false);
  }

  function handleReset() {
    setSettings({ ...DEFAULT_SETTINGS });
    setHasChanges(false);
  }

  return (
    <div className="flex flex-col h-full">
      <PageHeader
        title="系统设置"
        description="全局资源限制、超时、沙箱和压缩策略"
        icon={<Settings size={24} />}
        actions={
          <div className="flex items-center gap-2">
            {hasChanges && <span className="text-xs text-amber-600 bg-amber-50 px-2 py-1 rounded">有未保存的修改</span>}
            <button
              onClick={handleReset}
              className="flex items-center gap-1.5 px-3 py-2 text-sm bg-gray-100 hover:bg-gray-200 rounded-lg text-gray-700 transition-colors"
            >
              <RotateCcw size={14} />
              恢复默认
            </button>
            <button
              onClick={handleSave}
              disabled={!hasChanges}
              className="flex items-center gap-1.5 px-4 py-2 text-sm bg-purple-600 hover:bg-purple-700 rounded-lg text-white transition-colors disabled:opacity-50"
            >
              <Save size={14} />
              保存
            </button>
          </div>
        }
      />

      <div className="flex flex-1 overflow-hidden">
        {/* 左侧导航 */}
        <div className="w-52 bg-white border-r border-gray-200 py-4 shrink-0">
          {SECTIONS.map((section) => (
            <button
              key={section.id}
              onClick={() => setActiveSection(section.id)}
              className={`w-full text-left px-5 py-2.5 text-sm transition-colors ${
                activeSection === section.id
                  ? 'bg-purple-50 text-purple-700 font-medium border-r-2 border-purple-500'
                  : 'text-gray-600 hover:bg-gray-50'
              }`}
            >
              <span className="mr-2">{section.icon}</span>
              {section.title}
            </button>
          ))}
        </div>

        {/* 右侧内容 */}
        <div className="flex-1 overflow-y-auto p-6">
          <div className="max-w-2xl">
            {activeSection === 'resource' && (
              <SettingSection title="资源限制" description="控制并发数量，防止 GPU/CPU 资源耗尽">
                <SettingField label="最大并发工作流" description="同时运行的工作流数量上限">
                  <NumberInput value={settings.maxConcurrentWorkflows} onChange={(v) => set({ maxConcurrentWorkflows: v })} min={1} max={10} />
                </SettingField>
                <SettingField label="最大并发 LLM 调用" description="GPU 推理是瓶颈，Qwen3-32B 本地推理建议 ≤ 2">
                  <NumberInput value={settings.maxConcurrentLLMCalls} onChange={(v) => set({ maxConcurrentLLMCalls: v })} min={1} max={8} />
                </SettingField>
                <SettingField label="最大并发工具执行" description="同时执行的工具数量上限">
                  <NumberInput value={settings.maxConcurrentTools} onChange={(v) => set({ maxConcurrentTools: v })} min={1} max={50} />
                </SettingField>
              </SettingSection>
            )}

            {activeSection === 'timeout' && (
              <SettingSection title="默认超时" description="各类操作的最大执行时间，单位: 秒">
                <SettingField label="LLM 调用超时" description="单次 LLM 推理的最大等待时间">
                  <NumberInput value={settings.llmTimeoutSeconds} onChange={(v) => set({ llmTimeoutSeconds: v })} min={10} max={600} suffix="秒" />
                </SettingField>
                <SettingField label="工具执行超时" description="单次工具调用的最大等待时间">
                  <NumberInput value={settings.toolTimeoutSeconds} onChange={(v) => set({ toolTimeoutSeconds: v })} min={5} max={300} suffix="秒" />
                </SettingField>
                <SettingField label="工作流总超时" description="整个工作流执行的最大时间">
                  <NumberInput value={settings.workflowTimeoutSeconds} onChange={(v) => set({ workflowTimeoutSeconds: v })} min={30} max={3600} suffix="秒" />
                </SettingField>
              </SettingSection>
            )}

            {activeSection === 'sandbox' && (
              <SettingSection title="沙箱模式" description="工具执行（bash、python_exec 等）的隔离方式">
                <SettingField label="执行模式">
                  <div className="flex gap-3">
                    <label className={`flex-1 flex items-start gap-3 p-3 rounded-lg border cursor-pointer transition-colors ${
                      settings.sandboxMode === 'subprocess' ? 'border-purple-300 bg-purple-50' : 'border-gray-200 hover:border-gray-300'
                    }`}>
                      <input
                        type="radio" name="sandboxMode" value="subprocess"
                        checked={settings.sandboxMode === 'subprocess'}
                        onChange={() => set({ sandboxMode: 'subprocess' })}
                        className="mt-0.5"
                      />
                      <div>
                        <div className="text-sm font-medium text-gray-900">Subprocess</div>
                        <div className="text-xs text-gray-500">仅 timeout + 命令黑名单。适合开发调试。</div>
                      </div>
                    </label>
                    <label className={`flex-1 flex items-start gap-3 p-3 rounded-lg border cursor-pointer transition-colors ${
                      settings.sandboxMode === 'docker' ? 'border-purple-300 bg-purple-50' : 'border-gray-200 hover:border-gray-300'
                    }`}>
                      <input
                        type="radio" name="sandboxMode" value="docker"
                        checked={settings.sandboxMode === 'docker'}
                        onChange={() => set({ sandboxMode: 'docker' })}
                        className="mt-0.5"
                      />
                      <div>
                        <div className="text-sm font-medium text-gray-900">Docker</div>
                        <div className="text-xs text-gray-500">完全隔离（文件/CPU/内存/网络）。适合生产环境。</div>
                      </div>
                    </label>
                  </div>
                </SettingField>
                <SettingField label="工作目录" description="工具执行的默认工作目录">
                  <input className="input-base font-mono text-xs" value={settings.sandboxWorkDir} onChange={(e) => set({ sandboxWorkDir: e.target.value })} />
                </SettingField>
                <SettingField label="最大输出大小" description="工具输出的最大字符数">
                  <NumberInput value={settings.maxOutputSize} onChange={(v) => set({ maxOutputSize: v })} min={1000} max={1000000} suffix="字符" />
                </SettingField>
              </SettingSection>
            )}

            {activeSection === 'compression' && (
              <SettingSection title="上下文压缩" description="当上下文接近窗口限制时自动压缩（仿 Claude-Code autocompact）">
                <SettingField label="压缩策略">
                  <select className="input-base" value={settings.compressionStrategy} onChange={(e) => set({ compressionStrategy: e.target.value as SystemSettings['compressionStrategy'] })}>
                    <option value="auto">自动（短对话滑窗，长对话摘要）</option>
                    <option value="sliding_window">滑动窗口（保留最近 N 条）</option>
                    <option value="summarize">LLM 摘要压缩</option>
                  </select>
                </SettingField>
                <SettingField label="触发阈值" description="上下文占窗口比例达到此值时触发压缩">
                  <div className="flex items-center gap-3">
                    <input
                      type="range" min="50" max="95" step="5"
                      className="flex-1" value={settings.compressionThreshold}
                      onChange={(e) => set({ compressionThreshold: parseInt(e.target.value) })}
                    />
                    <span className="text-sm font-mono text-gray-700 w-12 text-right">{settings.compressionThreshold}%</span>
                  </div>
                </SettingField>
                <SettingField label="压缩用模型" description="执行摘要压缩的模型（建议用小模型降低成本）">
                  <select className="input-base" value={settings.compressionModel} onChange={(e) => set({ compressionModel: e.target.value })}>
                    <option value="qwen3-7b">qwen3-7b（推荐 · 快速）</option>
                    <option value="qwen3-32b">qwen3-32b（高质量 · 较慢）</option>
                  </select>
                </SettingField>
              </SettingSection>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

function SettingSection({ title, description, children }: { title: string; description: string; children: React.ReactNode }) {
  return (
    <div>
      <h2 className="text-lg font-semibold text-gray-900 mb-1">{title}</h2>
      <p className="text-sm text-gray-500 mb-6">{description}</p>
      <div className="space-y-5">{children}</div>
    </div>
  );
}

function SettingField({ label, description, children }: { label: string; description?: string; children: React.ReactNode }) {
  return (
    <div className="pb-5 border-b border-gray-100 last:border-0 last:pb-0">
      <div className="flex items-start justify-between gap-8">
        <div className="min-w-0">
          <label className="text-sm font-medium text-gray-800">{label}</label>
          {description && <p className="text-xs text-gray-400 mt-0.5">{description}</p>}
        </div>
        <div className="shrink-0 w-72">{children}</div>
      </div>
    </div>
  );
}

function NumberInput({
  value, onChange, min, max, suffix,
}: {
  value: number; onChange: (v: number) => void; min?: number; max?: number; suffix?: string;
}) {
  return (
    <div className="flex items-center gap-2">
      <input
        type="number" className="input-base w-24 text-right"
        value={value}
        min={min} max={max}
        onChange={(e) => onChange(parseInt(e.target.value) || 0)}
      />
      {suffix && <span className="text-xs text-gray-500">{suffix}</span>}
    </div>
  );
}
