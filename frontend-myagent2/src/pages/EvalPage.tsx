import { useState, useEffect, useCallback } from 'react';
import { FlaskConical, Plus, Trash2, Play, ChevronRight, ChevronDown, X, Check } from 'lucide-react';
import { toast } from 'sonner';
import { evalsApi } from '@/api/evals';
import type { EvalDataset, EvalCase, EvalRun } from '@/api/evals';

const STATUS_LABEL: Record<string, { label: string; cls: string }> = {
  pending:   { label: '待运行',  cls: 'bg-gray-100 text-gray-500' },
  running:   { label: '运行中',  cls: 'bg-blue-100 text-blue-600' },
  completed: { label: '已完成',  cls: 'bg-green-100 text-green-700' },
  failed:    { label: '失败',    cls: 'bg-red-100 text-red-600' },
};

function DatasetPanel({
  dataset,
  selected,
  onSelect,
  onDelete,
}: {
  dataset: EvalDataset;
  selected: boolean;
  onSelect: () => void;
  onDelete: () => void;
}) {
  return (
    <div
      onClick={onSelect}
      className={`flex items-center justify-between px-3 py-2.5 rounded-lg cursor-pointer transition-colors ${
        selected ? 'bg-purple-50 border border-purple-200' : 'hover:bg-gray-100 border border-transparent'
      }`}
    >
      <div className="min-w-0">
        <div className="text-sm font-medium text-gray-800 truncate">{dataset.name}</div>
        {dataset.description && (
          <div className="text-xs text-gray-400 truncate">{dataset.description}</div>
        )}
      </div>
      <button
        onClick={e => { e.stopPropagation(); onDelete(); }}
        className="ml-2 p-1 text-gray-300 hover:text-red-500 rounded transition-colors shrink-0"
      >
        <Trash2 size={13} />
      </button>
    </div>
  );
}

function CaseRow({ c, onDelete }: { c: EvalCase; onDelete: () => void }) {
  const [expanded, setExpanded] = useState(false);
  return (
    <div className="border-b border-gray-100 last:border-0">
      <div
        className="flex items-start gap-2 px-4 py-2.5 hover:bg-gray-50 cursor-pointer"
        onClick={() => setExpanded(v => !v)}
      >
        {expanded ? <ChevronDown size={13} className="mt-0.5 shrink-0 text-gray-400" /> : <ChevronRight size={13} className="mt-0.5 shrink-0 text-gray-400" />}
        <div className="flex-1 min-w-0">
          <div className="text-sm text-gray-700 truncate">{c.question}</div>
          {c.tags && <span className="text-[10px] text-gray-400">{c.tags}</span>}
        </div>
        <span className={`text-[10px] px-1.5 py-0.5 rounded ${c.difficulty === 'easy' ? 'bg-green-50 text-green-600' : c.difficulty === 'hard' ? 'bg-red-50 text-red-600' : 'bg-yellow-50 text-yellow-600'}`}>
          {c.difficulty}
        </span>
        <button
          onClick={e => { e.stopPropagation(); onDelete(); }}
          className="ml-1 p-1 text-gray-300 hover:text-red-500 rounded"
        >
          <Trash2 size={12} />
        </button>
      </div>
      {expanded && (
        <div className="px-4 pb-3 text-xs text-gray-500 space-y-1 bg-gray-50">
          {c.expected_answer && <div><span className="font-medium text-gray-600">期望答案：</span>{c.expected_answer}</div>}
          {c.context && <div><span className="font-medium text-gray-600">上下文：</span>{c.context}</div>}
        </div>
      )}
    </div>
  );
}

function RunRow({ run }: { run: EvalRun }) {
  const st = STATUS_LABEL[run.status] ?? STATUS_LABEL.pending;
  const passRate = run.total_cases > 0
    ? Math.round((run.passed_cases / run.total_cases) * 100)
    : 0;
  return (
    <tr className="border-b border-gray-100 hover:bg-gray-50">
      <td className="px-4 py-2.5 text-sm text-gray-700">{run.label || run.id.slice(0, 12)}</td>
      <td className="px-3 py-2.5 text-xs text-gray-500">{run.model || '—'}</td>
      <td className="px-3 py-2.5">
        <span className={`text-[11px] px-2 py-0.5 rounded-full font-medium ${st.cls}`}>{st.label}</span>
      </td>
      <td className="px-3 py-2.5 text-xs text-gray-500">{run.passed_cases}/{run.total_cases}</td>
      <td className="px-3 py-2.5">
        <div className="flex items-center gap-1.5">
          <div className="h-1.5 w-16 bg-gray-100 rounded-full overflow-hidden">
            <div className={`h-full rounded-full ${passRate >= 80 ? 'bg-green-500' : passRate >= 50 ? 'bg-yellow-500' : 'bg-red-400'}`} style={{ width: `${passRate}%` }} />
          </div>
          <span className="text-xs text-gray-500">{passRate}%</span>
        </div>
      </td>
      <td className="px-3 py-2.5 text-xs text-gray-400">
        {run.created_at ? new Date(run.created_at).toLocaleString('zh-CN') : '—'}
      </td>
    </tr>
  );
}

export default function EvalPage() {
  const [datasets, setDatasets] = useState<EvalDataset[]>([]);
  const [selectedDs, setSelectedDs] = useState<EvalDataset | null>(null);
  const [cases, setCases] = useState<EvalCase[]>([]);
  const [runs, setRuns] = useState<EvalRun[]>([]);
  const [loading, setLoading] = useState(false);
  const [showAddDs, setShowAddDs] = useState(false);
  const [newDsName, setNewDsName] = useState('');
  const [newQ, setNewQ] = useState('');
  const [newAns, setNewAns] = useState('');
  const [activeTab, setActiveTab] = useState<'cases' | 'runs'>('cases');

  const loadDatasets = useCallback(async () => {
    setLoading(true);
    try {
      const res = await evalsApi.listDatasets();
      setDatasets(res.items);
    } finally {
      setLoading(false);
    }
  }, []);

  const loadDetail = useCallback(async (ds: EvalDataset) => {
    setSelectedDs(ds);
    const [cRes, rRes] = await Promise.all([
      evalsApi.listCases(ds.id),
      evalsApi.listRuns(ds.id),
    ]);
    setCases(cRes.items);
    setRuns(rRes.items);
  }, []);

  useEffect(() => { loadDatasets(); }, [loadDatasets]);

  const handleCreateDs = async () => {
    if (!newDsName.trim()) return;
    await evalsApi.createDataset({ name: newDsName.trim() });
    toast.success('数据集已创建');
    setNewDsName('');
    setShowAddDs(false);
    loadDatasets();
  };

  const handleDeleteDs = async (id: string) => {
    if (!confirm('确认删除此数据集？所有用例和运行记录将一并删除。')) return;
    await evalsApi.deleteDataset(id);
    toast.success('已删除');
    if (selectedDs?.id === id) setSelectedDs(null);
    loadDatasets();
  };

  const handleAddCase = async () => {
    if (!newQ.trim() || !selectedDs) return;
    await evalsApi.createCase({ dataset_id: selectedDs.id, question: newQ.trim(), expected_answer: newAns.trim() });
    toast.success('用例已添加');
    setNewQ(''); setNewAns('');
    loadDetail(selectedDs);
  };

  const handleDeleteCase = async (id: string) => {
    await evalsApi.deleteCase(id);
    if (selectedDs) loadDetail(selectedDs);
  };

  const handleCreateRun = async () => {
    if (!selectedDs) return;
    const run = await evalsApi.createRun({ dataset_id: selectedDs.id });
    toast.success(`评测运行已创建 (${run.total_cases} 条用例)`);
    loadDetail(selectedDs);
  };

  return (
    <div className="h-full flex bg-gray-50">
      {/* Sidebar: datasets */}
      <div className="w-56 bg-white border-r border-gray-200 flex flex-col shrink-0">
        <div className="px-4 py-3 border-b border-gray-100 flex items-center justify-between">
          <span className="text-sm font-semibold text-gray-700 flex items-center gap-1.5">
            <FlaskConical size={15} className="text-purple-500" />数据集
          </span>
          <button onClick={() => setShowAddDs(v => !v)} className="p-1 hover:bg-gray-100 rounded text-purple-500">
            <Plus size={14} />
          </button>
        </div>
        {showAddDs && (
          <div className="px-3 py-2 border-b border-gray-100 flex gap-1.5">
            <input
              value={newDsName}
              onChange={e => setNewDsName(e.target.value)}
              onKeyDown={e => e.key === 'Enter' && handleCreateDs()}
              placeholder="数据集名称"
              className="flex-1 text-xs border border-gray-200 rounded px-2 py-1.5 focus:outline-none focus:ring-2 focus:ring-purple-300"
            />
            <button onClick={handleCreateDs} className="p-1.5 bg-purple-600 text-white rounded">
              <Check size={12} />
            </button>
            <button onClick={() => setShowAddDs(false)} className="p-1.5 text-gray-400 hover:bg-gray-100 rounded">
              <X size={12} />
            </button>
          </div>
        )}
        <div className="flex-1 overflow-y-auto p-2 space-y-0.5">
          {loading ? <div className="text-xs text-gray-400 text-center py-4">加载中…</div> : null}
          {datasets.map(ds => (
            <DatasetPanel
              key={ds.id}
              dataset={ds}
              selected={selectedDs?.id === ds.id}
              onSelect={() => loadDetail(ds)}
              onDelete={() => handleDeleteDs(ds.id)}
            />
          ))}
          {!loading && datasets.length === 0 && (
            <div className="text-xs text-gray-400 text-center py-6">暂无数据集</div>
          )}
        </div>
      </div>

      {/* Main */}
      <div className="flex-1 flex flex-col overflow-hidden">
        {!selectedDs ? (
          <div className="flex-1 flex items-center justify-center text-gray-400">
            <div className="text-center">
              <FlaskConical size={40} className="mx-auto mb-3 opacity-30" />
              <p className="text-sm">选择或创建一个数据集开始评测</p>
            </div>
          </div>
        ) : (
          <>
            {/* Dataset header */}
            <div className="bg-white border-b border-gray-200 px-6 py-3 flex items-center justify-between">
              <div>
                <h2 className="font-semibold text-gray-800">{selectedDs.name}</h2>
                <p className="text-xs text-gray-400">{cases.length} 条用例 · {runs.length} 次运行</p>
              </div>
              <div className="flex gap-2">
                <div className="flex border border-gray-200 rounded-lg overflow-hidden text-xs">
                  {(['cases', 'runs'] as const).map(t => (
                    <button
                      key={t}
                      onClick={() => setActiveTab(t)}
                      className={`px-3 py-1.5 transition-colors ${activeTab === t ? 'bg-purple-600 text-white' : 'text-gray-500 hover:bg-gray-50'}`}
                    >
                      {t === 'cases' ? `用例 (${cases.length})` : `运行 (${runs.length})`}
                    </button>
                  ))}
                </div>
                {activeTab === 'runs' && (
                  <button
                    onClick={handleCreateRun}
                    className="flex items-center gap-1.5 px-3 py-1.5 bg-purple-600 text-white text-xs rounded-lg hover:bg-purple-700"
                  >
                    <Play size={13} />新建运行
                  </button>
                )}
              </div>
            </div>

            {activeTab === 'cases' ? (
              <div className="flex-1 flex flex-col overflow-hidden">
                {/* Add case form */}
                <div className="bg-white border-b border-gray-100 px-4 py-3 flex gap-2 items-end">
                  <div className="flex-1">
                    <input
                      value={newQ}
                      onChange={e => setNewQ(e.target.value)}
                      placeholder="输入测试问题…"
                      className="w-full text-sm px-3 py-2 border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-purple-300"
                    />
                  </div>
                  <div className="flex-1">
                    <input
                      value={newAns}
                      onChange={e => setNewAns(e.target.value)}
                      placeholder="期望答案（可选）"
                      className="w-full text-sm px-3 py-2 border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-purple-300"
                    />
                  </div>
                  <button
                    disabled={!newQ.trim()}
                    onClick={handleAddCase}
                    className="px-3 py-2 bg-purple-600 text-white text-sm rounded-lg hover:bg-purple-700 disabled:opacity-40 flex items-center gap-1 shrink-0"
                  >
                    <Plus size={14} />添加
                  </button>
                </div>
                <div className="flex-1 overflow-y-auto bg-white">
                  {cases.length === 0 ? (
                    <div className="text-center text-gray-400 text-sm py-12">暂无用例，请添加</div>
                  ) : cases.map(c => (
                    <CaseRow key={c.id} c={c} onDelete={() => handleDeleteCase(c.id)} />
                  ))}
                </div>
              </div>
            ) : (
              <div className="flex-1 overflow-y-auto">
                {runs.length === 0 ? (
                  <div className="text-center text-gray-400 text-sm py-12">暂无运行记录</div>
                ) : (
                  <table className="w-full bg-white">
                    <thead>
                      <tr className="border-b border-gray-100 bg-gray-50">
                        <th className="px-4 py-2.5 text-left text-xs font-medium text-gray-500">标签</th>
                        <th className="px-3 py-2.5 text-left text-xs font-medium text-gray-500">模型</th>
                        <th className="px-3 py-2.5 text-left text-xs font-medium text-gray-500">状态</th>
                        <th className="px-3 py-2.5 text-left text-xs font-medium text-gray-500">通过/总数</th>
                        <th className="px-3 py-2.5 text-left text-xs font-medium text-gray-500">通过率</th>
                        <th className="px-3 py-2.5 text-left text-xs font-medium text-gray-500">创建时间</th>
                      </tr>
                    </thead>
                    <tbody>
                      {runs.map(r => <RunRow key={r.id} run={r} />)}
                    </tbody>
                  </table>
                )}
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
}
