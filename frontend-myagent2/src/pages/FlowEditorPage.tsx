import { type ChangeEvent, useEffect, useRef } from 'react';
import { useMemo, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { ArrowLeft, Workflow, Download, Upload, Play, Save, Loader2 } from 'lucide-react';
import { toast } from 'sonner';
import FlowCanvas from '@/components/canvas/FlowCanvas';
import NodeLibrary from '@/components/panels/NodeLibrary';
import NodeConfigPanel from '@/components/panels/NodeConfigPanel';
import RunWorkflowDialog from '@/components/workflow/RunWorkflowDialog';
import { useWorkflowStore } from '@/stores/workflowStore';
import { workflowApi } from '@/api/workflows';

export default function FlowEditorPage() {
  const navigate = useNavigate();
  const { id } = useParams();
  const isNew = id === 'new';
  const loaded = useRef(false);
  const [runDialogOpen, setRunDialogOpen] = useState(false);

  const workflowName = useWorkflowStore((s) => s.workflowName);
  const dirty = useWorkflowStore((s) => s.dirty);
  const saving = useWorkflowStore((s) => s.saving);
  const loading = useWorkflowStore((s) => s.loading);
  const workflowId = useWorkflowStore((s) => s.workflowId);
  const nodes = useWorkflowStore((s) => s.nodes);
  const edges = useWorkflowStore((s) => s.edges);

  const inputFields = useMemo(() => {
    const startNode = nodes.find((node) => node.type === 'start');
    const outputs = (startNode?.data.outputs as string[] | undefined) ?? [];
    return outputs;
  }, [nodes]);

  const loadWorkflow = useWorkflowStore((s) => s.loadWorkflow);
  const resetForNew = useWorkflowStore((s) => s.resetForNew);
  const saveWorkflow = useWorkflowStore((s) => s.saveWorkflow);
  const setWorkflowMeta = useWorkflowStore((s) => s.setWorkflowMeta);
  const setNodes = useWorkflowStore((s) => s.setNodes);
  const setEdges = useWorkflowStore((s) => s.setEdges);
  const workflowDescription = useWorkflowStore((s) => s.workflowDescription);
  const fileInputRef = useRef<HTMLInputElement>(null);

  // 加载或重置
  useEffect(() => {
    if (loaded.current) return;
    loaded.current = true;
    if (isNew) {
      resetForNew();
    } else if (id) {
      loadWorkflow(id).catch(() => toast.error('加载工作流失败'));
    }
  }, [id, isNew, loadWorkflow, resetForNew]);

  const handleSave = async () => {
    try {
      const savedId = await saveWorkflow();
      toast.success('保存成功');
      // 新建保存后更新 URL
      if (isNew && savedId) {
        navigate(`/workflows/${savedId}/edit`, { replace: true });
      }
    } catch {
      toast.error('保存失败');
    }
  };

  const handleRun = async () => {
    const wfId = workflowId;
    if (!wfId) {
      toast.error('请先保存工作流');
      return;
    }
    setRunDialogOpen(true);
  };

  const handleRunSubmit = async (inputs: Record<string, unknown>) => {
    if (!workflowId) return;
    try {
      const res = await workflowApi.execute(workflowId, inputs);
      toast.success(`已启动执行: ${res.execution_id}`);
      setRunDialogOpen(false);
      navigate(`/executions?selected=${res.execution_id}`);
    } catch {
      toast.error('运行失败');
    }
  };

  const handleExport = () => {
    const payload = {
      id: workflowId ?? undefined,
      name: workflowName,
      description: workflowDescription,
      definition: { nodes, edges },
    };
    const blob = new Blob([JSON.stringify(payload, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = `${workflowName || 'workflow'}.json`;
    link.click();
    URL.revokeObjectURL(url);
  };

  const handleImportFile = async (event: ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file) return;
    try {
      const text = await file.text();
      const data = JSON.parse(text) as {
        name?: string;
        description?: string;
        definition?: { nodes?: typeof nodes; edges?: typeof edges };
      };
      setWorkflowMeta(data.name || workflowName, data.description || '');
      setNodes(data.definition?.nodes ?? []);
      setEdges(data.definition?.edges ?? []);
      toast.success('工作流 JSON 已导入到编辑器');
    } catch {
      toast.error('导入失败，请检查工作流 JSON');
    } finally {
      event.target.value = '';
    }
  };

  return (
    <div className="flex flex-col h-screen w-screen bg-white">
      {/* 顶部工具栏 */}
      <header className="h-12 border-b border-gray-200 flex items-center justify-between px-4 bg-white shrink-0">
        <div className="flex items-center gap-3">
          <button
            onClick={() => navigate('/workflows')}
            className="p-1.5 rounded-lg hover:bg-gray-100 text-gray-500 transition-colors"
            title="返回工作流列表"
          >
            <ArrowLeft size={18} />
          </button>
          <div className="h-5 w-px bg-gray-200" />
          <Workflow size={20} className="text-purple-600" />
          <input
            className="font-semibold text-gray-800 bg-transparent border-none outline-none w-48 hover:bg-gray-50 focus:bg-gray-50 px-1 rounded"
            value={workflowName}
            onChange={(e) => setWorkflowMeta(e.target.value, workflowDescription)}
            placeholder="工作流名称"
          />
          {dirty && <span className="text-xs text-amber-500">● 未保存</span>}
          {loading && <Loader2 size={14} className="animate-spin text-gray-400" />}
        </div>
        <div className="flex items-center gap-2">
          <input ref={fileInputRef} type="file" accept="application/json" className="hidden" onChange={handleImportFile} />
          <button onClick={() => fileInputRef.current?.click()} className="flex items-center gap-1.5 px-3 py-1.5 text-xs bg-gray-100 hover:bg-gray-200 rounded-md text-gray-700 transition-colors">
            <Upload size={14} />
            导入
          </button>
          <button onClick={handleExport} className="flex items-center gap-1.5 px-3 py-1.5 text-xs bg-gray-100 hover:bg-gray-200 rounded-md text-gray-700 transition-colors">
            <Download size={14} />
            导出
          </button>
          <button
            onClick={handleSave}
            disabled={saving || !dirty}
            className="flex items-center gap-1.5 px-3 py-1.5 text-xs bg-blue-600 hover:bg-blue-700 disabled:opacity-50 rounded-md text-white transition-colors"
          >
            {saving ? <Loader2 size={14} className="animate-spin" /> : <Save size={14} />}
            保存
          </button>
          <button
            onClick={handleRun}
            className="flex items-center gap-1.5 px-3 py-1.5 text-xs bg-purple-600 hover:bg-purple-700 rounded-md text-white transition-colors"
          >
            <Play size={14} />
            运行
          </button>
        </div>
      </header>

      {/* 主体区域 */}
      <div className="flex flex-1 overflow-hidden">
        <NodeLibrary />
        <FlowCanvas />
        <NodeConfigPanel />
      </div>
      <RunWorkflowDialog
        open={runDialogOpen}
        title={workflowName}
        inputFields={inputFields}
        onClose={() => setRunDialogOpen(false)}
        onSubmit={handleRunSubmit}
      />
    </div>
  );
}
