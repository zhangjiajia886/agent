import { useEffect, useState } from 'react';
import { BookOpen, Plus, Pencil, Trash2, X, FileText, Type, Globe, Search } from 'lucide-react';
import Editor from '@monaco-editor/react';
import { toast } from 'sonner';
import PageHeader from '@/components/layout/PageHeader';
import type { KnowledgeItem } from '@/types/entities';
import { knowledgeApi, type KnowledgeDTO } from '@/api/knowledge';

const TYPE_META: Record<string, { label: string; icon: typeof FileText; color: string }> = {
  file: { label: '文件', icon: FileText, color: 'bg-blue-50 text-blue-700' },
  text: { label: '文本', icon: Type, color: 'bg-green-50 text-green-700' },
  url: { label: 'URL', icon: Globe, color: 'bg-amber-50 text-amber-700' },
};

function mapKnowledge(dto: KnowledgeDTO): KnowledgeItem {
  const content = JSON.stringify(dto.config ?? {}, null, 2);
  return {
    id: dto.id,
    name: dto.name,
    type: (dto.type as 'file' | 'text' | 'url') || 'text',
    content,
    sizeBytes: new Blob([content]).size,
    scope: 'global',
    createdAt: dto.created_at,
    updatedAt: dto.updated_at,
  };
}

export default function KnowledgePage() {
  const [items, setItems] = useState<KnowledgeItem[]>([]);
  const [selectedItem, setSelectedItem] = useState<KnowledgeItem | null>(null);
  const [searchQuery, setSearchQuery] = useState('');
  const [showDialog, setShowDialog] = useState(false);
  const [editingItem, setEditingItem] = useState<KnowledgeItem | null>(null);

  async function loadKnowledge(search = '') {
    try {
      const res = await knowledgeApi.list(search || undefined);
      const next = res.items.map(mapKnowledge);
      setItems(next);
      setSelectedItem((prev) => next.find((item) => item.id === prev?.id) ?? next[0] ?? null);
    } catch {
      toast.error('加载知识库失败');
    }
  }

  useEffect(() => {
    loadKnowledge(searchQuery);
  }, [searchQuery]);

  async function handleSave(item: KnowledgeItem) {
    try {
      let parsedConfig: Record<string, unknown>;
      try {
        parsedConfig = JSON.parse(item.content || '{}');
      } catch {
        parsedConfig = { content_template: item.content };
      }

      const exists = items.some((i) => i.id === item.id);
      if (exists) {
        await knowledgeApi.update(item.id, {
          name: item.name,
          config: parsedConfig,
          status: 'active',
        });
      } else {
        await knowledgeApi.create({
          name: item.name,
          type: item.type,
          config: parsedConfig,
        });
      }
      await loadKnowledge(searchQuery);
      setShowDialog(false);
      setEditingItem(null);
      toast.success('知识库已保存');
    } catch {
      toast.error('保存知识库失败');
    }
  }

  async function handleDelete(id: string) {
    try {
      await knowledgeApi.delete(id);
      await loadKnowledge(searchQuery);
      if (selectedItem?.id === id) setSelectedItem(null);
    } catch {
      toast.error('删除知识库失败');
    }
  }

  function handleDuplicate(item: KnowledgeItem) {
    setEditingItem({
      ...item,
      id: `kb_${Date.now()}`,
      name: `${item.name}-副本`,
      updatedAt: new Date().toISOString(),
    });
    setShowDialog(true);
  }

  return (
    <div className="flex flex-col h-full">
      <PageHeader
        title="知识库"
        description="默认展示系统知识模板；你也可以新增自己的知识库配置"
        icon={<BookOpen size={24} />}
        actions={
          <button
            onClick={() => { setEditingItem(null); setShowDialog(true); }}
            className="flex items-center gap-1.5 px-4 py-2 text-sm bg-purple-600 hover:bg-purple-700 rounded-lg text-white transition-colors"
          >
            <Plus size={16} />
            添加知识库
          </button>
        }
      />

      <div className="flex flex-1 overflow-hidden">
        <div className="w-80 border-r border-gray-200 flex flex-col bg-white shrink-0">
          <div className="p-3 border-b border-gray-100">
            <div className="relative">
              <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
              <input
                type="text"
                placeholder="搜索知识库..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="w-full pl-8 pr-3 py-1.5 text-sm border border-gray-200 rounded-lg outline-none focus:border-purple-400"
              />
            </div>
          </div>
          <div className="flex-1 overflow-y-auto">
            {items.map((item) => {
              const typeMeta = TYPE_META[item.type] ?? TYPE_META.text;
              const Icon = typeMeta.icon;
              const isSelected = selectedItem?.id === item.id;
              return (
                <div
                  key={item.id}
                  onClick={() => setSelectedItem(item)}
                  className={`px-4 py-3 border-b border-gray-50 cursor-pointer transition-colors ${isSelected ? 'bg-purple-50 border-l-2 border-l-purple-500' : 'hover:bg-gray-50'}`}
                >
                  <div className="flex items-center gap-2 mb-1">
                    <Icon size={14} className="text-gray-400 shrink-0" />
                    <span className="text-sm font-medium text-gray-900 truncate">{item.name}</span>
                    <span className={`text-[10px] px-1.5 py-0.5 rounded ${typeMeta.color}`}>{typeMeta.label}</span>
                  </div>
                  <div className="flex items-center gap-3 text-[10px] text-gray-400 ml-[22px]">
                    <span>{(item.sizeBytes / 1024).toFixed(1)} KB</span>
                    <span>{item.id.includes('template') ? '系统模板' : '用户配置'}</span>
                  </div>
                </div>
              );
            })}
          </div>
        </div>

        <div className="flex-1 flex flex-col overflow-hidden bg-gray-50">
          {selectedItem ? (
            <>
              <div className="px-6 py-4 bg-white border-b border-gray-200 flex items-center justify-between">
                <div>
                  <h2 className="text-base font-semibold text-gray-900">{selectedItem.name}</h2>
                  <div className="flex items-center gap-3 text-xs text-gray-400 mt-0.5">
                    <span>{(TYPE_META[selectedItem.type] ?? TYPE_META.text).label}</span>
                    <span>{(selectedItem.sizeBytes / 1024).toFixed(1)} KB</span>
                    <span>{selectedItem.id.includes('template') ? '系统预设，可复制修改' : '用户自建'}</span>
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  <button
                    onClick={() => handleDuplicate(selectedItem)}
                    className="px-3 py-1.5 text-sm bg-blue-50 hover:bg-blue-100 text-blue-600 rounded-lg transition-colors"
                  >
                    复制
                  </button>
                  <button onClick={() => handleDelete(selectedItem.id)} className="p-2 rounded-lg hover:bg-red-50 text-gray-400 hover:text-red-500 transition-colors">
                    <Trash2 size={16} />
                  </button>
                  <button
                    onClick={() => { setEditingItem(selectedItem); setShowDialog(true); }}
                    className="flex items-center gap-1.5 px-3 py-1.5 text-sm bg-purple-600 hover:bg-purple-700 rounded-lg text-white transition-colors"
                  >
                    <Pencil size={14} /> 编辑
                  </button>
                </div>
              </div>
              <div className="flex-1 overflow-hidden">
                <Editor
                  height="100%"
                  language="json"
                  theme="vs-light"
                  value={selectedItem.content}
                  options={{ readOnly: true, minimap: { enabled: false }, wordWrap: 'on', fontSize: 13, scrollBeyondLastLine: false, padding: { top: 16 } }}
                />
              </div>
            </>
          ) : (
            <div className="flex-1 flex items-center justify-center text-gray-400 text-sm">
              <div className="text-center">
                <BookOpen size={40} className="mx-auto mb-3 opacity-30" />
                <p>选择一个知识库模板或配置查看详情</p>
              </div>
            </div>
          )}
        </div>
      </div>

      {showDialog && (
        <KnowledgeEditDialog
          item={editingItem}
          onSave={handleSave}
          onClose={() => { setShowDialog(false); setEditingItem(null); }}
        />
      )}
    </div>
  );
}

function KnowledgeEditDialog({
  item,
  onSave,
  onClose,
}: {
  item: KnowledgeItem | null;
  onSave: (k: KnowledgeItem) => void;
  onClose: () => void;
}) {
  const isNew = !item;
  const [form, setForm] = useState<KnowledgeItem>(
    item ?? {
      id: `kb_${Date.now()}`,
      name: '',
      type: 'text',
      content: '{\n  "content_template": "# 新知识库"\n}',
      sizeBytes: 0,
      scope: 'global',
      createdAt: new Date().toISOString(),
      updatedAt: new Date().toISOString(),
    },
  );

  const set = (partial: Partial<KnowledgeItem>) => setForm((prev) => ({ ...prev, ...partial }));

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/30">
      <div className="bg-white rounded-2xl shadow-2xl w-[640px] max-h-[85vh] flex flex-col">
        <div className="flex items-center justify-between px-6 py-4 border-b border-gray-100">
          <h2 className="text-base font-semibold text-gray-900">{isNew ? '添加知识库' : `编辑: ${item?.name}`}</h2>
          <button onClick={onClose} className="p-1 rounded hover:bg-gray-100"><X size={18} className="text-gray-400" /></button>
        </div>

        <div className="flex-1 overflow-y-auto px-6 py-4 space-y-4">
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="text-xs font-medium text-gray-600 block mb-1">名称</label>
              <input className="input-base" value={form.name} onChange={(e) => set({ name: e.target.value })} placeholder="本地文档知识库" />
            </div>
            <div>
              <label className="text-xs font-medium text-gray-600 block mb-1">类型</label>
              <select className="input-base" value={form.type} onChange={(e) => set({ type: e.target.value as KnowledgeItem['type'] })}>
                <option value="text">文本</option>
                <option value="file">文件</option>
                <option value="url">URL</option>
              </select>
            </div>
          </div>

          <div>
            <label className="text-xs font-medium text-gray-600 block mb-1">配置 JSON</label>
            <div className="border border-gray-200 rounded-lg overflow-hidden">
              <Editor
                height="300px"
                language="json"
                theme="vs-light"
                value={form.content}
                onChange={(v) => set({ content: v ?? '', sizeBytes: new Blob([v ?? '']).size })}
                options={{ minimap: { enabled: false }, wordWrap: 'on', fontSize: 12, scrollBeyondLastLine: false, padding: { top: 8 } }}
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
