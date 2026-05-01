import { useState, useEffect, useCallback } from 'react';
import { Clock, Plus, Trash2, ToggleLeft, ToggleRight, X, Check } from 'lucide-react';
import { toast } from 'sonner';
import { schedulesApi } from '@/api/schedules';
import type { Schedule, ScheduleCreate } from '@/api/schedules';

const CRON_PRESETS = [
  { label: '每小时', expr: '0 * * * *' },
  { label: '每天 9 点', expr: '0 9 * * *' },
  { label: '每天 0 点', expr: '0 0 * * *' },
  { label: '每周一', expr: '0 9 * * 1' },
  { label: '每月 1 日', expr: '0 9 1 * *' },
];

function CreateForm({
  onSave,
  onCancel,
  workflows,
}: {
  onSave: (d: ScheduleCreate) => Promise<void>;
  onCancel: () => void;
  workflows: { id: string; name: string }[];
}) {
  const [workflowId, setWorkflowId] = useState(workflows[0]?.id ?? '');
  const [name, setName] = useState('');
  const [cronExpr, setCronExpr] = useState('0 9 * * *');
  const [saving, setSaving] = useState(false);

  return (
    <div className="bg-white border border-gray-200 rounded-xl p-5 shadow-sm space-y-3">
      <div className="grid grid-cols-2 gap-3">
        <div>
          <label className="text-xs text-gray-500 mb-1 block">名称</label>
          <input
            value={name}
            onChange={e => setName(e.target.value)}
            placeholder="定时任务名称"
            className="w-full px-3 py-2 text-sm border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-purple-300"
          />
        </div>
        <div>
          <label className="text-xs text-gray-500 mb-1 block">工作流</label>
          <select
            value={workflowId}
            onChange={e => setWorkflowId(e.target.value)}
            className="w-full px-3 py-2 text-sm border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-purple-300"
          >
            {workflows.length === 0 && <option value="">暂无工作流</option>}
            {workflows.map(w => <option key={w.id} value={w.id}>{w.name}</option>)}
          </select>
        </div>
      </div>
      <div>
        <label className="text-xs text-gray-500 mb-1 block">Cron 表达式</label>
        <div className="flex gap-2">
          <input
            value={cronExpr}
            onChange={e => setCronExpr(e.target.value)}
            placeholder="0 9 * * *"
            className="flex-1 px-3 py-2 text-sm border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-purple-300 font-mono"
          />
        </div>
        <div className="flex gap-1.5 mt-1.5 flex-wrap">
          {CRON_PRESETS.map(p => (
            <button
              key={p.expr}
              onClick={() => setCronExpr(p.expr)}
              className={`px-2 py-0.5 text-[11px] rounded border transition-colors ${
                cronExpr === p.expr
                  ? 'bg-purple-100 border-purple-300 text-purple-700'
                  : 'border-gray-200 text-gray-500 hover:bg-gray-50'
              }`}
            >
              {p.label}
            </button>
          ))}
        </div>
      </div>
      <div className="flex justify-end gap-2">
        <button onClick={onCancel} className="px-4 py-2 text-sm text-gray-600 border border-gray-200 rounded-lg hover:bg-gray-50">
          <X size={14} className="inline mr-1" />取消
        </button>
        <button
          disabled={!name.trim() || !workflowId || !cronExpr.trim() || saving}
          onClick={async () => {
            setSaving(true);
            try { await onSave({ workflow_id: workflowId, name, cron_expr: cronExpr }); }
            finally { setSaving(false); }
          }}
          className="px-4 py-2 text-sm bg-purple-600 text-white rounded-lg hover:bg-purple-700 disabled:opacity-40 flex items-center gap-1"
        >
          <Check size={14} />{saving ? '保存中…' : '创建'}
        </button>
      </div>
    </div>
  );
}

function ScheduleRow({
  schedule,
  onToggle,
  onDelete,
}: {
  schedule: Schedule;
  onToggle: (id: string) => void;
  onDelete: (id: string) => void;
}) {
  const enabled = Boolean(schedule.is_enabled);
  return (
    <tr className="border-b border-gray-100 hover:bg-gray-50">
      <td className="px-4 py-3">
        <div className="text-sm font-medium text-gray-800">{schedule.name}</div>
        <div className="text-xs text-gray-400 font-mono">{schedule.cron_expr}</div>
      </td>
      <td className="px-3 py-3 text-xs text-gray-500">{schedule.timezone}</td>
      <td className="px-3 py-3">
        <span className={`text-[11px] font-medium px-2 py-0.5 rounded-full ${enabled ? 'bg-green-100 text-green-700' : 'bg-gray-100 text-gray-500'}`}>
          {enabled ? '已启用' : '已停用'}
        </span>
      </td>
      <td className="px-3 py-3 text-xs text-gray-400">
        {schedule.run_count} 次 / {schedule.fail_count} 失败
      </td>
      <td className="px-3 py-3 text-xs text-gray-400">
        {schedule.last_run_at ? new Date(schedule.last_run_at).toLocaleString('zh-CN') : '—'}
      </td>
      <td className="px-3 py-3">
        <div className="flex items-center gap-1">
          <button
            onClick={() => onToggle(schedule.id)}
            className={`p-1.5 rounded transition-colors ${enabled ? 'text-green-500 hover:bg-green-50' : 'text-gray-400 hover:bg-gray-100'}`}
            title={enabled ? '停用' : '启用'}
          >
            {enabled ? <ToggleRight size={16} /> : <ToggleLeft size={16} />}
          </button>
          <button
            onClick={() => onDelete(schedule.id)}
            className="p-1.5 text-gray-400 hover:text-red-500 hover:bg-red-50 rounded transition-colors"
          >
            <Trash2 size={14} />
          </button>
        </div>
      </td>
    </tr>
  );
}

export default function SchedulePage() {
  const [schedules, setSchedules] = useState<Schedule[]>([]);
  const [workflows, setWorkflows] = useState<{ id: string; name: string }[]>([]);
  const [loading, setLoading] = useState(false);
  const [showCreate, setShowCreate] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [schedRes, wfRes] = await Promise.all([
        schedulesApi.list(),
        fetch('/api/workflows').then(r => r.json()),
      ]);
      setSchedules(schedRes.items);
      setWorkflows((wfRes.items ?? []).map((w: { id: string; name: string }) => ({ id: w.id, name: w.name })));
    } catch {
      toast.error('加载失败');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  const handleCreate = async (data: ScheduleCreate) => {
    await schedulesApi.create(data);
    toast.success('定时任务已创建');
    setShowCreate(false);
    load();
  };

  const handleToggle = async (id: string) => {
    await schedulesApi.toggle(id);
    load();
  };

  const handleDelete = async (id: string) => {
    if (!confirm('确认删除此定时任务？')) return;
    await schedulesApi.delete(id);
    toast.success('已删除');
    load();
  };

  return (
    <div className="h-full flex flex-col bg-gray-50">
      <div className="bg-white border-b border-gray-200 px-6 py-4 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Clock size={20} className="text-purple-500" />
          <h1 className="text-lg font-semibold text-gray-800">定时调度</h1>
          <span className="text-sm text-gray-400 ml-1">共 {schedules.length} 条</span>
        </div>
        <button
          onClick={() => setShowCreate(v => !v)}
          className="flex items-center gap-1.5 px-3 py-2 bg-purple-600 text-white text-sm rounded-lg hover:bg-purple-700"
        >
          <Plus size={15} />新建定时任务
        </button>
      </div>

      <div className="flex-1 overflow-y-auto p-6">
        {showCreate && (
          <div className="mb-4">
            <CreateForm onSave={handleCreate} onCancel={() => setShowCreate(false)} workflows={workflows} />
          </div>
        )}

        {loading ? (
          <div className="text-center text-gray-400 py-12">加载中…</div>
        ) : schedules.length === 0 ? (
          <div className="text-center py-20 text-gray-400">
            <Clock size={40} className="mx-auto mb-3 opacity-30" />
            <p className="text-sm">暂无定时任务</p>
          </div>
        ) : (
          <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
            <table className="w-full">
              <thead>
                <tr className="border-b border-gray-100 bg-gray-50">
                  <th className="px-4 py-2.5 text-left text-xs font-medium text-gray-500">名称 / Cron</th>
                  <th className="px-3 py-2.5 text-left text-xs font-medium text-gray-500">时区</th>
                  <th className="px-3 py-2.5 text-left text-xs font-medium text-gray-500">状态</th>
                  <th className="px-3 py-2.5 text-left text-xs font-medium text-gray-500">运行次数</th>
                  <th className="px-3 py-2.5 text-left text-xs font-medium text-gray-500">上次运行</th>
                  <th className="px-3 py-2.5 text-left text-xs font-medium text-gray-500">操作</th>
                </tr>
              </thead>
              <tbody>
                {schedules.map(s => (
                  <ScheduleRow key={s.id} schedule={s} onToggle={handleToggle} onDelete={handleDelete} />
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
