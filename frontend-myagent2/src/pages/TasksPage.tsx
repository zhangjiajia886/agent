import { useState, useEffect, useCallback } from 'react';
import { ListTodo, Plus, ChevronRight, ChevronDown, Circle, CheckCircle2, XCircle, Clock, AlertCircle, Trash2 } from 'lucide-react';
import { toast } from 'sonner';
import { tasksApi } from '@/api/tasks';
import type { Task, TaskCreate, TaskStatus, TaskPriority } from '@/api/tasks';

const STATUS_CONFIG: Record<TaskStatus, { label: string; icon: React.ReactNode; color: string }> = {
  pending:     { label: '待处理', icon: <Circle size={14} />,        color: 'text-gray-400' },
  in_progress: { label: '进行中', icon: <Clock size={14} />,         color: 'text-blue-500' },
  completed:   { label: '已完成', icon: <CheckCircle2 size={14} />,  color: 'text-green-500' },
  cancelled:   { label: '已取消', icon: <XCircle size={14} />,       color: 'text-gray-400' },
  failed:      { label: '失败',   icon: <AlertCircle size={14} />,   color: 'text-red-500' },
};

const PRIORITY_COLORS: Record<TaskPriority, string> = {
  low:    'bg-gray-100 text-gray-500',
  medium: 'bg-blue-100 text-blue-600',
  high:   'bg-orange-100 text-orange-600',
  urgent: 'bg-red-100 text-red-600',
};

const PRIORITY_LABELS: Record<TaskPriority, string> = {
  low: '低', medium: '中', high: '高', urgent: '紧急',
};

function TaskRow({
  task,
  depth = 0,
  onStatusChange,
  onDelete,
}: {
  task: Task;
  depth?: number;
  onStatusChange: (id: string, status: TaskStatus) => void;
  onDelete: (id: string) => void;
}) {
  const [expanded, setExpanded] = useState(depth < 1);
  const hasChildren = (task.children?.length ?? 0) > 0;
  const cfg = STATUS_CONFIG[task.status] ?? STATUS_CONFIG.pending;

  return (
    <>
      <tr className={`border-b border-gray-100 hover:bg-gray-50 transition-colors ${task.status === 'completed' ? 'opacity-60' : ''}`}>
        <td className="px-4 py-3">
          <div className="flex items-center gap-2" style={{ paddingLeft: `${depth * 20}px` }}>
            {hasChildren ? (
              <button onClick={() => setExpanded(v => !v)} className="text-gray-400 hover:text-gray-600 shrink-0">
                {expanded ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
              </button>
            ) : (
              <span className="w-[14px] shrink-0" />
            )}
            <span className={`text-sm ${task.status === 'completed' ? 'line-through text-gray-400' : 'text-gray-800'}`}>
              {task.title}
            </span>
          </div>
        </td>
        <td className="px-3 py-3">
          <div className={`flex items-center gap-1 text-sm ${cfg.color}`}>
            {cfg.icon}
            <span className="text-xs">{cfg.label}</span>
          </div>
        </td>
        <td className="px-3 py-3">
          <span className={`text-[11px] font-medium px-2 py-0.5 rounded-full ${PRIORITY_COLORS[task.priority]}`}>
            {PRIORITY_LABELS[task.priority]}
          </span>
        </td>
        <td className="px-3 py-3 text-xs text-gray-400">
          {task.due_at ? new Date(task.due_at).toLocaleDateString('zh-CN') : '—'}
        </td>
        <td className="px-3 py-3">
          <div className="flex items-center gap-1">
            {task.status !== 'completed' && (
              <button
                onClick={() => onStatusChange(task.id, 'completed')}
                className="p-1 text-gray-400 hover:text-green-500 hover:bg-green-50 rounded transition-colors"
                title="标记完成"
              >
                <CheckCircle2 size={13} />
              </button>
            )}
            {task.status === 'pending' && (
              <button
                onClick={() => onStatusChange(task.id, 'in_progress')}
                className="p-1 text-gray-400 hover:text-blue-500 hover:bg-blue-50 rounded transition-colors"
                title="开始执行"
              >
                <Clock size={13} />
              </button>
            )}
            <button
              onClick={() => onDelete(task.id)}
              className="p-1 text-gray-400 hover:text-red-500 hover:bg-red-50 rounded transition-colors"
            >
              <Trash2 size={13} />
            </button>
          </div>
        </td>
      </tr>
      {expanded && hasChildren && task.children!.map(child => (
        <TaskRow key={child.id} task={child} depth={depth + 1} onStatusChange={onStatusChange} onDelete={onDelete} />
      ))}
    </>
  );
}

function CreateTaskForm({ onSave, onCancel }: { onSave: (d: TaskCreate) => Promise<void>; onCancel: () => void }) {
  const [title, setTitle] = useState('');
  const [priority, setPriority] = useState<TaskPriority>('medium');
  const [saving, setSaving] = useState(false);

  return (
    <div className="flex items-center gap-2 p-3 bg-purple-50 border border-purple-200 rounded-xl">
      <input
        autoFocus
        value={title}
        onChange={e => setTitle(e.target.value)}
        onKeyDown={e => e.key === 'Enter' && title.trim() && (() => { setSaving(true); onSave({ title, priority }).finally(() => setSaving(false)); })()}
        placeholder="任务标题…"
        className="flex-1 px-3 py-1.5 text-sm border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-purple-300"
      />
      <select
        value={priority}
        onChange={e => setPriority(e.target.value as TaskPriority)}
        className="px-2 py-1.5 text-sm border border-gray-200 rounded-lg focus:outline-none"
      >
        <option value="low">低</option>
        <option value="medium">中</option>
        <option value="high">高</option>
        <option value="urgent">紧急</option>
      </select>
      <button
        disabled={!title.trim() || saving}
        onClick={async () => { setSaving(true); try { await onSave({ title, priority }); } finally { setSaving(false); } }}
        className="px-3 py-1.5 text-sm bg-purple-600 text-white rounded-lg disabled:opacity-40 hover:bg-purple-700"
      >
        {saving ? '…' : '添加'}
      </button>
      <button onClick={onCancel} className="px-2 py-1.5 text-sm text-gray-400 hover:text-gray-600">✕</button>
    </div>
  );
}

export default function TasksPage() {
  const [tasks, setTasks] = useState<Task[]>([]);
  const [loading, setLoading] = useState(false);
  const [filterStatus, setFilterStatus] = useState<TaskStatus | ''>('');
  const [showCreate, setShowCreate] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const res = await tasksApi.list({ root_only: true, status: filterStatus || undefined, limit: 100 });
      setTasks(res.items);
    } catch {
      toast.error('加载任务失败');
    } finally {
      setLoading(false);
    }
  }, [filterStatus]);

  useEffect(() => { load(); }, [load]);

  const handleCreate = async (data: TaskCreate) => {
    await tasksApi.create(data);
    toast.success('任务已创建');
    setShowCreate(false);
    load();
  };

  const handleStatusChange = async (id: string, status: TaskStatus) => {
    await tasksApi.update(id, { status });
    load();
  };

  const handleDelete = async (id: string) => {
    if (!confirm('确认删除此任务？')) return;
    await tasksApi.delete(id);
    toast.success('已删除');
    load();
  };

  const counts = Object.fromEntries(
    (Object.keys(STATUS_CONFIG) as TaskStatus[]).map(s => [s, tasks.filter(t => t.status === s).length])
  ) as Record<TaskStatus, number>;

  return (
    <div className="h-full flex flex-col bg-gray-50">
      {/* Header */}
      <div className="bg-white border-b border-gray-200 px-6 py-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <ListTodo size={20} className="text-purple-500" />
            <h1 className="text-lg font-semibold text-gray-800">任务管理</h1>
          </div>
          <button
            onClick={() => setShowCreate(v => !v)}
            className="flex items-center gap-1.5 px-3 py-2 bg-purple-600 text-white text-sm rounded-lg hover:bg-purple-700"
          >
            <Plus size={15} />新建任务
          </button>
        </div>
        {/* Status pills */}
        <div className="flex gap-2 mt-3 flex-wrap">
          <button
            onClick={() => setFilterStatus('')}
            className={`px-3 py-1 text-xs rounded-full border transition-colors ${filterStatus === '' ? 'bg-purple-600 text-white border-purple-600' : 'border-gray-200 text-gray-500 hover:bg-gray-50'}`}
          >
            全部 ({tasks.length})
          </button>
          {(Object.keys(STATUS_CONFIG) as TaskStatus[]).map(s => (
            <button
              key={s}
              onClick={() => setFilterStatus(s)}
              className={`px-3 py-1 text-xs rounded-full border transition-colors ${filterStatus === s ? 'bg-purple-600 text-white border-purple-600' : 'border-gray-200 text-gray-500 hover:bg-gray-50'}`}
            >
              {STATUS_CONFIG[s].label} ({counts[s] ?? 0})
            </button>
          ))}
        </div>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto p-6">
        {showCreate && (
          <div className="mb-4">
            <CreateTaskForm onSave={handleCreate} onCancel={() => setShowCreate(false)} />
          </div>
        )}

        {loading ? (
          <div className="text-center text-gray-400 py-12">加载中…</div>
        ) : tasks.length === 0 ? (
          <div className="text-center py-20 text-gray-400">
            <ListTodo size={40} className="mx-auto mb-3 opacity-30" />
            <p className="text-sm">暂无任务，点击「新建任务」添加</p>
          </div>
        ) : (
          <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
            <table className="w-full">
              <thead>
                <tr className="border-b border-gray-100 bg-gray-50">
                  <th className="px-4 py-2.5 text-left text-xs font-medium text-gray-500">任务</th>
                  <th className="px-3 py-2.5 text-left text-xs font-medium text-gray-500">状态</th>
                  <th className="px-3 py-2.5 text-left text-xs font-medium text-gray-500">优先级</th>
                  <th className="px-3 py-2.5 text-left text-xs font-medium text-gray-500">截止日期</th>
                  <th className="px-3 py-2.5 text-left text-xs font-medium text-gray-500">操作</th>
                </tr>
              </thead>
              <tbody>
                {tasks.map(t => (
                  <TaskRow
                    key={t.id}
                    task={t}
                    onStatusChange={handleStatusChange}
                    onDelete={handleDelete}
                  />
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
