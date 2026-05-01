import { useEffect, useMemo, useState } from 'react';
import { FileText, Plus, Pencil, Trash2, X, Search, Copy } from 'lucide-react';
import Editor from '@monaco-editor/react';
import { toast } from 'sonner';
import PageHeader from '@/components/layout/PageHeader';
import type { PromptTemplate } from '@/types/entities';
import { promptApi, type PromptDTO } from '@/api/prompts';

const TYPE_LABELS: Record<string, { label: string; color: string }> = {
  system: { label: 'System Prompt', color: 'bg-purple-50 text-purple-700 border-purple-200' },
  user: { label: 'User Template', color: 'bg-blue-50 text-blue-700 border-blue-200' },
  output_format: { label: '输出格式', color: 'bg-green-50 text-green-700 border-green-200' },
  snippet: { label: '片段', color: 'bg-amber-50 text-amber-700 border-amber-200' },
};

function dtoToTemplate(dto: PromptDTO): PromptTemplate {
  return {
    id: dto.id,
    name: dto.name,
    type: (dto.type as PromptTemplate['type']) || 'snippet',
    content: dto.content,
    variables: dto.variables ?? [],
    tags: dto.tags ?? [],
    source: dto.is_builtin ? 'builtin' : 'user',
    usageCount: 0,
    createdAt: dto.created_at,
    updatedAt: dto.updated_at,
  };
}

export default function PromptListPage() {
  const [templates, setTemplates] = useState<PromptTemplate[]>([]);
  const [filterType, setFilterType] = useState<string>('all');
  const [searchQuery, setSearchQuery] = useState('');
  const [editDialog, setEditDialog] = useState<PromptTemplate | null>(null);
  const [showDialog, setShowDialog] = useState(false);

  async function loadTemplates() {
    try {
      const res = await promptApi.list({
        type: filterType === 'all' ? undefined : filterType,
        search: searchQuery || undefined,
      });
      setTemplates(res.items.map(dtoToTemplate));
    } catch {
      toast.error('加载 Prompt 模板失败');
    }
  }

  useEffect(() => {
    loadTemplates();
  }, [filterType, searchQuery]);

  const grouped = useMemo(() => templates.reduce((acc, t) => {
    (acc[t.type] ??= []).push(t);
    return acc;
  }, {} as Record<string, PromptTemplate[]>), [templates]);

  async function handleSave(tpl: PromptTemplate) {
    try {
      const exists = templates.some((t) => t.id === tpl.id);
      if (exists) {
        await promptApi.update(tpl.id, {
          name: tpl.name,
          type: tpl.type,
          content: tpl.content,
          variables: tpl.variables,
          tags: tpl.tags,
        });
      } else {
        await promptApi.create({
          name: tpl.name,
          type: tpl.type,
          content: tpl.content,
          variables: tpl.variables,
          tags: tpl.tags,
        });
      }
      await loadTemplates();
      setShowDialog(false);
      setEditDialog(null);
      toast.success('Prompt 模板已保存');
    } catch {
      toast.error('保存 Prompt 模板失败');
    }
  }

  async function handleDelete(id: string) {
    try {
      await promptApi.delete(id);
      await loadTemplates();
    } catch {
      toast.error('删除 Prompt 模板失败');
    }
  }

  function handleDuplicate(tpl: PromptTemplate) {
    setEditDialog({
      ...tpl,
      id: `pt_${Date.now()}`,
      name: `${tpl.name} (副本)`,
      source: 'user',
      usageCount: 0,
      updatedAt: new Date().toISOString(),
    });
    setShowDialog(true);
  }

  return (
    <div className="flex flex-col h-full">
      <PageHeader
        title="Prompt 模板库"
        description={`真实模板资产，共 ${templates.length} 个；系统预设可直接复制后修改`}
        icon={<FileText size={24} />}
        actions={
          <button onClick={() => { setEditDialog(null); setShowDialog(true); }} className="flex items-center gap-1.5 px-4 py-2 text-sm bg-purple-600 hover:bg-purple-700 rounded-lg text-white transition-colors">
            <Plus size={16} />
            新建模板
          </button>
        }
      />

      <div className="flex items-center gap-3 px-6 py-3 border-b border-gray-100 bg-white">
        <div className="relative">
          <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
          <input
            type="text"
            placeholder="搜索模板..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="pl-8 pr-3 py-1.5 text-sm border border-gray-200 rounded-lg outline-none focus:border-purple-400 w-64"
          />
        </div>
        <div className="flex gap-1">
          <FilterChip label="全部" active={filterType === 'all'} onClick={() => setFilterType('all')} />
          {Object.entries(TYPE_LABELS).map(([key, val]) => (
            <FilterChip key={key} label={val.label} active={filterType === key} onClick={() => setFilterType(key)} />
          ))}
        </div>
      </div>

      <div className="flex-1 overflow-y-auto p-6 space-y-6">
        {Object.entries(grouped).map(([type, list]) => {
          const typeMeta = TYPE_LABELS[type] ?? TYPE_LABELS.snippet;
          return (
            <div key={type}>
              <h3 className="text-sm font-semibold text-gray-700 mb-3 flex items-center gap-2">
                <span className={`text-[10px] px-2 py-0.5 rounded-full border ${typeMeta.color}`}>{typeMeta.label}</span>
                <span className="text-xs text-gray-400">{list.length}</span>
              </h3>
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
                {list.map((tpl) => (
                  <PromptCard
                    key={tpl.id}
                    template={tpl}
                    onEdit={() => { setEditDialog(tpl); setShowDialog(true); }}
                    onDuplicate={() => handleDuplicate(tpl)}
                    onDelete={() => handleDelete(tpl.id)}
                  />
                ))}
              </div>
            </div>
          );
        })}
        {templates.length === 0 && (
          <div className="text-center py-20 text-gray-400 text-sm">无匹配模板</div>
        )}
      </div>

      {showDialog && (
        <PromptEditDialog
          template={editDialog}
          onSave={handleSave}
          onClose={() => { setShowDialog(false); setEditDialog(null); }}
        />
      )}
    </div>
  );
}

function PromptCard({
  template: tpl,
  onEdit,
  onDuplicate,
  onDelete,
}: {
  template: PromptTemplate;
  onEdit: () => void;
  onDuplicate: () => void;
  onDelete: () => void;
}) {
  return (
    <div className="bg-white rounded-xl border border-gray-200 hover:border-purple-200 hover:shadow-sm transition-all group">
      <div className="px-4 py-3">
        <div className="flex items-start justify-between">
          <h4 className="text-sm font-medium text-gray-900">{tpl.name}</h4>
          <div className="flex items-center gap-0.5 opacity-0 group-hover:opacity-100 transition-opacity">
            <button onClick={onDuplicate} className="p-1 rounded hover:bg-gray-100 text-gray-400"><Copy size={13} /></button>
            <button onClick={onDelete} className="p-1 rounded hover:bg-red-50 text-gray-400 hover:text-red-500"><Trash2 size={13} /></button>
          </div>
        </div>
        <p className="text-xs text-gray-500 mt-1 line-clamp-3 font-mono leading-relaxed">{tpl.content.slice(0, 120)}...</p>
        <div className="flex items-center gap-2 mt-2">
          {tpl.tags.map((tag) => (
            <span key={tag} className="text-[10px] bg-gray-50 text-gray-500 px-1.5 py-0.5 rounded border border-gray-100">{tag}</span>
          ))}
          {tpl.variables.length > 0 && tpl.variables.map((v) => (
            <code key={v} className="text-[10px] bg-purple-50 text-purple-600 px-1 py-0.5 rounded font-mono">{`{{${v}}}`}</code>
          ))}
        </div>
      </div>
      <div className="px-4 py-2 border-t border-gray-50 flex items-center justify-between">
        <span className="text-[10px] text-gray-400">使用 {tpl.usageCount} 次</span>
        <button onClick={onEdit} className="text-xs text-purple-600 hover:text-purple-700 flex items-center gap-1">
          <Pencil size={12} /> 编辑
        </button>
      </div>
    </div>
  );
}

function PromptEditDialog({
  template,
  onSave,
  onClose,
}: {
  template: PromptTemplate | null;
  onSave: (t: PromptTemplate) => void;
  onClose: () => void;
}) {
  const isNew = !template;
  const [form, setForm] = useState<PromptTemplate>(
    template ?? {
      id: `pt_${Date.now()}`,
      name: '',
      type: 'snippet',
      content: '',
      variables: [],
      tags: [],
      source: 'user',
      usageCount: 0,
      createdAt: new Date().toISOString(),
      updatedAt: new Date().toISOString(),
    },
  );
  const [tagInput, setTagInput] = useState('');

  const set = (partial: Partial<PromptTemplate>) => setForm((prev) => ({ ...prev, ...partial }));

  function handleContentChange(value: string | undefined) {
    const content = value ?? '';
    const vars = [...new Set(Array.from(content.matchAll(/\{\{(\w+)\}\}/g)).map((m) => m[1]))];
    set({ content, variables: vars });
  }

  function addTag() {
    if (tagInput.trim() && !form.tags.includes(tagInput.trim())) {
      set({ tags: [...form.tags, tagInput.trim()] });
      setTagInput('');
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/30">
      <div className="bg-white rounded-2xl shadow-2xl w-[640px] max-h-[85vh] flex flex-col">
        <div className="flex items-center justify-between px-6 py-4 border-b border-gray-100">
          <h2 className="text-base font-semibold text-gray-900">{isNew ? '新建模板' : `编辑: ${template.name}`}</h2>
          <button onClick={onClose} className="p-1 rounded hover:bg-gray-100"><X size={18} className="text-gray-400" /></button>
        </div>

        <div className="flex-1 overflow-y-auto px-6 py-4 space-y-4">
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="text-xs font-medium text-gray-600 block mb-1">名称</label>
              <input className="input-base" value={form.name} onChange={(e) => set({ name: e.target.value })} />
            </div>
            <div>
              <label className="text-xs font-medium text-gray-600 block mb-1">类型</label>
              <select className="input-base" value={form.type} onChange={(e) => set({ type: e.target.value as PromptTemplate['type'] })}>
                {Object.entries(TYPE_LABELS).map(([key, val]) => (
                  <option key={key} value={key}>{val.label}</option>
                ))}
              </select>
            </div>
          </div>

          <div>
            <label className="text-xs font-medium text-gray-600 block mb-1">标签</label>
            <div className="flex items-center gap-2">
              <input
                className="input-base flex-1"
                value={tagInput}
                onChange={(e) => setTagInput(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && (e.preventDefault(), addTag())}
                placeholder="输入标签按回车"
              />
              {form.tags.map((tag) => (
                <span key={tag} className="flex items-center gap-1 text-xs bg-gray-100 text-gray-600 px-2 py-0.5 rounded">
                  {tag}
                  <button onClick={() => set({ tags: form.tags.filter((t) => t !== tag) })} className="text-gray-400 hover:text-gray-600">×</button>
                </span>
              ))}
            </div>
          </div>

          <div>
            <label className="text-xs font-medium text-gray-600 block mb-1">
              内容
              {form.variables.length > 0 && (
                <span className="ml-2 text-gray-400 font-normal">
                  变量: {form.variables.map((v) => `{{${v}}}`).join(', ')}
                </span>
              )}
            </label>
            <div className="border border-gray-200 rounded-lg overflow-hidden">
              <Editor
                height="240px"
                language="markdown"
                theme="vs-light"
                value={form.content}
                onChange={handleContentChange}
                options={{
                  minimap: { enabled: false },
                  wordWrap: 'on',
                  lineNumbers: 'off',
                  fontSize: 12,
                  scrollBeyondLastLine: false,
                  padding: { top: 8 },
                }}
              />
            </div>
          </div>
        </div>

        <div className="px-6 py-4 border-t border-gray-100 flex items-center justify-end gap-2">
          <button onClick={onClose} className="px-4 py-1.5 text-sm text-gray-600 hover:bg-gray-100 rounded-lg transition-colors">取消</button>
          <button
            onClick={() => onSave({ ...form, updatedAt: new Date().toISOString() })}
            disabled={!form.name || !form.content}
            className="px-4 py-1.5 text-sm bg-purple-600 hover:bg-purple-700 text-white rounded-lg transition-colors disabled:opacity-50"
          >
            保存
          </button>
        </div>
      </div>
    </div>
  );
}

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
