import { useState, useEffect, useCallback } from 'react';
import { BrainCircuit, Plus, Pencil, Copy, Trash2, Search, Shield, GitBranch, AlertCircle, Zap } from 'lucide-react';
import Editor from '@monaco-editor/react';
import PageHeader from '@/components/layout/PageHeader';
import { skillApi } from '@/api/skills';
import SkillStatsPanel from '@/components/panels/SkillStatsPanel';
import type { Skill } from '@/types/entities';

const CATEGORY_LABELS: Record<string, { label: string; color: string }> = {
  coding: { label: '编程', color: 'bg-blue-50 text-blue-700 border-blue-200' },
  data_analysis: { label: '数据分析', color: 'bg-green-50 text-green-700 border-green-200' },
  data: { label: '数据', color: 'bg-green-50 text-green-700 border-green-200' },
  text_processing: { label: '文本处理', color: 'bg-amber-50 text-amber-700 border-amber-200' },
  custom: { label: '自定义', color: 'bg-purple-50 text-purple-700 border-purple-200' },
  general: { label: '通用', color: 'bg-gray-50 text-gray-700 border-gray-200' },
  devops: { label: 'DevOps', color: 'bg-orange-50 text-orange-700 border-orange-200' },
  development: { label: '开发', color: 'bg-blue-50 text-blue-700 border-blue-200' },
  writing: { label: '写作', color: 'bg-pink-50 text-pink-700 border-pink-200' },
};

const SOURCE_LABELS: Record<string, { label: string; color: string }> = {
  user: { label: '用户', color: 'bg-gray-50 text-gray-600 border-gray-200' },
  file: { label: '文件', color: 'bg-cyan-50 text-cyan-600 border-cyan-200' },
  bundled: { label: 'Bundled', color: 'bg-indigo-50 text-indigo-600 border-indigo-200' },
  legacy_command: { label: 'Legacy', color: 'bg-yellow-50 text-yellow-700 border-yellow-200' },
  community: { label: '社区', color: 'bg-teal-50 text-teal-600 border-teal-200' },
};

const STATUS_LABELS: Record<string, { label: string; color: string }> = {
  full: { label: '完整', color: 'bg-green-50 text-green-700 border-green-200' },
  partial: { label: '部分', color: 'bg-yellow-50 text-yellow-700 border-yellow-200' },
  degraded: { label: '降级', color: 'bg-orange-50 text-orange-700 border-orange-200' },
  pending: { label: '待定', color: 'bg-gray-50 text-gray-500 border-gray-200' },
};

const MODE_LABELS: Record<string, { label: string; color: string }> = {
  inline: { label: 'Inline', color: 'bg-blue-50 text-blue-600 border-blue-200' },
  fork: { label: 'Fork', color: 'bg-violet-50 text-violet-600 border-violet-200' },
};

export default function SkillListPage() {
  const [skills, setSkills] = useState<Skill[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedSkill, setSelectedSkill] = useState<Skill | null>(null);
  const [filterCategory, setFilterCategory] = useState<string>('all');
  const [filterSource, setFilterSource] = useState<string>('all');
  const [filterStatus, setFilterStatus] = useState<string>('all');
  const [filterMode, setFilterMode] = useState<string>('all');
  const [searchQuery, setSearchQuery] = useState('');
  const [isEditing, setIsEditing] = useState(false);

  const fetchSkills = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await skillApi.list({
        category: filterCategory === 'all' ? undefined : filterCategory,
        search: searchQuery || undefined,
        source_type: filterSource === 'all' ? undefined : filterSource,
        migration_status: filterStatus === 'all' ? undefined : filterStatus,
        context_mode: filterMode === 'all' ? undefined : filterMode,
      });
      setSkills((res.items ?? []) as unknown as Skill[]);
    } catch (e) {
      setError(e instanceof Error ? e.message : '加载失败');
    } finally {
      setLoading(false);
    }
  }, [filterCategory, filterSource, filterStatus, filterMode, searchQuery]);

  useEffect(() => { fetchSkills(); }, [fetchSkills]);

  const filtered = skills;

  async function handleSave(updated: Skill) {
    try {
      await skillApi.update(updated.id, updated);
      await fetchSkills();
      setSelectedSkill(updated);
      setIsEditing(false);
    } catch (e) {
      console.error('Save failed', e);
    }
  }

  async function handleCreate() {
    try {
      const res = await skillApi.create({
        name: '新建 Skill',
        description: '',
        category: 'custom',
        tags: [],
        content: '# 新建 Skill\n\n## 角色\n描述角色...\n\n## 任务\n{{input}}\n\n## 输出\n输出格式...',
        is_builtin: false,
        source_type: 'user',
        source_path: '',
        source_repo: '',
        allowed_tools: [],
        arguments: [],
        argument_hint: '',
        when_to_use: '',
        context_mode: '',
        agent: '',
        model: '',
        variables: ['input'],
        required_tools: [],
        migration_status: '',
        migration_notes: '',
        content_hash: '',
      });
      await fetchSkills();
      const created = skills.find(s => s.id === res.id);
      if (created) { setSelectedSkill(created); setIsEditing(true); }
    } catch (e) {
      console.error('Create failed', e);
    }
  }

  async function handleDelete(id: string) {
    try {
      await skillApi.delete(id);
      await fetchSkills();
      if (selectedSkill?.id === id) setSelectedSkill(null);
    } catch (e) {
      console.error('Delete failed', e);
    }
  }

  async function handleDuplicate(skill: Skill) {
    try {
      const { id: _id, created_at: _ca, updated_at: _ua, ...rest } = skill;
      const res = await skillApi.create({ ...rest, name: `${skill.name} (副本)`, source_type: 'user' });
      await fetchSkills();
      const dup = skills.find(s => s.id === res.id);
      if (dup) setSelectedSkill(dup);
    } catch (e) {
      console.error('Duplicate failed', e);
    }
  }

  if (loading) {
    return (
      <div className="flex flex-col h-full">
        <PageHeader
          title="Skill 管理"
          description="Markdown 技能模板，可嵌入 LLM 节点的 System Prompt"
          icon={<BrainCircuit size={24} />}
        />
        <div className="flex-1 flex items-center justify-center text-sm text-gray-400">正在加载 Skills...</div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex flex-col h-full">
        <PageHeader
          title="Skill 管理"
          description="Markdown 技能模板，可嵌入 LLM 节点的 System Prompt"
          icon={<BrainCircuit size={24} />}
        />
        <div className="flex-1 flex items-center justify-center px-6">
          <div className="text-sm text-red-500 bg-red-50 border border-red-200 rounded-lg px-4 py-3">加载 Skills 失败：{error}</div>
        </div>
      </div>
    );
  }

  return (
    <div className="flex flex-col h-full">
      <PageHeader
        title="Skill 管理"
        description="Markdown 技能模板，可嵌入 LLM 节点的 System Prompt"
        icon={<BrainCircuit size={24} />}
        actions={
          <button
            onClick={handleCreate}
            className="flex items-center gap-1.5 px-4 py-2 text-sm bg-purple-600 hover:bg-purple-700 rounded-lg text-white transition-colors"
          >
            <Plus size={16} />
            新建 Skill
          </button>
        }
      />

      <div className="flex flex-1 overflow-hidden">
        {/* 左侧列表 */}
        <div className="w-80 border-r border-gray-200 flex flex-col bg-white shrink-0">
          {/* 搜索+筛选 */}
          <div className="p-3 border-b border-gray-100 space-y-2">
            <div className="relative">
              <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
              <input
                type="text"
                placeholder="搜索 Skill..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="w-full pl-8 pr-3 py-1.5 text-sm border border-gray-200 rounded-lg outline-none focus:border-purple-400"
              />
            </div>
            <div className="flex gap-1 flex-wrap">
              <FilterChip label="全部" active={filterCategory === 'all'} onClick={() => setFilterCategory('all')} />
              {Object.entries(CATEGORY_LABELS).map(([key, val]) => (
                <FilterChip key={key} label={val.label} active={filterCategory === key} onClick={() => setFilterCategory(key)} />
              ))}
            </div>
            <div className="flex gap-1 flex-wrap">
              <FilterChip label="全部来源" active={filterSource === 'all'} onClick={() => setFilterSource('all')} />
              {Object.entries(SOURCE_LABELS).map(([key, val]) => (
                <FilterChip key={key} label={val.label} active={filterSource === key} onClick={() => setFilterSource(key)} />
              ))}
            </div>
            <div className="flex gap-1 flex-wrap">
              <FilterChip label="全部状态" active={filterStatus === 'all'} onClick={() => setFilterStatus('all')} />
              {Object.entries(STATUS_LABELS).map(([key, val]) => (
                <FilterChip key={key} label={val.label} active={filterStatus === key} onClick={() => setFilterStatus(key)} />
              ))}
            </div>
            <div className="flex gap-1 flex-wrap">
              <FilterChip label="全部模式" active={filterMode === 'all'} onClick={() => setFilterMode('all')} />
              {Object.entries(MODE_LABELS).map(([key, val]) => (
                <FilterChip key={key} label={val.label} active={filterMode === key} onClick={() => setFilterMode(key)} />
              ))}
            </div>
          </div>

          {/* 统计面板 */}
          <div className="px-3 py-3 border-b border-gray-100">
            <SkillStatsPanel />
          </div>

          {/* 列表 */}
          <div className="flex-1 overflow-y-auto">
            {filtered.map((skill) => {
              const cat = CATEGORY_LABELS[skill.category] ?? { label: skill.category || '未分类', color: 'bg-gray-50 text-gray-700 border-gray-200' };
              const isSelected = selectedSkill?.id === skill.id;
              return (
                <div
                  key={skill.id}
                  onClick={() => { setSelectedSkill(skill); setIsEditing(false); }}
                  className={`px-4 py-3 border-b border-gray-50 cursor-pointer transition-colors ${
                    isSelected ? 'bg-purple-50 border-l-2 border-l-purple-500' : 'hover:bg-gray-50'
                  }`}
                >
                  <div className="flex items-start justify-between">
                    <div className="min-w-0 flex-1">
                      <div className="flex items-center gap-2">
                        <span className="text-sm font-medium text-gray-900 truncate">{skill.name}</span>
                        <span className={`text-[10px] px-1.5 py-0.5 rounded border ${cat.color}`}>
                          {cat.label}
                        </span>
                      </div>
                      <p className="text-xs text-gray-500 mt-0.5 truncate">{skill.description}</p>
                      <div className="flex items-center gap-1.5 mt-1.5 flex-wrap">
                        <SkillBadge map={SOURCE_LABELS} value={skill.source_type} fallback="user" />
                        {skill.migration_status && <SkillBadge map={STATUS_LABELS} value={skill.migration_status} />}
                        {skill.context_mode && <SkillBadge map={MODE_LABELS} value={skill.context_mode} />}
                      </div>
                    </div>
                  </div>
                </div>
              );
            })}
            {filtered.length === 0 && (
              <div className="text-center py-10 text-sm text-gray-400">无匹配结果</div>
            )}
          </div>
        </div>

        {/* 右侧详情/编辑 */}
        <div className="flex-1 flex flex-col overflow-hidden bg-gray-50">
          {selectedSkill ? (
            isEditing ? (
              <SkillEditor skill={selectedSkill} onSave={handleSave} onCancel={() => setIsEditing(false)} />
            ) : (
              <SkillDetail
                skill={selectedSkill}
                onEdit={() => setIsEditing(true)}
                onDuplicate={() => handleDuplicate(selectedSkill)}
                onDelete={() => handleDelete(selectedSkill.id)}
              />
            )
          ) : (
            <div className="flex-1 flex items-center justify-center text-gray-400 text-sm">
              <div className="text-center">
                <BrainCircuit size={40} className="mx-auto mb-3 opacity-30" />
                <p>选择一个 Skill 查看详情</p>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

// ===== Skill 详情视图 =====
function SkillDetail({
  skill,
  onEdit,
  onDuplicate,
  onDelete,
}: {
  skill: Skill;
  onEdit: () => void;
  onDuplicate: () => void;
  onDelete: () => void;
}) {
  const cat = CATEGORY_LABELS[skill.category] ?? { label: skill.category, color: 'bg-gray-50 text-gray-600 border-gray-200' };
  return (
    <div className="flex-1 flex flex-col overflow-hidden">
      {/* 头部 */}
      <div className="px-6 py-4 bg-white border-b border-gray-200 flex items-center justify-between">
        <div>
          <div className="flex items-center gap-2">
            <h2 className="text-base font-semibold text-gray-900">{skill.name}</h2>
            <span className={`text-[10px] px-1.5 py-0.5 rounded border ${cat.color}`}>{cat.label}</span>
            <SkillBadge map={SOURCE_LABELS} value={skill.source_type} fallback="user" />
            {skill.context_mode && <SkillBadge map={MODE_LABELS} value={skill.context_mode} />}
          </div>
          <p className="text-sm text-gray-500 mt-0.5">{skill.description}</p>
        </div>
        <div className="flex items-center gap-2">
          <button onClick={onDuplicate} className="p-2 rounded-lg hover:bg-gray-100 text-gray-400 hover:text-gray-700 transition-colors" title="复制">
            <Copy size={16} />
          </button>
          <button onClick={onDelete} className="p-2 rounded-lg hover:bg-red-50 text-gray-400 hover:text-red-500 transition-colors" title="删除">
            <Trash2 size={16} />
          </button>
          <button
            onClick={onEdit}
            className="flex items-center gap-1.5 px-3 py-1.5 text-sm bg-purple-600 hover:bg-purple-700 rounded-lg text-white transition-colors"
          >
            <Pencil size={14} />
            编辑
          </button>
        </div>
      </div>

      {/* 增强元信息面板 */}
      <div className="px-6 py-3 bg-white border-b border-gray-100 space-y-3 text-xs overflow-y-auto max-h-64">
        {/* 来源信息 */}
        <DetailSection icon={<GitBranch size={13} />} title="来源信息">
          <InfoItem label="来源" value={SOURCE_LABELS[skill.source_type]?.label ?? skill.source_type ?? 'user'} />
          {skill.source_repo && <InfoItem label="仓库" value={skill.source_repo} />}
          {skill.source_path && <InfoItem label="路径" value={skill.source_path} mono />}
        </DetailSection>

        {/* 执行配置 */}
        <DetailSection icon={<Zap size={13} />} title="执行配置">
          <InfoItem label="模式" value={skill.context_mode || '(默认)'} />
          {skill.agent && <InfoItem label="Agent" value={skill.agent} />}
          {skill.model && <InfoItem label="模型" value={skill.model} />}
        </DetailSection>

        {/* 工具权限 */}
        <DetailSection icon={<Shield size={13} />} title="工具权限">
          <div className="flex flex-wrap gap-1 mt-0.5">
            {(skill.allowed_tools ?? []).length > 0
              ? (skill.allowed_tools ?? []).map((t) => (
                  <span key={t} className="bg-blue-50 text-blue-600 border border-blue-200 px-1.5 py-0.5 rounded text-[10px]">{t}</span>
                ))
              : <span className="text-gray-400">无限制</span>}
          </div>
        </DetailSection>

        {/* 触发场景 */}
        {skill.when_to_use && (
          <DetailSection icon={<AlertCircle size={13} />} title="触发场景">
            <p className="text-gray-600 mt-0.5 leading-relaxed">{skill.when_to_use}</p>
          </DetailSection>
        )}

        {/* 变量 */}
        <DetailSection icon={<BrainCircuit size={13} />} title="变量">
          <div className="flex flex-wrap gap-1 mt-0.5">
            {skill.variables.length > 0
              ? skill.variables.map((v) => (
                  <code key={v} className="bg-purple-50 text-purple-600 px-1.5 py-0.5 rounded font-mono text-[10px]">
                    {`{{${v}}}`}
                  </code>
                ))
              : <span className="text-gray-400">无</span>}
          </div>
        </DetailSection>

        {/* 依赖工具 */}
        {(skill.required_tools ?? []).length > 0 && (
          <DetailSection icon={<Shield size={13} />} title="依赖工具">
            <div className="flex flex-wrap gap-1 mt-0.5">
              {(skill.required_tools ?? []).map((t) => (
                <span key={t} className="bg-gray-100 text-gray-600 px-1.5 py-0.5 rounded text-[10px]">{t}</span>
              ))}
            </div>
          </DetailSection>
        )}

        {/* 迁移状态 */}
        {skill.migration_status && (
          <DetailSection icon={<AlertCircle size={13} />} title="迁移状态">
            <div className="flex items-center gap-2 mt-0.5">
              <SkillBadge map={STATUS_LABELS} value={skill.migration_status} />
              {skill.migration_notes && <span className="text-gray-500">{skill.migration_notes}</span>}
            </div>
          </DetailSection>
        )}
      </div>

      {/* Markdown 内容预览 (Monaco readonly) */}
      <div className="flex-1 overflow-hidden">
        <Editor
          height="100%"
          language="markdown"
          theme="vs-light"
          value={skill.content}
          options={{
            readOnly: true,
            minimap: { enabled: false },
            wordWrap: 'on',
            lineNumbers: 'on',
            fontSize: 13,
            scrollBeyondLastLine: false,
            padding: { top: 16 },
          }}
        />
      </div>
    </div>
  );
}

// ===== Skill 编辑器 =====
function SkillEditor({
  skill,
  onSave,
  onCancel,
}: {
  skill: Skill;
  onSave: (s: Skill) => void;
  onCancel: () => void;
}) {
  const [form, setForm] = useState<Skill>({ ...skill });
  const set = (partial: Partial<Skill>) => setForm((prev) => ({ ...prev, ...partial }));

  // 自动提取 {{变量}} 
  function handleContentChange(value: string | undefined) {
    const content = value ?? '';
    const vars = [...new Set(Array.from(content.matchAll(/\{\{(\w+)\}\}/g)).map((m) => m[1]))];
    set({ content, variables: vars });
  }

  return (
    <div className="flex-1 flex flex-col overflow-hidden">
      {/* 头部 */}
      <div className="px-6 py-3 bg-white border-b border-gray-200 flex items-center justify-between">
        <div className="flex items-center gap-3 flex-1">
          <input
            className="text-base font-semibold text-gray-900 border-none outline-none bg-transparent flex-1"
            value={form.name}
            onChange={(e) => set({ name: e.target.value })}
            placeholder="Skill 名称"
          />
        </div>
        <div className="flex items-center gap-2">
          <button onClick={onCancel} className="px-3 py-1.5 text-sm text-gray-600 hover:bg-gray-100 rounded-lg transition-colors">
            取消
          </button>
          <button
            onClick={() => onSave({ ...form, updated_at: new Date().toISOString() })}
            className="px-4 py-1.5 text-sm bg-purple-600 hover:bg-purple-700 text-white rounded-lg transition-colors"
          >
            保存
          </button>
        </div>
      </div>

      {/* 基础信息 */}
      <div className="px-6 py-3 bg-white border-b border-gray-100 flex items-center gap-4 flex-wrap">
        <div className="flex items-center gap-2">
          <label className="text-xs text-gray-500">分类:</label>
          <select
            className="text-xs border border-gray-200 rounded px-2 py-1 outline-none focus:border-purple-400"
            value={form.category}
            onChange={(e) => set({ category: e.target.value })}
          >
            {Object.entries(CATEGORY_LABELS).map(([key, val]) => (
              <option key={key} value={key}>{val.label}</option>
            ))}
          </select>
        </div>
        <div className="flex items-center gap-2 flex-1 min-w-[200px]">
          <label className="text-xs text-gray-500">描述:</label>
          <input
            className="flex-1 text-xs border border-gray-200 rounded px-2 py-1 outline-none focus:border-purple-400"
            value={form.description}
            onChange={(e) => set({ description: e.target.value })}
            placeholder="简要描述..."
          />
        </div>
        <div className="text-xs text-gray-400">
          变量: {form.variables.map((v) => (
            <code key={v} className="bg-purple-50 text-purple-600 px-1 rounded mx-0.5 font-mono">{`{{${v}}}`}</code>
          ))}
        </div>
      </div>

      {/* 高级配置 */}
      <div className="px-6 py-3 bg-white border-b border-gray-100 overflow-y-auto max-h-56">
        <div className="grid grid-cols-2 gap-x-6 gap-y-2">
          <EditorField label="来源类型">
            <select className="w-full text-xs border border-gray-200 rounded px-2 py-1 outline-none focus:border-purple-400" value={form.source_type} onChange={(e) => set({ source_type: e.target.value })}>
              {Object.entries(SOURCE_LABELS).map(([k, v]) => <option key={k} value={k}>{v.label}</option>)}
            </select>
          </EditorField>
          <EditorField label="执行模式">
            <select className="w-full text-xs border border-gray-200 rounded px-2 py-1 outline-none focus:border-purple-400" value={form.context_mode} onChange={(e) => set({ context_mode: e.target.value })}>
              <option value="">(默认)</option>
              {Object.entries(MODE_LABELS).map(([k, v]) => <option key={k} value={k}>{v.label}</option>)}
            </select>
          </EditorField>
          <EditorField label="模型">
            <input className="w-full text-xs border border-gray-200 rounded px-2 py-1 outline-none focus:border-purple-400" value={form.model} onChange={(e) => set({ model: e.target.value })} placeholder="如 qwen3-32b" />
          </EditorField>
          <EditorField label="Agent">
            <input className="w-full text-xs border border-gray-200 rounded px-2 py-1 outline-none focus:border-purple-400" value={form.agent} onChange={(e) => set({ agent: e.target.value })} placeholder="关联 Agent 名称" />
          </EditorField>
          <EditorField label="工具权限" full>
            <TagInput
              values={form.allowed_tools ?? []}
              onChange={(v) => set({ allowed_tools: v })}
              placeholder="输入工具名后回车..."
            />
          </EditorField>
          <EditorField label="触发场景" full>
            <textarea
              className="w-full text-xs border border-gray-200 rounded px-2 py-1 outline-none focus:border-purple-400 min-h-[2rem] resize-y"
              value={form.when_to_use}
              onChange={(e) => set({ when_to_use: e.target.value })}
              placeholder="描述何时应使用该 Skill..."
              rows={2}
            />
          </EditorField>
          <EditorField label="参数提示">
            <input className="w-full text-xs border border-gray-200 rounded px-2 py-1 outline-none focus:border-purple-400" value={form.argument_hint} onChange={(e) => set({ argument_hint: e.target.value })} placeholder="$ARGUMENTS 提示" />
          </EditorField>
          <EditorField label="迁移状态">
            <select className="w-full text-xs border border-gray-200 rounded px-2 py-1 outline-none focus:border-purple-400" value={form.migration_status} onChange={(e) => set({ migration_status: e.target.value })}>
              <option value="">(无)</option>
              {Object.entries(STATUS_LABELS).map(([k, v]) => <option key={k} value={k}>{v.label}</option>)}
            </select>
          </EditorField>
          <EditorField label="标签" full>
            <TagInput
              values={form.tags ?? []}
              onChange={(v) => set({ tags: v })}
              placeholder="输入标签后回车..."
            />
          </EditorField>
        </div>
      </div>

      {/* Monaco 编辑器 */}
      <div className="flex-1 overflow-hidden">
        <Editor
          height="100%"
          language="markdown"
          theme="vs-light"
          value={form.content}
          onChange={handleContentChange}
          options={{
            minimap: { enabled: false },
            wordWrap: 'on',
            lineNumbers: 'on',
            fontSize: 13,
            scrollBeyondLastLine: false,
            padding: { top: 16 },
            tabSize: 2,
          }}
        />
      </div>
    </div>
  );
}

// ===== 辅助组件 =====
function FilterChip({ label, active, onClick }: { label: string; active: boolean; onClick: () => void }) {
  return (
    <button
      onClick={onClick}
      className={`px-2.5 py-1 text-[11px] rounded-md transition-colors ${
        active ? 'bg-purple-100 text-purple-700 font-medium' : 'bg-gray-100 text-gray-500 hover:bg-gray-200'
      }`}
    >
      {label}
    </button>
  );
}

function SkillBadge({ map, value, fallback }: { map: Record<string, { label: string; color: string }>; value?: string; fallback?: string }) {
  const key = value || fallback || '';
  const info = map[key];
  if (!info) return null;
  return <span className={`text-[10px] px-1.5 py-0.5 rounded border ${info.color}`}>{info.label}</span>;
}

function DetailSection({ icon, title, children }: { icon: React.ReactNode; title: string; children: React.ReactNode }) {
  return (
    <div>
      <div className="flex items-center gap-1.5 text-gray-500 font-medium mb-1">
        {icon}
        <span>{title}</span>
      </div>
      <div className="pl-5">{children}</div>
    </div>
  );
}

function InfoItem({ label, value, mono }: { label: string; value: string; mono?: boolean }) {
  return (
    <div className="flex items-center gap-2 text-gray-600">
      <span className="text-gray-400 w-10 shrink-0">{label}:</span>
      <span className={mono ? 'font-mono text-[10px] bg-gray-50 px-1.5 py-0.5 rounded' : ''}>{value}</span>
    </div>
  );
}

function EditorField({ label, full, children }: { label: string; full?: boolean; children: React.ReactNode }) {
  return (
    <div className={`flex flex-col gap-1 ${full ? 'col-span-2' : ''}`}>
      <label className="text-[10px] text-gray-400 font-medium">{label}</label>
      {children}
    </div>
  );
}

function TagInput({ values, onChange, placeholder }: { values: string[]; onChange: (v: string[]) => void; placeholder?: string }) {
  const [input, setInput] = useState('');

  function handleKeyDown(e: React.KeyboardEvent<HTMLInputElement>) {
    if (e.key === 'Enter' && input.trim()) {
      e.preventDefault();
      const tag = input.trim();
      if (!values.includes(tag)) {
        onChange([...values, tag]);
      }
      setInput('');
    } else if (e.key === 'Backspace' && !input && values.length > 0) {
      onChange(values.slice(0, -1));
    }
  }

  return (
    <div className="flex flex-wrap gap-1 items-center border border-gray-200 rounded px-2 py-1 focus-within:border-purple-400 min-h-[1.75rem]">
      {values.map((tag) => (
        <span key={tag} className="flex items-center gap-0.5 bg-purple-50 text-purple-600 text-[10px] px-1.5 py-0.5 rounded">
          {tag}
          <button type="button" onClick={() => onChange(values.filter((t) => t !== tag))} className="text-purple-400 hover:text-purple-700 ml-0.5">&times;</button>
        </span>
      ))}
      <input
        className="flex-1 min-w-[80px] text-xs border-none outline-none bg-transparent"
        value={input}
        onChange={(e) => setInput(e.target.value)}
        onKeyDown={handleKeyDown}
        placeholder={values.length === 0 ? placeholder : ''}
      />
    </div>
  );
}
