import { useState, useEffect, useCallback } from 'react';
import { Brain, Plus, Search, Trash2, Edit2, Tag, ChevronDown, ChevronRight, X, Check } from 'lucide-react';
import { toast } from 'sonner';
import { memoriesApi } from '@/api/memories';
import type { Memory, MemoryCreate } from '@/api/memories';

const TYPE_LABELS: Record<string, string> = {
  fact: '事实',
  preference: '偏好',
  context: '上下文',
  instruction: '指令',
};

const TYPE_COLORS: Record<string, string> = {
  fact: 'bg-blue-100 text-blue-700',
  preference: 'bg-purple-100 text-purple-700',
  context: 'bg-amber-100 text-amber-700',
  instruction: 'bg-green-100 text-green-700',
};

function MemoryCard({
  memory,
  onDelete,
  onEdit,
}: {
  memory: Memory;
  onDelete: (id: string) => void;
  onEdit: (m: Memory) => void;
}) {
  const [expanded, setExpanded] = useState(false);

  return (
    <div className="bg-white border border-gray-200 rounded-xl p-4 hover:shadow-sm transition-shadow">
      <div className="flex items-start justify-between gap-2">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap mb-1">
            <span
              className={`text-[11px] font-medium px-2 py-0.5 rounded-full ${
                TYPE_COLORS[memory.type] ?? 'bg-gray-100 text-gray-600'
              }`}
            >
              {TYPE_LABELS[memory.type] ?? memory.type}
            </span>
            {memory.tags && memory.tags.split(',').filter(Boolean).map(t => (
              <span key={t.trim()} className="flex items-center gap-0.5 text-[11px] px-1.5 py-0.5 bg-gray-100 text-gray-500 rounded">
                <Tag size={9} />
                {t.trim()}
              </span>
            ))}
            <span className="text-[11px] text-gray-400 ml-auto">v{memory.version}</span>
          </div>
          <h3 className="text-sm font-semibold text-gray-800 truncate">{memory.title}</h3>
        </div>
        <div className="flex items-center gap-1 shrink-0">
          <button
            onClick={() => onEdit(memory)}
            className="p-1.5 text-gray-400 hover:text-blue-500 hover:bg-blue-50 rounded-lg transition-colors"
          >
            <Edit2 size={13} />
          </button>
          <button
            onClick={() => onDelete(memory.id)}
            className="p-1.5 text-gray-400 hover:text-red-500 hover:bg-red-50 rounded-lg transition-colors"
          >
            <Trash2 size={13} />
          </button>
        </div>
      </div>

      <div className="mt-2">
        <button
          onClick={() => setExpanded(v => !v)}
          className="flex items-center gap-1 text-xs text-gray-400 hover:text-gray-600"
        >
          {expanded ? <ChevronDown size={12} /> : <ChevronRight size={12} />}
          {expanded ? '收起' : '展开内容'}
        </button>
        {expanded && (
          <p className="mt-2 text-sm text-gray-600 leading-relaxed whitespace-pre-wrap bg-gray-50 rounded-lg p-3">
            {memory.content}
          </p>
        )}
      </div>

      <div className="mt-2 text-[11px] text-gray-400">
        {new Date(memory.updated_at).toLocaleString('zh-CN')}
      </div>
    </div>
  );
}

function MemoryForm({
  initial,
  onSave,
  onCancel,
}: {
  initial?: Partial<Memory>;
  onSave: (data: MemoryCreate) => Promise<void>;
  onCancel: () => void;
}) {
  const [title, setTitle] = useState(initial?.title ?? '');
  const [content, setContent] = useState(initial?.content ?? '');
  const [type, setType] = useState(initial?.type ?? 'fact');
  const [tags, setTags] = useState(initial?.tags ?? '');
  const [saving, setSaving] = useState(false);

  const handleSubmit = async () => {
    if (!title.trim() || !content.trim()) {
      toast.error('标题和内容不能为空');
      return;
    }
    setSaving(true);
    try {
      await onSave({ title: title.trim(), content: content.trim(), type, tags });
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="bg-white border border-gray-200 rounded-xl p-5 shadow-sm">
      <div className="space-y-3">
        <input
          value={title}
          onChange={e => setTitle(e.target.value)}
          placeholder="记忆标题（简短描述）"
          className="w-full px-3 py-2 text-sm border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-purple-300"
        />
        <textarea
          value={content}
          onChange={e => setContent(e.target.value)}
          placeholder="记忆内容"
          rows={4}
          className="w-full px-3 py-2 text-sm border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-purple-300 resize-none"
        />
        <div className="flex gap-2">
          <select
            value={type}
            onChange={e => setType(e.target.value)}
            className="flex-1 px-3 py-2 text-sm border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-purple-300"
          >
            <option value="fact">事实</option>
            <option value="preference">偏好</option>
            <option value="context">上下文</option>
            <option value="instruction">指令</option>
          </select>
          <input
            value={tags}
            onChange={e => setTags(e.target.value)}
            placeholder="标签（逗号分隔）"
            className="flex-1 px-3 py-2 text-sm border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-purple-300"
          />
        </div>
        <div className="flex gap-2 justify-end">
          <button
            onClick={onCancel}
            className="px-4 py-2 text-sm text-gray-600 border border-gray-200 rounded-lg hover:bg-gray-50"
          >
            <X size={14} className="inline mr-1" />取消
          </button>
          <button
            onClick={handleSubmit}
            disabled={saving}
            className="px-4 py-2 text-sm bg-purple-600 text-white rounded-lg hover:bg-purple-700 disabled:opacity-50 flex items-center gap-1"
          >
            <Check size={14} />
            {saving ? '保存中…' : '保存'}
          </button>
        </div>
      </div>
    </div>
  );
}

export default function MemoryPage() {
  const [memories, setMemories] = useState<Memory[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(false);
  const [search, setSearch] = useState('');
  const [filterType, setFilterType] = useState('');
  const [showForm, setShowForm] = useState(false);
  const [editTarget, setEditTarget] = useState<Memory | null>(null);
  const [offset, setOffset] = useState(0);
  const LIMIT = 20;

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const res = await memoriesApi.list({
        type: filterType || undefined,
        tags: search || undefined,
        limit: LIMIT,
        offset,
      });
      setMemories(res.items);
      setTotal(res.total);
    } catch {
      toast.error('加载记忆失败');
    } finally {
      setLoading(false);
    }
  }, [filterType, search, offset]);

  useEffect(() => { load(); }, [load]);

  const handleCreate = async (data: MemoryCreate) => {
    await memoriesApi.create(data);
    toast.success('记忆已创建');
    setShowForm(false);
    load();
  };

  const handleEdit = async (data: MemoryCreate) => {
    if (!editTarget) return;
    await memoriesApi.update(editTarget.id, data);
    toast.success('记忆已更新（新版本）');
    setEditTarget(null);
    load();
  };

  const handleDelete = async (id: string) => {
    if (!confirm('确认删除此记忆？')) return;
    await memoriesApi.delete(id);
    toast.success('已删除');
    load();
  };

  return (
    <div className="h-full flex flex-col bg-gray-50">
      {/* Header */}
      <div className="bg-white border-b border-gray-200 px-6 py-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Brain size={20} className="text-purple-500" />
            <h1 className="text-lg font-semibold text-gray-800">记忆管理</h1>
            <span className="text-sm text-gray-400 ml-1">共 {total} 条</span>
          </div>
          <button
            onClick={() => { setShowForm(true); setEditTarget(null); }}
            className="flex items-center gap-1.5 px-3 py-2 bg-purple-600 text-white text-sm rounded-lg hover:bg-purple-700"
          >
            <Plus size={15} />新建记忆
          </button>
        </div>
        {/* Filter bar */}
        <div className="flex gap-2 mt-3">
          <div className="relative flex-1 max-w-xs">
            <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
            <input
              value={search}
              onChange={e => { setSearch(e.target.value); setOffset(0); }}
              placeholder="搜索标签…"
              className="w-full pl-8 pr-3 py-1.5 text-sm border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-purple-200"
            />
          </div>
          <select
            value={filterType}
            onChange={e => { setFilterType(e.target.value); setOffset(0); }}
            className="px-3 py-1.5 text-sm border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-purple-200"
          >
            <option value="">全部类型</option>
            <option value="fact">事实</option>
            <option value="preference">偏好</option>
            <option value="context">上下文</option>
            <option value="instruction">指令</option>
          </select>
        </div>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto p-6">
        {(showForm && !editTarget) && (
          <div className="mb-4">
            <MemoryForm onSave={handleCreate} onCancel={() => setShowForm(false)} />
          </div>
        )}
        {editTarget && (
          <div className="mb-4">
            <MemoryForm initial={editTarget} onSave={handleEdit} onCancel={() => setEditTarget(null)} />
          </div>
        )}

        {loading ? (
          <div className="text-center text-gray-400 py-12">加载中…</div>
        ) : memories.length === 0 ? (
          <div className="text-center py-20 text-gray-400">
            <Brain size={40} className="mx-auto mb-3 opacity-30" />
            <p className="text-sm">暂无记忆，点击「新建记忆」添加</p>
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
            {memories.map(m => (
              <MemoryCard
                key={m.id}
                memory={m}
                onDelete={handleDelete}
                onEdit={mem => { setEditTarget(mem); setShowForm(false); }}
              />
            ))}
          </div>
        )}

        {/* Pagination */}
        {total > LIMIT && (
          <div className="flex justify-center gap-2 mt-6">
            <button
              disabled={offset === 0}
              onClick={() => setOffset(o => Math.max(0, o - LIMIT))}
              className="px-3 py-1.5 text-sm border border-gray-200 rounded-lg disabled:opacity-40 hover:bg-gray-50"
            >上一页</button>
            <span className="px-3 py-1.5 text-sm text-gray-500">
              {Math.floor(offset / LIMIT) + 1} / {Math.ceil(total / LIMIT)}
            </span>
            <button
              disabled={offset + LIMIT >= total}
              onClick={() => setOffset(o => o + LIMIT)}
              className="px-3 py-1.5 text-sm border border-gray-200 rounded-lg disabled:opacity-40 hover:bg-gray-50"
            >下一页</button>
          </div>
        )}
      </div>
    </div>
  );
}
