import { useState, useEffect, useCallback, useMemo } from 'react';
import { useSearchParams } from 'react-router-dom';
import { Activity, XCircle, CheckCircle2, Loader2, AlertTriangle, ChevronRight, Eye, RotateCcw, Trash2 } from 'lucide-react';
import { toast } from 'sonner';
import PageHeader from '@/components/layout/PageHeader';
import type { ExecutionRecord } from '@/types/entities';
import { executionApi } from '@/api/executions';
import type { ExecutionDTO, CheckpointInfo } from '@/api/executions';
import { workflowApi } from '@/api/workflows';
import type { FlowNode } from '@/types/workflow';

const STATUS_MAP: Record<string, { label: string; icon: typeof CheckCircle2; color: string; bgColor: string }> = {
  running: { label: '运行中', icon: Loader2, color: 'text-blue-600', bgColor: 'bg-blue-50' },
  success: { label: '成功', icon: CheckCircle2, color: 'text-green-600', bgColor: 'bg-green-50' },
  done: { label: '成功', icon: CheckCircle2, color: 'text-green-600', bgColor: 'bg-green-50' },
  failed: { label: '失败', icon: XCircle, color: 'text-red-600', bgColor: 'bg-red-50' },
  error: { label: '失败', icon: XCircle, color: 'text-red-600', bgColor: 'bg-red-50' },
  cancelled: { label: '已取消', icon: XCircle, color: 'text-gray-500', bgColor: 'bg-gray-50' },
  killed: { label: '已终止', icon: XCircle, color: 'text-gray-500', bgColor: 'bg-gray-50' },
  timeout: { label: '超时', icon: AlertTriangle, color: 'text-amber-600', bgColor: 'bg-amber-50' },
};

const DEFAULT_STATUS = { label: '未知', icon: AlertTriangle, color: 'text-gray-400', bgColor: 'bg-gray-50' };

function dtoToExec(d: ExecutionDTO): ExecutionRecord {
  const started = d.started_at ? new Date(d.started_at).getTime() : Date.now();
  const finished = d.finished_at ? new Date(d.finished_at).getTime() : Date.now();
  return {
    id: d.id,
    workflowId: d.workflow_id,
    workflowName: d.workflow_name || d.workflow_id,
    version: '',
    status: (d.status === 'done' ? 'success' : d.status === 'error' ? 'failed' : d.status === 'killed' ? 'cancelled' : d.status) as ExecutionRecord['status'],
    totalDurationMs: d.finished_at ? finished - started : Date.now() - started,
    totalTokens: d.total_tokens,
    cost: d.total_cost,
    error: d.error || undefined,
    startedAt: d.started_at || d.created_at,
    finishedAt: d.finished_at,
  };
}

// Trace 瀑布图模拟数据
interface TraceNode {
  nodeId: string;
  nodeName: string;
  nodeType: string;
  status: 'success' | 'failed' | 'running';
  startMs: number;
  durationMs: number;
  inputTokens?: number;
  outputTokens?: number;
  error?: string;
  resultPreview?: string;
}

interface ExecutionDetail extends ExecutionRecord {
  inputs?: Record<string, unknown>;
  outputs?: Record<string, unknown>;
  logs?: unknown[];
}

interface TraceSpanDTO {
  id: string;
  node_id: string;
  node_type: string;
  status: string;
  start_time: string;
  end_time?: string;
  input_tokens?: number;
  output_tokens?: number;
  latency_ms?: number;
  result_preview?: string;
  error?: string;
}

function relativeTime(iso: string): string {
  const diff = Date.now() - new Date(iso).getTime();
  const minutes = Math.floor(diff / 60000);
  if (minutes < 1) return '刚刚';
  if (minutes < 60) return `${minutes}分钟前`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}小时前`;
  return `${Math.floor(hours / 24)}天前`;
}

export default function ExecutionMonitorPage() {
  const [searchParams] = useSearchParams();
  const [filterStatus, setFilterStatus] = useState<string>('all');
  const [selectedExec, setSelectedExec] = useState<string | null>(null);
  const [allExecs, setAllExecs] = useState<ExecutionRecord[]>([]);
  const [loadingExecs, setLoadingExecs] = useState(true);

  const fetchExecs = useCallback(async () => {
    setLoadingExecs(true);
    try {
      const res = await executionApi.list({ limit: 100 });
      setAllExecs(res.items.map(dtoToExec));
    } catch {
      toast.error('加载执行记录失败');
    } finally {
      setLoadingExecs(false);
    }
  }, []);

  useEffect(() => { fetchExecs(); }, [fetchExecs]);

  useEffect(() => {
    const selected = searchParams.get('selected');
    if (selected) {
      setSelectedExec(selected);
    }
  }, [searchParams]);

  useEffect(() => {
    if (selectedExec) return;
    if (allExecs.length === 0) return;
    setSelectedExec(allExecs[0].id);
  }, [allExecs, selectedExec]);

  const running = allExecs.filter((e) => e.status === 'running');
  const history = allExecs.filter((e) => e.status !== 'running');
  const filtered = filterStatus === 'all'
    ? history
    : history.filter((e) => e.status === filterStatus);

  return (
    <div className="flex flex-col h-full">
      <PageHeader
        title="执行监控"
        description={`${running.length} 个运行中 · ${history.length} 条历史记录`}
        icon={<Activity size={24} />}
      />

      <div className="flex flex-1 overflow-hidden">
        {/* 左侧列表 */}
        <div className="flex-1 overflow-y-auto border-r border-gray-200">
          {/* 运行中 */}
          {running.length > 0 && (
            <div className="p-4">
              <h3 className="text-xs font-semibold text-blue-600 uppercase tracking-wider mb-3 flex items-center gap-1.5">
                <Loader2 size={12} className="animate-spin" />
                运行中 ({running.length})
              </h3>
              <div className="space-y-2">
                {running.map((exec) => (
                  <RunningCard key={exec.id} exec={exec} selected={selectedExec === exec.id} onClick={() => setSelectedExec(exec.id)} />
                ))}
              </div>
            </div>
          )}

          {/* 历史 */}
          <div className="p-4 pt-2">
            <div className="flex items-center justify-between mb-3">
              <h3 className="text-xs font-semibold text-gray-500 uppercase tracking-wider">历史记录</h3>
              <div className="flex gap-1">
                {['all', 'success', 'failed', 'timeout'].map((s) => (
                  <button
                    key={s}
                    onClick={() => setFilterStatus(s)}
                    className={`px-2 py-0.5 text-[10px] rounded ${filterStatus === s ? 'bg-purple-100 text-purple-700' : 'text-gray-400 hover:bg-gray-100'}`}
                  >
                    {s === 'all' ? '全部' : (STATUS_MAP[s] ?? DEFAULT_STATUS).label}
                  </button>
                ))}
              </div>
            </div>

            <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-gray-100 bg-gray-50/50">
                    <th className="text-left text-[11px] font-medium text-gray-400 px-4 py-2">ID</th>
                    <th className="text-left text-[11px] font-medium text-gray-400 px-4 py-2">工作流</th>
                    <th className="text-left text-[11px] font-medium text-gray-400 px-4 py-2">状态</th>
                    <th className="text-right text-[11px] font-medium text-gray-400 px-4 py-2">耗时</th>
                    <th className="text-right text-[11px] font-medium text-gray-400 px-4 py-2">Token</th>
                    <th className="text-right text-[11px] font-medium text-gray-400 px-4 py-2">时间</th>
                    <th className="px-4 py-2"></th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-50">
                  {filtered.map((exec) => {
                    const st = STATUS_MAP[exec.status] ?? DEFAULT_STATUS;
                    const Icon = st.icon;
                    return (
                      <tr
                        key={exec.id}
                        onClick={() => setSelectedExec(exec.id)}
                        className={`cursor-pointer transition-colors ${selectedExec === exec.id ? 'bg-purple-50' : 'hover:bg-gray-50'}`}
                      >
                        <td className="px-4 py-2.5 font-mono text-xs text-gray-500">{exec.id}</td>
                        <td className="px-4 py-2.5">
                          <div className="text-sm text-gray-900">{exec.workflowName}</div>
                          <div className="text-[10px] text-gray-400">{exec.version}</div>
                        </td>
                        <td className="px-4 py-2.5">
                          <span className={`flex items-center gap-1 text-xs ${st.color}`}>
                            <Icon size={13} />
                            {st.label}
                          </span>
                        </td>
                        <td className="px-4 py-2.5 text-right text-xs text-gray-500">{(exec.totalDurationMs / 1000).toFixed(1)}s</td>
                        <td className="px-4 py-2.5 text-right text-xs text-gray-500">{exec.totalTokens.toLocaleString()}</td>
                        <td className="px-4 py-2.5 text-right text-xs text-gray-400">{relativeTime(exec.startedAt)}</td>
                        <td className="px-4 py-2.5">
                          <ChevronRight size={14} className="text-gray-300" />
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </div>
        </div>

        {/* 右侧 Trace 详情 */}
        <div className="w-[440px] bg-white overflow-y-auto shrink-0">
          {selectedExec ? (
            <TraceDetail execId={selectedExec} executions={allExecs} loading={loadingExecs} />
          ) : (
            <div className="flex-1 flex items-center justify-center h-full text-gray-400 text-sm">
              <div className="text-center">
                <Eye size={32} className="mx-auto mb-2 opacity-30" />
                <p>选择一条执行记录查看 Trace</p>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

function RunningCard({ exec, selected, onClick }: { exec: ExecutionRecord; selected: boolean; onClick: () => void }) {
  const progress = exec.progress ? (exec.progress.current / exec.progress.total) * 100 : 0;
  return (
    <div
      onClick={onClick}
      className={`bg-white rounded-lg border p-3 cursor-pointer transition-all ${
        selected ? 'border-blue-300 shadow-sm' : 'border-gray-200 hover:border-blue-200'
      }`}
    >
      <div className="flex items-center justify-between mb-2">
        <div className="flex items-center gap-2">
          <Loader2 size={14} className="text-blue-500 animate-spin" />
          <span className="text-sm font-medium text-gray-900">{exec.workflowName}</span>
          <span className="text-[10px] text-gray-400">{exec.version}</span>
        </div>
        <span className="text-xs text-gray-500">{exec.id}</span>
      </div>
      <div className="flex items-center gap-3">
        <div className="flex-1">
          <div className="h-1.5 bg-gray-100 rounded-full overflow-hidden">
            <div className="h-full bg-blue-500 rounded-full transition-all" style={{ width: `${progress}%` }} />
          </div>
        </div>
        <span className="text-xs text-gray-500 shrink-0">
          节点 {exec.progress?.current}/{exec.progress?.total}
        </span>
      </div>
      <div className="flex items-center gap-4 mt-2 text-[11px] text-gray-400">
        <span>当前: {exec.currentNode}</span>
        <span>{(exec.totalDurationMs / 1000).toFixed(1)}s</span>
        <span>{exec.totalTokens} tokens</span>
        <button className="ml-auto text-red-400 hover:text-red-600 text-xs">取消</button>
      </div>
    </div>
  );
}

function TraceDetail({ execId, executions, loading }: { execId: string; executions: ExecutionRecord[]; loading: boolean }) {
  const exec = executions.find((e) => e.id === execId);
  const [traceNodes, setTraceNodes] = useState<TraceNode[]>([]);
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null);
  const [execDetail, setExecDetail] = useState<ExecutionDetail | null>(null);
  const [nodeLabels, setNodeLabels] = useState<Record<string, string>>({});
  const [checkpoint, setCheckpoint] = useState<CheckpointInfo | null>(null);
  const [resuming, setResuming] = useState(false);

  useEffect(() => {
    if (!exec || exec.status === 'running') { setCheckpoint(null); return; }
    executionApi.getCheckpoint(execId).then(setCheckpoint).catch(() => setCheckpoint(null));
  }, [exec, execId]);

  const handleResume = async () => {
    setResuming(true);
    try {
      await executionApi.resume(execId);
      toast.success('已重新触发执行，请稍候刷新列表');
    } catch (e) {
      toast.error('恢复失败');
    } finally {
      setResuming(false);
    }
  };

  const handleDeleteCheckpoint = async () => {
    await executionApi.deleteCheckpoint(execId);
    setCheckpoint(null);
    toast.success('断点已清除');
  };

  useEffect(() => {
    let cancelled = false;
    async function loadTraces() {
      if (!exec) {
        setTraceNodes([]);
        return;
      }
      try {
        const res = await executionApi.traces(execId);
        if (cancelled) return;
        const items = (res.items ?? []) as TraceSpanDTO[];
        const baseStart = items.length > 0 ? new Date(items[0].start_time).getTime() : 0;
        setTraceNodes(items.map((item) => {
          const start = item.start_time ? new Date(item.start_time).getTime() : baseStart;
          const end = item.end_time ? new Date(item.end_time).getTime() : start + (item.latency_ms ?? 0);
          return {
            nodeId: item.node_id,
            nodeName: item.node_id,
            nodeType: item.node_type,
            status: item.status === 'error' ? 'failed' : item.status === 'done' ? 'success' : 'running',
            startMs: Math.max(start - baseStart, 0),
            durationMs: item.latency_ms ?? Math.max(end - start, 0),
            inputTokens: item.input_tokens ?? 0,
            outputTokens: item.output_tokens ?? 0,
            error: item.error ?? '',
            resultPreview: item.result_preview ?? '',
          };
        }));
      } catch {
        if (!cancelled) {
          setTraceNodes([]);
        }
      }
    }
    loadTraces();
    return () => {
      cancelled = true;
    };
  }, [exec, execId]);

  useEffect(() => {
    let cancelled = false;
    async function loadDetail() {
      if (!exec) {
        setExecDetail(null);
        setNodeLabels({});
        return;
      }
      try {
        const detail = await executionApi.get(execId);
        if (cancelled) return;
        setExecDetail({
          ...exec,
          inputs: detail.inputs,
          outputs: detail.outputs,
          logs: detail.logs,
        });
        if (exec.workflowId) {
          const workflow = await workflowApi.get(exec.workflowId);
          if (cancelled) return;
          const definition = workflow.definition as { nodes?: FlowNode[] };
          const labels = Object.fromEntries((definition.nodes ?? []).map((node) => [node.id, String(node.data?.label ?? node.id)]));
          setNodeLabels(labels);
        } else {
          setNodeLabels({});
        }
      } catch {
        if (!cancelled) {
          setExecDetail(exec ? { ...exec } : null);
          setNodeLabels({});
        }
      }
    }
    loadDetail();
    return () => {
      cancelled = true;
    };
  }, [exec, execId]);

  const enrichedTraceNodes = useMemo(
    () => traceNodes.map((node) => ({ ...node, nodeName: nodeLabels[node.nodeId] ?? node.nodeName })),
    [nodeLabels, traceNodes],
  );

  if (!exec) {
    return (
      <div className="h-full flex items-center justify-center text-sm text-gray-400 px-6 text-center">
        {loading ? '正在加载执行记录...' : `未找到执行 ${execId}，可能列表尚未刷新或该执行已被删除`}
      </div>
    );
  }

  const selectedNode = enrichedTraceNodes.find((node) => node.nodeId === selectedNodeId) ?? enrichedTraceNodes[0] ?? null;

  const st = STATUS_MAP[exec.status] ?? DEFAULT_STATUS;
  const Icon = st.icon;
  const totalMs = exec.status === 'running' ? 8300 : exec.totalDurationMs;

  return (
    <div className="p-5">
      {/* 头部 */}
      <div className="mb-5">
        <div className="flex items-center gap-2 mb-1">
          <span className={`flex items-center gap-1 text-sm font-medium ${st.color}`}>
            <Icon size={16} className={exec.status === 'running' ? 'animate-spin' : ''} />
            {exec.id}
          </span>
          <span className="text-xs text-gray-400">· {exec.workflowName} {exec.version}</span>
        </div>
        <div className="flex items-center gap-4 text-xs text-gray-500">
          <span>总耗时: {(totalMs / 1000).toFixed(1)}s</span>
          <span>Token: {exec.totalTokens.toLocaleString()}</span>
          {exec.cost > 0 && <span>成本: ¥{exec.cost.toFixed(4)}</span>}
        </div>
      </div>

      <div className="grid grid-cols-2 gap-3 mb-4">
        <SummaryCard title="输入摘要" value={execDetail?.inputs} emptyText="无输入" />
        <SummaryCard title="输出摘要" value={execDetail?.outputs} emptyText={exec.status === 'running' ? '执行中，暂无输出' : '无输出'} />
      </div>

      {/* 断点恢复卡片 */}
      {checkpoint?.has_checkpoint && (
        <div className="mb-4 p-3 bg-amber-50 border border-amber-200 rounded-xl">
          <div className="flex items-center justify-between gap-2 mb-2">
            <div className="text-xs font-semibold text-amber-700 flex items-center gap-1.5">
              <RotateCcw size={12} />断点恢复可用
            </div>
            <button onClick={handleDeleteCheckpoint} className="text-[10px] text-gray-400 hover:text-red-500 flex items-center gap-1">
              <Trash2 size={10} />清除
            </button>
          </div>
          <div className="text-[11px] text-amber-600 mb-1">
            已完成 {checkpoint.completed_count}/{checkpoint.total_nodes ?? '?'} 个节点
            {checkpoint.checkpoint_at && ` · ${new Date(checkpoint.checkpoint_at).toLocaleString('zh-CN')}`}
          </div>
          <div className="h-1.5 bg-amber-100 rounded-full overflow-hidden mb-2">
            <div
              className="h-full bg-amber-400 rounded-full"
              style={{ width: `${checkpoint.progress_pct ?? 0}%` }}
            />
          </div>
          <div className="flex gap-2">
            <button
              onClick={handleResume}
              disabled={resuming}
              className="flex-1 py-1.5 bg-amber-500 text-white text-xs rounded-lg hover:bg-amber-600 disabled:opacity-40 flex items-center justify-center gap-1"
            >
              {resuming ? <Loader2 size={12} className="animate-spin" /> : <RotateCcw size={12} />}
              {resuming ? '恢复中…' : '从断点继续'}
            </button>
          </div>
        </div>
      )}

      {/* 错误信息 */}
      {exec.error && (
        <div className="mb-4 p-3 bg-red-50 border border-red-200 rounded-lg">
          <div className="flex items-center gap-1.5 text-xs font-semibold text-red-600 mb-1">
            <XCircle size={12} />
            错误信息
          </div>
          <p className="text-xs text-red-700 whitespace-pre-wrap break-all">{exec.error}</p>
        </div>
      )}

      {/* Trace 瀑布图 */}
      <h4 className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-3">执行链路</h4>
      <div className="space-y-1.5">
        {enrichedTraceNodes.length === 0 && (
          <div className="text-xs text-gray-400 py-2">暂无阶段日志（历史执行可能发生在日志持久化能力上线之前）</div>
        )}
        {enrichedTraceNodes.map((node) => {
          const safeTotalMs = Math.max(totalMs, 1);
          const widthPct = Math.max((node.durationMs / safeTotalMs) * 100, 2);
          const leftPct = (node.startMs / safeTotalMs) * 100;
          const typeColors: Record<string, string> = {
            start: 'bg-green-400', end: 'bg-red-400', llm: 'bg-purple-500', tool: 'bg-amber-400',
          };
          const barColor = typeColors[node.nodeType] || 'bg-gray-400';

          return (
            <div key={`${node.nodeId}-${node.startMs}`} className="space-y-1 cursor-pointer" onClick={() => setSelectedNodeId(node.nodeId)}>
              <div className="flex items-center gap-3">
              {/* 节点名 */}
                <div className="w-28 text-xs text-right text-gray-600 truncate shrink-0">
                  {node.nodeName}
                </div>

              {/* 瀑布条 */}
                <div className="flex-1 h-6 bg-gray-50 rounded relative overflow-hidden">
                  <div
                    className={`absolute top-0.5 bottom-0.5 rounded ${barColor} flex items-center px-1.5`}
                    style={{ left: `${leftPct}%`, width: `${widthPct}%`, minWidth: '24px' }}
                  >
                    <span className="text-[10px] text-white font-medium truncate">
                      {node.durationMs >= 100 ? `${(node.durationMs / 1000).toFixed(1)}s` : `${node.durationMs}ms`}
                    </span>
                  </div>
                </div>

              {/* Token 信息 */}
                <div className="w-20 text-[10px] text-gray-400 text-right shrink-0">
                  {node.inputTokens ? `${node.inputTokens}→${node.outputTokens}` : '—'}
                </div>
              </div>
              {(node.error || node.resultPreview) && (
                <div className="ml-[124px] mr-[84px] text-[10px] text-gray-500 bg-gray-50 rounded px-2 py-1 break-all whitespace-pre-wrap">
                  {node.error || node.resultPreview}
                </div>
              )}
            </div>
          );
        })}
      </div>

      {/* 时间轴刻度 */}
      <div className="flex items-center mt-1 ml-[124px] mr-[84px]">
        <span className="text-[9px] text-gray-300">0s</span>
        <div className="flex-1" />
        <span className="text-[9px] text-gray-300">{(totalMs / 1000).toFixed(1)}s</span>
      </div>

      <div className="mt-5 border-t border-gray-100 pt-4">
        <h4 className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-3">阶段详情</h4>
        {selectedNode ? (
          <div className="bg-gray-50 rounded-lg border border-gray-200 p-3 space-y-2">
            <div className="flex items-center justify-between gap-3">
              <div>
                <div className="text-sm font-medium text-gray-900">{selectedNode.nodeName}</div>
                <div className="text-[10px] text-gray-400">{selectedNode.nodeId} · {selectedNode.nodeType}</div>
              </div>
              <span className={`text-[10px] px-2 py-0.5 rounded ${selectedNode.status === 'failed' ? 'bg-red-50 text-red-600' : selectedNode.status === 'running' ? 'bg-blue-50 text-blue-600' : 'bg-green-50 text-green-600'}`}>
                {selectedNode.status === 'failed' ? '失败' : selectedNode.status === 'running' ? '运行中' : '成功'}
              </span>
            </div>
            <div className="grid grid-cols-2 gap-2 text-[11px] text-gray-600">
              <DetailKV label="耗时" value={selectedNode.durationMs >= 100 ? `${(selectedNode.durationMs / 1000).toFixed(2)}s` : `${selectedNode.durationMs}ms`} />
              <DetailKV label="Token" value={selectedNode.inputTokens ? `${selectedNode.inputTokens} → ${selectedNode.outputTokens}` : '—'} />
              <DetailKV label="开始偏移" value={`${(selectedNode.startMs / 1000).toFixed(2)}s`} />
              <DetailKV label="结果" value={selectedNode.error ? '异常' : '已完成'} />
            </div>
            <div>
              <div className="text-[10px] font-medium text-gray-500 mb-1">输出 / 错误摘要</div>
              <div className="text-[11px] text-gray-700 whitespace-pre-wrap break-all bg-white border border-gray-200 rounded px-2 py-2 min-h-[60px]">
                {selectedNode.error || selectedNode.resultPreview || '暂无摘要'}
              </div>
            </div>
          </div>
        ) : (
          <div className="text-xs text-gray-400">暂无可查看的阶段详情</div>
        )}
      </div>
    </div>
  );
}

function SummaryCard({ title, value, emptyText }: { title: string; value: Record<string, unknown> | undefined; emptyText: string }) {
  const text = value && Object.keys(value).length > 0 ? JSON.stringify(value, null, 2) : '';
  return (
    <div className="border border-gray-200 rounded-lg overflow-hidden bg-white">
      <div className="px-3 py-2 text-[10px] font-semibold text-gray-500 uppercase tracking-wider bg-gray-50 border-b border-gray-100">{title}</div>
      <pre className="p-3 text-[11px] text-gray-700 whitespace-pre-wrap break-all min-h-[96px] max-h-44 overflow-auto">{text || emptyText}</pre>
    </div>
  );
}

function DetailKV({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-center justify-between gap-2 bg-white border border-gray-200 rounded px-2 py-1.5">
      <span className="text-gray-400">{label}</span>
      <span className="text-gray-700 text-right">{value}</span>
    </div>
  );
}
