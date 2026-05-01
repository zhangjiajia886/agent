import { X } from 'lucide-react';
import { useWorkflowStore } from '@/stores/workflowStore';
import type { FlowNode, LLMNodeData, ToolNodeData, ConditionNodeData, LoopNodeData, HumanNodeData, VariableNodeData, SkillNodeData } from '@/types/workflow';
import Editor from '@monaco-editor/react';

export default function NodeConfigPanel() {
  const selectedNodeId = useWorkflowStore((s) => s.selectedNodeId);
  const nodes = useWorkflowStore((s) => s.nodes);
  const updateNodeData = useWorkflowStore((s) => s.updateNodeData);
  const selectNode = useWorkflowStore((s) => s.selectNode);
  const deleteNode = useWorkflowStore((s) => s.deleteNode);

  const node = nodes.find((n) => n.id === selectedNodeId) as FlowNode | undefined;
  if (!node) return null;

  const update = (data: Record<string, unknown>) => updateNodeData(node.id, data);

  return (
    <div className="w-80 bg-white border-l border-gray-200 flex flex-col h-full overflow-y-auto">
      {/* 头部 */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-gray-200">
        <div>
          <input
            className="text-sm font-semibold text-gray-800 border-none outline-none bg-transparent w-full"
            value={node.data.label as string}
            onChange={(e) => update({ label: e.target.value })}
          />
          <div className="text-[10px] text-gray-400 uppercase">{node.type}</div>
        </div>
        <button
          onClick={() => selectNode(null)}
          className="p-1 hover:bg-gray-100 rounded"
        >
          <X size={16} className="text-gray-400" />
        </button>
      </div>

      {/* 内容区域 */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {node.type === 'start' && <IOListConfig title="输入变量" hint="运行工作流时可填写这些变量" values={((node.data.outputs as string[]) || [])} update={(values) => update({ outputs: values })} />}
        {node.type === 'end' && <IOListConfig title="输出变量" hint="执行结果会从上下文中提取这些变量" values={((node.data.outputs as string[]) || [])} update={(values) => update({ outputs: values })} />}
        {node.type === 'llm' && <LLMConfig data={node.data as LLMNodeData} update={update} />}
        {node.type === 'tool' && <ToolConfig data={node.data as ToolNodeData} update={update} />}
        {node.type === 'condition' && <ConditionConfig data={node.data as ConditionNodeData} update={update} />}
        {node.type === 'loop' && <LoopConfig data={node.data as LoopNodeData} update={update} />}
        {node.type === 'human' && <HumanConfig data={node.data as HumanNodeData} update={update} />}
        {node.type === 'variable' && <VariableConfig data={node.data as VariableNodeData} update={update} />}
        {node.type === 'skill' && <SkillConfig data={node.data as SkillNodeData} update={update} />}

        {/* 通用配置 */}
        <Section title="通用配置">
          <Field label="描述">
            <textarea
              className="input-base resize-none h-16"
              value={(node.data.description as string) || ''}
              onChange={(e) => update({ description: e.target.value })}
              placeholder="节点说明..."
            />
          </Field>
          <Field label="超时 (秒)">
            <input
              type="number"
              className="input-base w-20"
              value={(node.data.timeout as number) || ''}
              onChange={(e) => update({ timeout: parseInt(e.target.value) || undefined })}
              placeholder="无限制"
            />
          </Field>
        </Section>
      </div>

      {/* 底部操作 */}
      <div className="px-4 py-3 border-t border-gray-200 flex gap-2">
        <button
          onClick={() => { deleteNode(node.id); selectNode(null); }}
          className="text-xs text-red-500 hover:text-red-700 hover:bg-red-50 px-3 py-1.5 rounded"
        >
          删除节点
        </button>
      </div>
    </div>
  );
}

// ===== LLM 配置 =====
function LLMConfig({ data, update }: { data: LLMNodeData; update: (d: Record<string, unknown>) => void }) {
  return (
    <>
      <Section title="系统 Prompt">
        <div className="border border-gray-200 rounded-lg overflow-hidden">
          <Editor
            height="160px"
            language="markdown"
            theme="vs-light"
            value={data.systemPrompt || ''}
            onChange={(v) => update({ systemPrompt: v || '' })}
            options={{
              minimap: { enabled: false },
              wordWrap: 'on',
              lineNumbers: 'off',
              fontSize: 12,
              scrollBeyondLastLine: false,
              renderLineHighlight: 'none',
              padding: { top: 8 },
            }}
          />
        </div>
      </Section>

      <Section title="用户消息模板">
        <div className="border border-gray-200 rounded-lg overflow-hidden">
          <Editor
            height="80px"
            language="markdown"
            theme="vs-light"
            value={data.userPromptTemplate || ''}
            onChange={(v) => update({ userPromptTemplate: v || '' })}
            options={{
              minimap: { enabled: false },
              wordWrap: 'on',
              lineNumbers: 'off',
              fontSize: 12,
              scrollBeyondLastLine: false,
              renderLineHighlight: 'none',
              padding: { top: 8 },
            }}
          />
        </div>
        <div className="text-[10px] text-gray-400 mt-1">
          使用 {'{{变量名}}'} 插入变量
        </div>
      </Section>

      <Section title="模型配置">
        <Field label="模型">
          <select
            className="input-base"
            value={data.model || 'qwen3-32b'}
            onChange={(e) => update({ model: e.target.value })}
          >
            <option value="qwen3-32b">Qwen3-32B</option>
            <option value="qwen3-7b">Qwen3-7B</option>
            <option value="qwen3-1.7b">Qwen3-1.7B</option>
          </select>
        </Field>
        <Field label={`温度: ${data.temperature ?? 0.7}`}>
          <input
            type="range"
            min="0" max="2" step="0.1"
            className="w-full"
            value={data.temperature ?? 0.7}
            onChange={(e) => update({ temperature: parseFloat(e.target.value) })}
          />
        </Field>
        <Field label="最大 Token">
          <input
            type="number"
            className="input-base w-24"
            value={data.maxTokens || 2048}
            onChange={(e) => update({ maxTokens: parseInt(e.target.value) })}
          />
        </Field>
      </Section>

      <Section title="输出">
        <Field label="输出格式">
          <select
            className="input-base"
            value={data.outputFormat || 'text'}
            onChange={(e) => update({ outputFormat: e.target.value })}
          >
            <option value="text">文本</option>
            <option value="json">JSON</option>
            <option value="markdown">Markdown</option>
          </select>
        </Field>
        <Field label="输出变量">
          <input
            className="input-base font-mono"
            value={data.outputVariable || ''}
            onChange={(e) => update({ outputVariable: e.target.value })}
            placeholder="result"
          />
        </Field>
      </Section>
    </>
  );
}

// ===== Tool 配置 =====
function ToolConfig({ data, update }: { data: ToolNodeData; update: (d: Record<string, unknown>) => void }) {
  return (
    <Section title="工具配置">
      <Field label="工具名称">
        <select
          className="input-base"
          value={data.toolName || ''}
          onChange={(e) => update({ toolName: e.target.value })}
        >
          <option value="">选择工具...</option>
          <option value="bash">Bash 命令</option>
          <option value="read_file">读取文件</option>
          <option value="write_file">写入文件</option>
          <option value="grep_search">搜索文件</option>
          <option value="http_request">HTTP 请求</option>
          <option value="sql_query">SQL 查询</option>
          <option value="python_exec">Python 执行</option>
        </select>
      </Field>
      <Field label="输出变量">
        <input
          className="input-base font-mono"
          value={data.outputVariable || ''}
          onChange={(e) => update({ outputVariable: e.target.value })}
        />
      </Field>
    </Section>
  );
}

// ===== Condition 配置 =====
function ConditionConfig({ data, update }: { data: ConditionNodeData; update: (d: Record<string, unknown>) => void }) {
  const branches = data.branches || [];
  return (
    <Section title="分支条件">
      {branches.map((b, i) => (
        <div key={b.id} className="space-y-1 p-2 bg-gray-50 rounded-lg">
          <Field label={`分支 ${i + 1}: ${b.label}`}>
            <input
              className="input-base font-mono text-[11px]"
              value={b.condition}
              onChange={(e) => {
                const newBranches = [...branches];
                newBranches[i] = { ...b, condition: e.target.value };
                update({ branches: newBranches });
              }}
              placeholder="条件表达式"
            />
          </Field>
        </div>
      ))}
    </Section>
  );
}

// ===== Loop 配置 =====
function LoopConfig({ data, update }: { data: LoopNodeData; update: (d: Record<string, unknown>) => void }) {
  return (
    <Section title="循环配置">
      <Field label="最大迭代次数">
        <input
          type="number"
          className="input-base w-20"
          value={data.maxIterations || 10}
          onChange={(e) => update({ maxIterations: parseInt(e.target.value) })}
        />
      </Field>
      <Field label="退出条件">
        <input
          className="input-base font-mono text-[11px]"
          value={data.exitCondition || ''}
          onChange={(e) => update({ exitCondition: e.target.value })}
          placeholder="JS 表达式"
        />
      </Field>
    </Section>
  );
}

// ===== Human 配置 =====
function HumanConfig({ data, update }: { data: HumanNodeData; update: (d: Record<string, unknown>) => void }) {
  return (
    <Section title="审批配置">
      <Field label="交互类型">
        <select
          className="input-base"
          value={data.interactionType || 'approve'}
          onChange={(e) => update({ interactionType: e.target.value })}
        >
          <option value="approve">确认审批</option>
          <option value="input">用户输入</option>
          <option value="select">用户选择</option>
        </select>
      </Field>
      <Field label="展示模板">
        <textarea
          className="input-base resize-none h-16"
          value={data.displayTemplate || ''}
          onChange={(e) => update({ displayTemplate: e.target.value })}
          placeholder="将执行: {{sql}}"
        />
      </Field>
    </Section>
  );
}

// ===== Variable 配置 =====
function VariableConfig({ data, update }: { data: VariableNodeData; update: (d: Record<string, unknown>) => void }) {
  return (
    <Section title="变量赋值">
      <Field label="变量名">
        <input
          className="input-base font-mono"
          value={data.outputVariable || ''}
          onChange={(e) => update({ outputVariable: e.target.value })}
        />
      </Field>
      <Field label="表达式">
        <input
          className="input-base font-mono text-[11px]"
          value={data.expression || ''}
          onChange={(e) => update({ expression: e.target.value })}
          placeholder="JS 表达式"
        />
      </Field>
    </Section>
  );
}

// ===== Skill 配置 =====
function SkillConfig({ data, update }: { data: SkillNodeData; update: (d: Record<string, unknown>) => void }) {
  return (
    <>
      <Section title="Skill 配置">
        <Field label="Skill 名称">
          <input
            className="input-base font-mono"
            value={data.skillName || ''}
            onChange={(e) => update({ skillName: e.target.value })}
            placeholder="例如: batch, debug, verify"
          />
        </Field>
        <Field label="Skill ID">
          <input
            className="input-base font-mono text-[11px]"
            value={data.skillId || ''}
            onChange={(e) => update({ skillId: e.target.value })}
            placeholder="skill_xxx"
          />
        </Field>
        <Field label="来源类型">
          <select
            className="input-base"
            value={data.sourceType || 'user'}
            onChange={(e) => update({ sourceType: e.target.value })}
          >
            <option value="user">用户自定义</option>
            <option value="file">文件 (SKILL.md)</option>
            <option value="bundled">Bundled (内置)</option>
            <option value="legacy_command">Legacy 命令</option>
            <option value="community">社区</option>
          </select>
        </Field>
      </Section>

      <Section title="执行配置">
        <Field label="执行模式">
          <select
            className="input-base"
            value={data.contextMode || 'inline'}
            onChange={(e) => update({ contextMode: e.target.value })}
          >
            <option value="inline">Inline (同步注入)</option>
            <option value="fork">Fork (子 Agent 执行)</option>
          </select>
        </Field>
        <Field label="参数模板">
          <input
            className="input-base font-mono text-[11px]"
            value={data.argsTemplate || ''}
            onChange={(e) => update({ argsTemplate: e.target.value })}
            placeholder="{{input}}"
          />
        </Field>
        <Field label="模型覆盖">
          <select
            className="input-base"
            value={data.modelOverride || ''}
            onChange={(e) => update({ modelOverride: e.target.value })}
          >
            <option value="">默认</option>
            <option value="qwen3-32b">Qwen3-32B</option>
            <option value="qwen3-7b">Qwen3-7B</option>
          </select>
        </Field>
        <Field label="输出变量">
          <input
            className="input-base font-mono"
            value={data.outputVariable || ''}
            onChange={(e) => update({ outputVariable: e.target.value })}
            placeholder="skill_result"
          />
        </Field>
      </Section>

      <Section title="工具权限">
        <div className="flex flex-wrap gap-1">
          {(data.allowedTools || []).map((tool, i) => (
            <span key={i} className="text-[10px] bg-amber-50 text-amber-700 px-1.5 py-0.5 rounded">
              {tool}
            </span>
          ))}
          {(!data.allowedTools || data.allowedTools.length === 0) && (
            <span className="text-[10px] text-gray-400">无工具权限限制</span>
          )}
        </div>
      </Section>

      {data.whenToUse && (
        <Section title="触发场景">
          <p className="text-[11px] text-gray-600 leading-relaxed">{data.whenToUse}</p>
        </Section>
      )}

      {data.migrationStatus && (
        <Section title="迁移状态">
          <span className={`text-[10px] px-2 py-0.5 rounded ${
            data.migrationStatus === 'full' ? 'bg-green-50 text-green-700' :
            data.migrationStatus === 'partial' ? 'bg-yellow-50 text-yellow-700' :
            data.migrationStatus === 'degraded' ? 'bg-red-50 text-red-700' :
            'bg-gray-100 text-gray-600'
          }`}>
            {data.migrationStatus}
          </span>
        </Section>
      )}
    </>
  );
}

function IOListConfig({ title, hint, values, update }: { title: string; hint: string; values: string[]; update: (values: string[]) => void }) {
  const text = values.join('\n');
  return (
    <Section title={title}>
      <textarea
        className="input-base resize-none h-28 font-mono text-[11px]"
        value={text}
        onChange={(e) => update(e.target.value.split('\n').map((item) => item.trim()).filter(Boolean))}
        placeholder="每行一个变量名"
      />
      <div className="text-[10px] text-gray-400">{hint}</div>
    </Section>
  );
}

// ===== 通用 UI 组件 =====
function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div>
      <h3 className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-2">
        {title}
      </h3>
      <div className="space-y-2">{children}</div>
    </div>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div>
      <label className="text-[11px] text-gray-500 block mb-0.5">{label}</label>
      {children}
    </div>
  );
}
