import { useNavigate } from 'react-router-dom';
import { Workflow, Plus, Upload, MoreHorizontal, Play, Pencil, Copy, Trash2, Download, FileInput } from 'lucide-react';
import { useState, useRef, useEffect, useCallback } from 'react';
import { toast } from 'sonner';
import PageHeader from '@/components/layout/PageHeader';
import RunWorkflowDialog from '@/components/workflow/RunWorkflowDialog';
import DifyImportDialog from '@/components/workflow/DifyImportDialog';
import type { WorkflowListItem } from '@/types/entities';
import { workflowApi } from '@/api/workflows';
import type { WorkflowDTO } from '@/api/workflows';

function dtoToItem(d: WorkflowDTO): WorkflowListItem {
  const def = d.definition as Record<string, unknown> | undefined;
  const nodes = (def?.nodes as unknown[] | undefined) ?? [];
  const edges = (def?.edges as unknown[] | undefined) ?? [];
  return {
    id: d.id,
    name: d.name,
    description: d.description,
    status: (d.status as WorkflowListItem['status']) || 'draft',
    version: `v${d.version}`,
    nodeCount: nodes.length,
    edgeCount: edges.length,
    createdAt: d.created_at,
    updatedAt: d.updated_at,
    tags: d.tags ?? [],
  };
}

function relativeTime(iso?: string): string {
  if (!iso) return '-';
  const diff = Date.now() - new Date(iso).getTime();
  const minutes = Math.floor(diff / 60000);
  if (minutes < 1) return '刚刚';
  if (minutes < 60) return `${minutes}分钟前`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}小时前`;
  return `${Math.floor(hours / 24)}天前`;
}

const STATUS_BADGE: Record<string, { className: string; label: string }> = {
  active: { className: 'bg-green-50 text-green-700 border-green-200', label: '活跃' },
  draft: { className: 'bg-gray-50 text-gray-600 border-gray-200', label: '草稿' },
  archived: { className: 'bg-yellow-50 text-yellow-700 border-yellow-200', label: '归档' },
};

const RUN_STATUS_ICON: Record<string, { color: string; label: string }> = {
  success: { color: 'text-green-500', label: '成功' },
  failed: { color: 'text-red-500', label: '失败' },
  running: { color: 'text-blue-500', label: '运行中' },
};

export default function WorkflowListPage() {
  const navigate = useNavigate();
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [filter, setFilter] = useState<'all' | 'active' | 'draft' | 'archived'>('all');
  const [searchQuery, setSearchQuery] = useState('');
  const [allWorkflows, setAllWorkflows] = useState<WorkflowListItem[]>([]);
  const [rawWorkflows, setRawWorkflows] = useState<WorkflowDTO[]>([]);
  const [runTarget, setRunTarget] = useState<WorkflowDTO | null>(null);
  const [difyImportOpen, setDifyImportOpen] = useState(false);

  const fetchList = useCallback(async () => {
    try {
      const res = await workflowApi.list({ search: searchQuery || undefined, status: filter === 'all' ? undefined : filter });
      setRawWorkflows(res.items);
      setAllWorkflows(res.items.map(dtoToItem));
    } catch {
      toast.error('加载工作流失败');
    }
  }, [searchQuery, filter]);

  useEffect(() => { fetchList(); }, [fetchList]);

  const workflows = allWorkflows;

  async function handleImportFile(event: React.ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    if (!file) return;
    try {
      const text = await file.text();
      const data = JSON.parse(text) as Partial<WorkflowDTO>;
      const definition = (data.definition ?? {}) as Record<string, unknown>;
      await workflowApi.create({
        name: data.name || file.name.replace(/\.json$/i, ''),
        description: data.description || '从 JSON 导入的工作流',
        definition,
        tags: data.tags ?? ['imported'],
      });
      toast.success('工作流导入成功');
      await fetchList();
    } catch {
      toast.error('导入工作流失败，请检查 JSON 格式');
    } finally {
      event.target.value = '';
    }
  }

  async function handleClone(id: string) {
    try {
      const res = await workflowApi.clone(id);
      toast.success('工作流已复制');
      await fetchList();
      navigate(`/workflows/${res.id}/edit`);
    } catch {
      toast.error('复制工作流失败');
    }
  }

  async function handleDelete(id: string) {
    try {
      await workflowApi.delete(id);
      toast.success('工作流已删除');
      await fetchList();
    } catch {
      toast.error('删除工作流失败');
    }
  }

  function handleRun(id: string) {
    const wf = rawWorkflows.find((item) => item.id === id) ?? null;
    if (!wf) {
      toast.error('未找到工作流定义');
      return;
    }
    setRunTarget(wf);
  }

  async function handleRunSubmit(inputs: Record<string, unknown>) {
    if (!runTarget) return;
    try {
      const res = await workflowApi.execute(runTarget.id, inputs);
      toast.success(`已启动执行: ${res.execution_id}`);
      setRunTarget(null);
      navigate(`/executions?selected=${res.execution_id}`);
    } catch {
      toast.error('运行工作流失败');
    }
  }

  function handleExport(id: string) {
    const wf = rawWorkflows.find((item) => item.id === id);
    if (!wf) {
      toast.error('未找到要导出的工作流');
      return;
    }
    const blob = new Blob([JSON.stringify(wf, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = `${wf.name}.json`;
    link.click();
    URL.revokeObjectURL(url);
  }

  return (
    <div className="flex flex-col h-full">
      <PageHeader
        title="工作流管理"
        description={`共 ${allWorkflows.length} 个工作流`}
        icon={<Workflow size={24} />}
        actions={
          <div className="flex items-center gap-2">
            <input
              type="file"
              ref={fileInputRef}
              onChange={handleImportFile}
              className="hidden"
              accept=".json"
            />
            <button
              onClick={() => setDifyImportOpen(true)}
              className="flex items-center gap-1.5 px-3 py-2 text-sm bg-orange-50 hover:bg-orange-100 rounded-lg text-orange-700 border border-orange-200 transition-colors"
            >
              <FileInput size={16} />
              从 Dify 导入
            </button>
            <button
              onClick={() => fileInputRef.current?.click()}
              className="flex items-center gap-1.5 px-3 py-2 text-sm bg-gray-100 hover:bg-gray-200 rounded-lg text-gray-700 transition-colors"
            >
              <Upload size={16} />
              导入 JSON
            </button>
            <button
              onClick={() => navigate('/workflows/new/edit')}
              className="flex items-center gap-1.5 px-4 py-2 text-sm bg-purple-600 hover:bg-purple-700 rounded-lg text-white transition-colors"
            >
              <Plus size={16} />
              新建工作流
            </button>
          </div>
        }
      />

      {/* 筛选栏 */}
      <div className="flex items-center gap-3 px-6 py-3 border-b border-gray-100 bg-white">
        <input
          type="text"
          placeholder="搜索工作流..."
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          className="px-3 py-1.5 text-sm border border-gray-200 rounded-lg outline-none focus:border-purple-400 focus:ring-1 focus:ring-purple-200 w-64"
        />
        <div className="flex items-center gap-1 bg-gray-100 rounded-lg p-0.5">
          {(['all', 'active', 'draft', 'archived'] as const).map((f) => (
            <button
              key={f}
              onClick={() => setFilter(f)}
              className={`px-3 py-1 text-xs rounded-md transition-colors ${
                filter === f ? 'bg-white text-gray-900 shadow-sm' : 'text-gray-500 hover:text-gray-700'
              }`}
            >
              {f === 'all' ? '全部' : f === 'active' ? '活跃' : f === 'draft' ? '草稿' : '归档'}
            </button>
          ))}
        </div>
      </div>

      {/* 卡片网格 */}
      <div className="flex-1 overflow-y-auto p-6">
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
          {workflows.map((wf) => (
            <WorkflowCard
              key={wf.id}
              workflow={wf}
              onEdit={() => navigate(`/workflows/${wf.id}/edit`)}
              onClone={() => handleClone(wf.id)}
              onDelete={() => handleDelete(wf.id)}
              onExport={() => handleExport(wf.id)}
              onRun={() => handleRun(wf.id)}
            />
          ))}
          {workflows.length === 0 && (
            <div className="col-span-full text-center py-20 text-gray-400">
              <Workflow size={40} className="mx-auto mb-3 opacity-30" />
              <p className="text-sm">没有匹配的工作流</p>
            </div>
          )}
        </div>
      </div>
      <DifyImportDialog
        open={difyImportOpen}
        onClose={() => setDifyImportOpen(false)}
        onDone={(count) => {
          toast.success(`成功导入 ${count} 个 Dify 工作流`);
          fetchList();
        }}
      />
      <RunWorkflowDialog
        open={!!runTarget}
        title={runTarget?.name ?? ''}
        inputFields={(((runTarget?.definition as { nodes?: Array<{ type?: string; data?: { outputs?: string[] } }> | undefined })?.nodes ?? []).find((node) => node.type === 'start')?.data?.outputs ?? [])}
        onClose={() => setRunTarget(null)}
        onSubmit={handleRunSubmit}
      />
    </div>
  );
}

function WorkflowCard({
  workflow: wf,
  onEdit,
  onClone,
  onDelete,
  onExport,
  onRun,
}: {
  workflow: WorkflowListItem;
  onEdit: () => void;
  onClone: () => void;
  onDelete: () => void;
  onExport: () => void;
  onRun: () => void;
}) {
  const [menuOpen, setMenuOpen] = useState(false);
  const menuRef = useRef<HTMLDivElement>(null);

  const badge = STATUS_BADGE[wf.status];
  const runStatus = wf.lastRunStatus ? RUN_STATUS_ICON[wf.lastRunStatus] : null;

  return (
    <div className="bg-white rounded-xl border border-gray-200 hover:border-purple-200 hover:shadow-md transition-all group">
      {/* 头部 */}
      <div className="px-4 pt-4 pb-2">
        <div className="flex items-start justify-between">
          <div className="flex-1 min-w-0">
            <h3 className="font-semibold text-gray-900 truncate">{wf.name}</h3>
            <p className="text-xs text-gray-500 mt-0.5 line-clamp-2">{wf.description}</p>
          </div>
          <div className="relative ml-2" ref={menuRef}>
            <button
              onClick={() => setMenuOpen(!menuOpen)}
              className="p-1 rounded hover:bg-gray-100 opacity-0 group-hover:opacity-100 transition-opacity"
            >
              <MoreHorizontal size={16} className="text-gray-400" />
            </button>
            {menuOpen && (
              <div className="absolute right-0 mt-1 w-36 bg-white border border-gray-200 rounded-lg shadow-lg z-10 py-1">
                <MenuItem icon={<Copy size={14} />} label="复制" onClick={() => { setMenuOpen(false); onClone(); }} />
                <MenuItem icon={<Download size={14} />} label="导出 JSON" onClick={() => { setMenuOpen(false); onExport(); }} />
                <div className="border-t border-gray-100 my-1" />
                <MenuItem icon={<Trash2 size={14} />} label="删除" onClick={() => { setMenuOpen(false); onDelete(); }} danger />
              </div>
            )}
          </div>
        </div>

        {/* 标签 */}
        <div className="flex items-center gap-1.5 mt-2">
          <span className={`text-[10px] px-1.5 py-0.5 rounded border ${badge.className}`}>
            {badge.label}
          </span>
          <span className="text-[10px] text-gray-400">{wf.version}</span>
          {wf.tags.map((tag) => (
            <span key={tag} className="text-[10px] px-1.5 py-0.5 rounded bg-gray-50 text-gray-500 border border-gray-100">
              {tag}
            </span>
          ))}
        </div>
      </div>

      {/* 统计 */}
      <div className="px-4 py-2 flex items-center gap-4 text-[11px] text-gray-400">
        <span>{wf.nodeCount} 节点</span>
        <span>{wf.edgeCount} 连线</span>
        {wf.successRate !== undefined && <span>成功率 {wf.successRate}%</span>}
      </div>

      {/* 底部 */}
      <div className="px-4 py-3 border-t border-gray-100 flex items-center justify-between">
        <div className="flex items-center gap-1.5 text-[11px] text-gray-400">
          {runStatus && <span className={runStatus.color}>●</span>}
          <span>{wf.lastRunAt ? relativeTime(wf.lastRunAt) : '未运行'}</span>
        </div>
        <div className="flex items-center gap-1">
          <button
            onClick={onEdit}
            className="flex items-center gap-1 px-2.5 py-1 text-xs rounded-md bg-gray-50 hover:bg-gray-100 text-gray-600 transition-colors"
          >
            <Pencil size={12} />
            编辑
          </button>
          <button onClick={onRun} className="flex items-center gap-1 px-2.5 py-1 text-xs rounded-md bg-purple-50 hover:bg-purple-100 text-purple-600 transition-colors">
            <Play size={12} />
            运行
          </button>
        </div>
      </div>
    </div>
  );
}

function MenuItem({
  icon,
  label,
  onClick,
  danger,
}: {
  icon: React.ReactNode;
  label: string;
  onClick: () => void;
  danger?: boolean;
}) {
  return (
    <button
      onClick={onClick}
      className={`flex items-center gap-2 w-full px-3 py-1.5 text-xs text-left transition-colors ${
        danger ? 'text-red-500 hover:bg-red-50' : 'text-gray-600 hover:bg-gray-50'
      }`}
    >
      {icon}
      {label}
    </button>
  );
}
