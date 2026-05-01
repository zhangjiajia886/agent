import { useState, useEffect, useRef, useCallback, useMemo } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { ArrowLeft, Save, Rocket, Plus, X, Send, Loader2, ChevronDown, ChevronRight, Brain, Maximize2, Minimize2 } from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';

import { toast } from 'sonner';
import { appApi, streamPreviewChat, type AppDTO, type AppVariable } from '@/api/apps';
import { DiagramBlock, isDiagramLang } from '@/components/DiagramBlock';
import { LazyImage } from '@/components/LazyImage';
import { modelApi } from '@/api/models';

function parseThink(raw: string): { thinking: string; answer: string } {
  // Handle both <thinking> (Claude) and <think> (Qwen3)
  for (const tag of ['thinking', 'think']) {
    const open = `<${tag}>`, close = `</${tag}>`;
    const startM = raw.match(new RegExp(`^${open}([\\s\\S]*?)(${close}|$)`));
    if (startM) return { thinking: startM[1].trim(), answer: raw.slice(startM[0].length).trim() };
    const anyM = raw.match(new RegExp(`^([\\s\\S]*?)${open}([\\s\\S]*?)${close}([\\s\\S]*)$`));
    if (anyM) return { thinking: anyM[2].trim(), answer: (anyM[1] + anyM[3]).trim() };
  }
  return { thinking: '', answer: raw };
}

const ALL_BUILTIN_TOOLS = [
  { name: 'web_search',   label: '联网搜索',   desc: '实时搜索互联网' },
  { name: 'web_fetch',    label: '网页抓取',   desc: '获取网页纯文本内容' },
  { name: 'python_exec',  label: 'Python 执行', desc: '运行 Python 代码' },
  { name: 'bash',         label: 'Bash 命令',   desc: '执行 Shell 命令' },
  { name: 'http_request', label: 'HTTP 请求',   desc: '调用外部 API' },
  { name: 'read_file',    label: '读取文件',    desc: '读取本地文件' },
  { name: 'write_file',   label: '写入文件',    desc: '写入本地文件' },
  { name: 'edit_file',    label: '编辑文件',    desc: 'str_replace 精确修改文件' },
  { name: 'grep_search',  label: '文本搜索',    desc: '在文件中搜索文本' },
  { name: 'find_files',   label: '查找文件',    desc: 'Glob 模式搜索文件' },
  { name: 'list_dir',     label: '列出目录',    desc: '查看目录内容' },
  { name: 'todo',         label: '任务列表',    desc: '读写 Todo 任务列表' },
  { name: 'mysql_query',  label: 'MySQL 查询',  desc: '连接 MySQL 执行 SQL' },
  { name: 'mysql_schema', label: 'MySQL 结构',  desc: '查看表结构和字段' },
  { name: 'redis_cmd',    label: 'Redis 命令',  desc: 'GET/SET/DEL 等 Redis 操作' },
  { name: 'sqlite_query', label: 'SQLite 查询', desc: '查询本地 SQLite 文件' },
  { name: 'milvus_search',label: 'Milvus 搜索', desc: '向量相似度搜索' },
  { name: 'excel_read',   label: 'Excel 读取',  desc: '读取 xlsx/xls 表格' },
  { name: 'excel_write',  label: 'Excel 写入',  desc: '写入数据到 Excel' },
  { name: 'word_read',    label: 'Word 读取',   desc: '读取 .docx 文档文本' },
  { name: 'word_write',   label: 'Word 写入',   desc: '创建 Word 文档' },
  { name: 'ppt_read',     label: 'PPT 读取',    desc: '提取幻灯片文本内容' },
  { name: 'ppt_write',    label: 'PPT 写入',    desc: '创建 PowerPoint 文件' },
  { name: 'md_to_html',       label: 'MD→HTML',       desc: 'Markdown 转 HTML' },
  // ── 新增工具 ──
  { name: 'insert_file_line', label: '行级插入',       desc: '在指定行号前插入内容' },
  { name: 'undo_edit',        label: '撤销编辑',       desc: '撤销最近一次文件修改' },
  { name: 'git',              label: 'Git 操作',       desc: 'diff / log / status / commit / push 等' },
  { name: 'notebook_read',    label: 'Notebook 读取',  desc: '读取 .ipynb 所有 cell 内容' },
  { name: 'notebook_edit',    label: 'Notebook 编辑',  desc: '编辑指定 cell 内容或追加新 cell' },
  { name: 'zip_files',        label: 'ZIP 打包',       desc: '多文件打包为 zip，返回下载链接' },
  { name: 'image_read',       label: '读取图片',       desc: '读图为 Base64（多模态 LLM 输入）' },
  { name: 'pdf_read',         label: 'PDF 读取',       desc: '提取 PDF 文字内容（逐页）' },
  { name: 'env_info',         label: '环境信息',       desc: '查看 OS / Python / 内存等运行环境' },
  { name: 'process_list',     label: '进程列表',       desc: '查看运行中进程（支持名称过滤）' },
  { name: 'multi_bash',       label: '并发 Bash',      desc: '同时执行多条 Shell 命令，并行加速' },
];

interface ChatMsg { role: 'user' | 'assistant'; content: string; loading?: boolean; thinkSeconds?: number }

export default function AppBuilderPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [app, setApp] = useState<AppDTO | null>(null);
  const [form, setForm] = useState<Partial<AppDTO>>({});
  const [saving, setSaving] = useState(false);
  const [models, setModels] = useState<{ id: string; name: string; model_id: string; max_tokens: number }[]>([]);

  // Sections open state
  const [openSections, setOpenSections] = useState({ basic: true, prompt: true, vars: false, tools: false, model: false });

  // Preview chat
  const [previewMsgs, setPreviewMsgs] = useState<ChatMsg[]>([]);
  const [previewInput, setPreviewInput] = useState('');
  const [previewLoading, setPreviewLoading] = useState(false);
  const [varValues, setVarValues] = useState<Record<string, string>>({});
  const [previewSessionId] = useState(`preview_${Date.now()}`);
  const [previewConfirm, setPreviewConfirm] = useState<{ tool_call_id: string; name: string; preview: string } | null>(null);
  const [leftCollapsed, setLeftCollapsed] = useState(false);
  const chatEndRef = useRef<HTMLDivElement>(null);
  const abortRef = useRef<AbortController | null>(null);
  const autoAllowRef = useRef<Set<string>>(new Set());

  useEffect(() => {
    if (id) loadApp(id);
    modelApi.list().then(d => setModels(
      (d.items ?? []).map(m => ({ id: m.id, name: m.name, model_id: m.model_id, max_tokens: m.max_tokens ?? 4096 }))
    )).catch(() => {});
  }, [id]);

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [previewMsgs]);

  // Init var values from form variables
  useEffect(() => {
    const vars = form.variables ?? [];
    setVarValues(prev => {
      const next = { ...prev };
      vars.forEach(v => { if (!(v.key in next)) next[v.key] = v.default ?? ''; });
      return next;
    });
  }, [form.variables]);

  async function loadApp(appId: string) {
    const data = await appApi.get(appId);
    setApp(data);
    setForm(data);
    if (data.opening_msg) {
      setPreviewMsgs([{ role: 'assistant', content: data.opening_msg }]);
    }
  }

  async function handleSave() {
    if (!id) return;
    setSaving(true);
    try {
      const updated = await appApi.update(id, {
        name: form.name,
        description: form.description,
        icon: form.icon,
        opening_msg: form.opening_msg,
        system_prompt: form.system_prompt,
        variables: form.variables,
        tools: form.tools,
        model: form.model,
        model_params: (form.model_params as Record<string, unknown>) ?? {},
      });
      setApp(updated);
      toast.success('已保存');
    } catch {
      toast.error('保存失败');
    } finally {
      setSaving(false);
    }
  }

  async function handlePublish() {
    if (!id) return;
    setSaving(true);
    try {
      await appApi.update(id, { ...form, is_published: true });
      toast.success('已发布！用户可以通过对话页使用此应用');
      navigate(`/apps/${id}/chat`);
    } catch {
      toast.error('发布失败');
    } finally {
      setSaving(false);
    }
  }

  const toggleTool = useCallback((name: string) => {
    setForm(prev => {
      const tools = prev.tools ?? [];
      return { ...prev, tools: tools.includes(name) ? tools.filter(t => t !== name) : [...tools, name] };
    });
  }, []);

  function addVariable() {
    const newVar: AppVariable = { key: `var_${Date.now()}`, label: '新变量', type: 'text', required: false, default: '' };
    setForm(prev => ({ ...prev, variables: [...(prev.variables ?? []), newVar] }));
    setOpenSections(s => ({ ...s, vars: true }));
  }

  function updateVar(idx: number, patch: Partial<AppVariable>) {
    setForm(prev => {
      const vars = [...(prev.variables ?? [])];
      vars[idx] = { ...vars[idx], ...patch };
      return { ...prev, variables: vars };
    });
  }

  function removeVar(idx: number) {
    setForm(prev => ({ ...prev, variables: (prev.variables ?? []).filter((_, i) => i !== idx) }));
  }

  const PREVIEW_API_BASE = (import.meta as unknown as { env?: Record<string, string> }).env?.VITE_API_BASE ?? 'http://localhost:8001';

  async function handlePreviewSend() {
    if (!previewInput.trim() || previewLoading || !id) return;
    const userMsg = previewInput.trim();
    setPreviewInput('');
    setPreviewMsgs(prev => [...prev, { role: 'user', content: userMsg }, { role: 'assistant', content: '', loading: true }]);
    setPreviewLoading(true);
    abortRef.current = new AbortController();

    const inlineEnabled = (form.model_params as Record<string, unknown>)?.enable_inline_images !== false;
    let thinkStartedAt: number | null = null;

    try {
      let content = '';
      for await (const event of streamPreviewChat(id, previewSessionId, userMsg, form, varValues, abortRef.current.signal)) {
        const e = event as Record<string, unknown>;
        if (e.type === 'content_replace') {
          content = (e.content as string) ?? '';
          setPreviewMsgs(prev => { const m = [...prev]; m[m.length - 1] = { role: 'assistant', content, loading: true }; return m; });
        } else if (e.type === 'delta') {
          const chunk = (e.content as string) ?? '';
          // Detect thinking start/end for duration tracking
          if ((chunk.includes('<thinking>') || chunk.includes('<think>')) && thinkStartedAt === null) {
            thinkStartedAt = Date.now();
          }
          content += chunk;
          setPreviewMsgs(prev => { const m = [...prev]; m[m.length - 1] = { role: 'assistant', content, loading: true }; return m; });
        } else if (e.type === 'tool_result') {
          const res = e.result as Record<string, unknown> | undefined;
          if (res && inlineEnabled && Array.isArray(res.file_urls)) {
            for (const f of res.file_urls as Array<{ url: string; name: string; type: string }>) {
              if (f.type === 'image') {
                content += `\n\n![${f.name}](${PREVIEW_API_BASE}${f.url})\n`;
              } else if (f.type === 'document') {
                content += `\n\n📄 [${f.name}](${PREVIEW_API_BASE}${f.url})\n`;
              }
            }
          }
          setPreviewMsgs(prev => { const m = [...prev]; m[m.length - 1] = { role: 'assistant', content, loading: true }; return m; });
        } else if (e.type === 'tool_confirm_request') {
          const toolName = e.name as string;
          const tcId = e.tool_call_id as string;
          if (autoAllowRef.current.has(toolName)) {
            const token = localStorage.getItem('auth_token');
            await fetch(`${PREVIEW_API_BASE}/api/chat/confirm/${tcId}`, {
              method: 'POST',
              headers: { 'Content-Type': 'application/json', ...(token ? { Authorization: `Bearer ${token}` } : {}) },
              body: JSON.stringify({ action: 'allow' }),
            });
          } else {
            setPreviewConfirm({ tool_call_id: tcId, name: toolName, preview: e.preview as string });
          }
        } else if (e.type === 'done') {
          const thinkSeconds = thinkStartedAt ? Math.round((Date.now() - thinkStartedAt) / 1000) : undefined;
          setPreviewMsgs(prev => { const m = [...prev]; m[m.length - 1] = { role: 'assistant', content, thinkSeconds }; return m; });
        }
      }
    } catch {
      setPreviewMsgs(prev => {
        const msgs = [...prev];
        msgs[msgs.length - 1] = { role: 'assistant', content: '⚠️ 请求失败，请检查配置后重试' };
        return msgs;
      });
    } finally {
      setPreviewLoading(false);
    }
  }

  async function handleConfirmDecision(action: string, allowAll = false) {
    if (!previewConfirm) return;
    const token = localStorage.getItem('auth_token');
    await fetch(`${PREVIEW_API_BASE}/api/chat/confirm/${previewConfirm.tool_call_id}`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
      body: JSON.stringify({ action }),
    });
    if (allowAll) autoAllowRef.current.add(previewConfirm.name);
    setPreviewConfirm(null);
  }

  function Section({ id: sid, title, children, badge }: { id: keyof typeof openSections; title: string; children: React.ReactNode; badge?: string }) {
    const open = openSections[sid];
    return (
      <div className="border-b border-gray-100 last:border-0">
        <button
          className="w-full flex items-center justify-between px-5 py-3 text-sm font-medium text-gray-700 hover:bg-gray-50"
          onClick={() => setOpenSections(s => ({ ...s, [sid]: !s[sid] }))}
        >
          <span className="flex items-center gap-2">
            {title}
            {badge && <span className="text-xs bg-purple-100 text-purple-600 px-1.5 py-0.5 rounded-full">{badge}</span>}
          </span>
          {open ? <ChevronDown size={15} /> : <ChevronRight size={15} />}
        </button>
        {open && <div className="px-5 pb-4">{children}</div>}
      </div>
    );
  }

  if (!app) return <div className="flex items-center justify-center h-full text-gray-400">加载中...</div>;

  return (
    <div className="flex h-full bg-white overflow-hidden">
      {/* ── Left: Config panel ───────────────────────────────────── */}
      <div className={`${leftCollapsed ? 'w-10' : 'w-72'} border-r border-gray-200 flex flex-col shrink-0 transition-all duration-200 overflow-hidden`}>
        {/* Header */}
        {leftCollapsed ? (
          <div className="flex flex-col items-center py-3 gap-3">
            <button onClick={() => setLeftCollapsed(false)} className="p-1.5 text-gray-500 hover:text-gray-800 hover:bg-gray-100 rounded" title="展开配置面板">
              <Maximize2 size={16} />
            </button>
          </div>
        ) : (
          <div className="flex items-center gap-2 px-4 py-3 border-b border-gray-200">
            <button onClick={() => navigate('/apps')} className="text-gray-500 hover:text-gray-800">
              <ArrowLeft size={18} />
            </button>
            <span className="text-sm font-semibold text-gray-800 flex-1 truncate">{form.name || '未命名'}</span>
            <button onClick={() => setLeftCollapsed(true)} className="p-1.5 text-gray-400 hover:text-gray-700 hover:bg-gray-100 rounded" title="折叠配置面板">
              <Minimize2 size={14} />
            </button>
            <button onClick={handleSave} disabled={saving} className="p-1.5 text-gray-500 hover:text-gray-800 hover:bg-gray-100 rounded" title="保存">
              <Save size={15} />
            </button>
            <button
              onClick={handlePublish} disabled={saving}
              className="flex items-center gap-1 px-3 py-1.5 bg-purple-600 text-white rounded-lg text-xs font-medium hover:bg-purple-700"
            >
              <Rocket size={13} /> 发布
            </button>
          </div>
        )}

        {/* Scrollable config sections */}
        <div className={`flex-1 overflow-y-auto ${leftCollapsed ? 'hidden' : ''}`}>
          {/* Basic info */}
          <Section id="basic" title="基本信息">
            <div className="space-y-3">
              <div className="flex gap-2">
                <input
                  value={form.icon ?? '🤖'}
                  onChange={e => setForm(p => ({ ...p, icon: e.target.value }))}
                  className="w-12 text-xl text-center border border-gray-200 rounded-lg py-1"
                  placeholder="🤖"
                />
                <input
                  value={form.name ?? ''}
                  onChange={e => setForm(p => ({ ...p, name: e.target.value }))}
                  placeholder="应用名称"
                  className="flex-1 border border-gray-200 rounded-lg px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-purple-300"
                />
              </div>
              <textarea
                value={form.description ?? ''}
                onChange={e => setForm(p => ({ ...p, description: e.target.value }))}
                placeholder="一句话描述这个应用的用途"
                rows={2}
                className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm resize-none focus:outline-none focus:ring-2 focus:ring-purple-300"
              />
              <input
                value={form.opening_msg ?? ''}
                onChange={e => setForm(p => ({ ...p, opening_msg: e.target.value }))}
                placeholder="欢迎语（用户打开应用时的第一条消息）"
                className="w-full border border-gray-200 rounded-lg px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-purple-300"
              />
            </div>
          </Section>

          {/* System Prompt */}
          <Section id="prompt" title="系统提示词">
            <div className="space-y-2">
              <p className="text-xs text-gray-400">定义 AI 的角色和行为。支持 <code className="bg-gray-100 px-1 rounded">{'{{变量名}}'}</code> 占位符</p>
              <textarea
                value={form.system_prompt ?? ''}
                onChange={e => setForm(p => ({ ...p, system_prompt: e.target.value }))}
                placeholder="你是一个专业的AI助手..."
                rows={8}
                className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm font-mono resize-none focus:outline-none focus:ring-2 focus:ring-purple-300"
              />
            </div>
          </Section>

          {/* Variables */}
          <Section id="vars" title="开场变量" badge={String((form.variables ?? []).length || '')}>
            <div className="space-y-2">
              {(form.variables ?? []).map((v, idx) => (
                <div key={idx} className="border border-gray-100 rounded-lg p-3 space-y-2 bg-gray-50">
                  <div className="flex gap-2">
                    <input
                      value={v.key}
                      onChange={e => updateVar(idx, { key: e.target.value })}
                      placeholder="变量名 (英文)"
                      className="flex-1 border border-gray-200 rounded px-2 py-1 text-xs font-mono bg-white"
                    />
                    <button onClick={() => removeVar(idx)} className="text-red-400 hover:text-red-600"><X size={14} /></button>
                  </div>
                  <input
                    value={v.label}
                    onChange={e => updateVar(idx, { label: e.target.value })}
                    placeholder="展示名称"
                    className="w-full border border-gray-200 rounded px-2 py-1 text-xs bg-white"
                  />
                  <div className="flex gap-2">
                    <select
                      value={v.type}
                      onChange={e => updateVar(idx, { type: e.target.value as AppVariable['type'] })}
                      className="flex-1 border border-gray-200 rounded px-2 py-1 text-xs bg-white"
                    >
                      <option value="text">单行文本</option>
                      <option value="textarea">多行文本</option>
                      <option value="select">下拉选择</option>
                    </select>
                    <label className="flex items-center gap-1 text-xs text-gray-500">
                      <input type="checkbox" checked={v.required} onChange={e => updateVar(idx, { required: e.target.checked })} />
                      必填
                    </label>
                  </div>
                  <input
                    value={v.default}
                    onChange={e => updateVar(idx, { default: e.target.value })}
                    placeholder="默认值"
                    className="w-full border border-gray-200 rounded px-2 py-1 text-xs bg-white"
                  />
                </div>
              ))}
              <button onClick={addVariable} className="w-full flex items-center justify-center gap-1.5 py-2 border border-dashed border-gray-300 rounded-lg text-xs text-gray-500 hover:border-purple-400 hover:text-purple-500">
                <Plus size={13} /> 添加变量
              </button>
            </div>
          </Section>

          {/* Tools */}
          <Section id="tools" title="启用工具" badge={String((form.tools ?? []).length || '')}>
            {/* Select all / none */}
            <div className="flex items-center justify-between mb-2">
              <span className="text-xs text-gray-400">{(form.tools ?? []).length} / {ALL_BUILTIN_TOOLS.length} 已选</span>
              <div className="flex gap-1.5">
                <button
                  onClick={() => setForm(p => ({ ...p, tools: ALL_BUILTIN_TOOLS.map(t => t.name) }))}
                  className="px-2 py-0.5 text-[11px] rounded border border-purple-200 text-purple-600 hover:bg-purple-50"
                >全选</button>
                <button
                  onClick={() => setForm(p => ({ ...p, tools: [] }))}
                  className="px-2 py-0.5 text-[11px] rounded border border-gray-200 text-gray-500 hover:bg-gray-50"
                >清空</button>
              </div>
            </div>
            <div className="space-y-1.5">
              {ALL_BUILTIN_TOOLS.map(tool => (
                <label key={tool.name} className="flex items-center gap-3 p-2 rounded-lg hover:bg-gray-50 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={(form.tools ?? []).includes(tool.name)}
                    onChange={() => toggleTool(tool.name)}
                    className="accent-purple-600"
                  />
                  <div>
                    <div className="text-sm font-medium text-gray-700">{tool.label}</div>
                    <div className="text-xs text-gray-400">{tool.desc}</div>
                  </div>
                </label>
              ))}
            </div>
          </Section>

          {/* Model */}
          <Section id="model" title="模型">
            <select
              value={form.model ?? ''}
              onChange={e => {
                const selected = models.find(m => m.model_id === e.target.value);
                setForm(p => ({
                  ...p,
                  model: e.target.value,
                  model_params: {
                    ...(p.model_params as object || {}),
                    ...(selected ? { max_tokens: selected.max_tokens } : {}),
                  },
                }));
              }}
              className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-purple-300"
            >
              <option value="">系统默认</option>
              {models.map(m => <option key={m.id} value={m.model_id}>{m.name || m.model_id}</option>)}
            </select>

            {/* Model Parameters */}
            <div className="mt-3 space-y-3">
              {/* Temperature */}
              <div>
                <div className="flex justify-between items-center mb-1">
                  <label className="text-xs text-gray-500">Temperature（创造性）</label>
                  <span className="text-xs font-mono text-gray-700 w-8 text-right">
                    {((form.model_params as Record<string,unknown>)?.temperature ?? 0.7) as number}
                  </span>
                </div>
                <input
                  type="range" min="0" max="2" step="0.05"
                  value={Number((form.model_params as Record<string,unknown>)?.temperature ?? 0.7)}
                  onChange={e => setForm(p => ({ ...p, model_params: { ...(p.model_params as object || {}), temperature: parseFloat(e.target.value) } }))}
                  className="w-full accent-purple-500"
                />
                <div className="flex justify-between text-[10px] text-gray-300 mt-0.5">
                  <span>精确 0</span><span>均衡 0.7</span><span>创意 2</span>
                </div>
              </div>

              {/* Max Tokens */}
              <div>
                {(() => {
                  const selectedModel = models.find(m => m.model_id === form.model);
                  const modelMax = selectedModel?.max_tokens ?? 32000;
                  const current = Number((form.model_params as Record<string,unknown>)?.max_tokens ?? modelMax);
                  return (
                    <>
                      <div className="flex justify-between items-center mb-1">
                        <label className="text-xs text-gray-500">最大输出 Token 数</label>
                        <span className="text-xs font-mono text-gray-700">{current.toLocaleString()} / {modelMax.toLocaleString()}</span>
                      </div>
                      <input
                        type="range" min="256" max={modelMax} step="256"
                        value={current}
                        onChange={e => setForm(p => ({ ...p, model_params: { ...(p.model_params as object || {}), max_tokens: parseInt(e.target.value) || 256 } }))}
                        className="w-full accent-purple-500"
                      />
                      <div className="flex justify-between text-[10px] text-gray-300 mt-0.5">
                        <span>256</span><span>{Math.round(modelMax / 2).toLocaleString()}</span><span>{modelMax.toLocaleString()}</span>
                      </div>
                    </>
                  );
                })()}
              </div>

              {/* Enable Thinking */}
              <div className="flex items-center justify-between py-1">
                <div>
                  <span className="text-xs text-gray-500">启用思考过程</span>
                  <p className="text-[10px] text-gray-400 mt-0.5">
                    显示模型推理链（需模型支持，推荐 claude-opus-4-6）
                  </p>
                </div>
                <button
                  type="button"
                  onClick={() => setForm(p => ({
                    ...p,
                    model_params: {
                      ...(p.model_params as object || {}),
                      enable_thinking: !((p.model_params as Record<string,unknown>)?.enable_thinking ?? false),
                    },
                  }))}
                  className={`relative inline-flex h-5 w-9 shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors duration-200 focus:outline-none ${
                    (form.model_params as Record<string,unknown>)?.enable_thinking
                      ? 'bg-purple-500'
                      : 'bg-gray-200'
                  }`}
                >
                  <span
                    className={`inline-block h-4 w-4 transform rounded-full bg-white shadow transition duration-200 ${
                      (form.model_params as Record<string,unknown>)?.enable_thinking
                        ? 'translate-x-4'
                        : 'translate-x-0'
                    }`}
                  />
                </button>
              </div>

              {/* Enable Inline Images */}
              <div className="flex items-center justify-between py-1">
                <div>
                  <span className="text-xs text-gray-500">图片内联展示</span>
                  <p className="text-[10px] text-gray-400 mt-0.5">
                    工具生成的图片直接显示在回复气泡中
                  </p>
                </div>
                <button
                  type="button"
                  onClick={() => setForm(p => ({
                    ...p,
                    model_params: {
                      ...(p.model_params as object || {}),
                      enable_inline_images: !((p.model_params as Record<string,unknown>)?.enable_inline_images ?? true),
                    },
                  }))}
                  className={`relative inline-flex h-5 w-9 shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors duration-200 focus:outline-none ${
                    (form.model_params as Record<string,unknown>)?.enable_inline_images !== false
                      ? 'bg-purple-500'
                      : 'bg-gray-200'
                  }`}
                >
                  <span
                    className={`inline-block h-4 w-4 transform rounded-full bg-white shadow transition duration-200 ${
                      (form.model_params as Record<string,unknown>)?.enable_inline_images !== false
                        ? 'translate-x-4'
                        : 'translate-x-0'
                    }`}
                  />
                </button>
              </div>

              {/* Enable Sandbox HTML */}
              <div className="flex items-center justify-between py-1">
                <div>
                  <span className="text-xs text-gray-500">HTML 沙箱渲染</span>
                  <p className="text-[10px] text-gray-400 mt-0.5">
                    将 HTML 代码块渲染为可交互应用（ECharts / D3 等）
                  </p>
                </div>
                <button
                  type="button"
                  onClick={() => setForm(p => ({
                    ...p,
                    model_params: {
                      ...(p.model_params as object || {}),
                      enable_sandbox_html: !((p.model_params as Record<string,unknown>)?.enable_sandbox_html ?? false),
                    },
                  }))}
                  className={`relative inline-flex h-5 w-9 shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors duration-200 focus:outline-none ${
                    (form.model_params as Record<string,unknown>)?.enable_sandbox_html
                      ? 'bg-purple-500'
                      : 'bg-gray-200'
                  }`}
                >
                  <span
                    className={`inline-block h-4 w-4 transform rounded-full bg-white shadow transition duration-200 ${
                      (form.model_params as Record<string,unknown>)?.enable_sandbox_html
                        ? 'translate-x-4'
                        : 'translate-x-0'
                    }`}
                  />
                </button>
              </div>
            </div>
          </Section>
        </div>
      </div>

      {/* ── Right: Preview chat ──────────────────────────────────── */}
      <div className="flex-1 flex flex-col bg-gray-50 min-w-0">
        {/* Preview header */}
        <div className="bg-white border-b border-gray-200 px-6 py-3 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <span className="text-lg">{form.icon ?? '🤖'}</span>
            <span className="font-semibold text-gray-800 text-sm">{form.name || '未命名'}</span>
            <span className="text-xs bg-blue-50 text-blue-500 px-2 py-0.5 rounded-full">调试预览</span>
          </div>
          <button
            onClick={() => {
              setPreviewMsgs(form.opening_msg ? [{ role: 'assistant', content: form.opening_msg }] : []);
            }}
            className="text-xs text-gray-400 hover:text-gray-700"
          >
            清空对话
          </button>
        </div>

        {/* Variable fill area (shown when vars exist) */}
        {(form.variables ?? []).length > 0 && (
          <div className="bg-white border-b border-gray-100 px-6 py-3 flex gap-4 flex-wrap">
            {(form.variables ?? []).map(v => (
              <div key={v.key} className="flex items-center gap-2">
                <label className="text-xs text-gray-500">{v.label}</label>
                {v.type === 'select' ? (
                  <select
                    value={varValues[v.key] ?? v.default}
                    onChange={e => setVarValues(prev => ({ ...prev, [v.key]: e.target.value }))}
                    className="border border-gray-200 rounded px-2 py-1 text-xs"
                  >
                    {(v.options ?? []).map(o => <option key={o}>{o}</option>)}
                  </select>
                ) : (
                  <input
                    value={varValues[v.key] ?? v.default}
                    onChange={e => setVarValues(prev => ({ ...prev, [v.key]: e.target.value }))}
                    className="border border-gray-200 rounded px-2 py-1 text-xs w-28"
                    placeholder={v.default || v.label}
                  />
                )}
              </div>
            ))}
          </div>
        )}

        {/* Messages */}
        <div className="flex-1 overflow-y-auto px-6 py-4 space-y-4">
          {previewMsgs.length === 0 && (
            <div className="flex items-center justify-center h-32 text-gray-400 text-sm">
              在左侧配置好参数后，直接在下方输入框发消息预览效果
            </div>
          )}
          {previewMsgs.map((msg, i) => (
            <div key={i} className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
              <PreviewBubble key={i} msg={msg} enableSandboxHtml={!!(form.model_params as Record<string,unknown>)?.enable_sandbox_html} />
            </div>
          ))}
          <div ref={chatEndRef} />
        </div>

        {/* Input */}
        <div className="bg-white border-t border-gray-200 px-6 py-4">
          <div className="flex gap-3 items-end">
            <textarea
              value={previewInput}
              onChange={e => setPreviewInput(e.target.value)}
              onKeyDown={e => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); handlePreviewSend(); } }}
              placeholder="输入消息预览效果... (Enter 发送)"
              rows={2}
              className="flex-1 border border-gray-200 rounded-xl px-4 py-2.5 text-sm resize-none focus:outline-none focus:ring-2 focus:ring-purple-300"
            />
            <button
              onClick={handlePreviewSend}
              disabled={previewLoading || !previewInput.trim()}
              className="p-3 bg-purple-600 text-white rounded-xl hover:bg-purple-700 disabled:opacity-40"
            >
              {previewLoading ? <Loader2 size={18} className="animate-spin" /> : <Send size={18} />}
            </button>
          </div>
        </div>
      </div>

      {previewConfirm && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm">
          <div className="bg-white rounded-2xl shadow-2xl w-full max-w-lg mx-4 overflow-hidden">
            <div className={`px-6 py-4 flex items-center gap-3 ${
              ['bash', 'python_exec', 'multi_bash'].includes(previewConfirm.name)
                ? 'bg-orange-50 border-b border-orange-200'
                : 'bg-yellow-50 border-b border-yellow-200'
            }`}>
              <span className="text-2xl">
                {['bash', 'python_exec', 'multi_bash'].includes(previewConfirm.name) ? '⚠️' : '📝'}
              </span>
              <div>
                <div className="font-semibold text-gray-900">Agent 请求执行操作</div>
                <div className="text-sm text-gray-500">
                  工具：<span className="font-mono font-bold text-gray-800">{previewConfirm.name}</span>
                </div>
              </div>
            </div>
            <div className="px-6 py-4">
              <div className="text-xs text-gray-500 mb-2 font-medium">执行内容预览</div>
              <pre className="text-xs bg-gray-50 border border-gray-200 rounded-lg p-3 max-h-56 overflow-y-auto whitespace-pre-wrap font-mono leading-relaxed">
                {previewConfirm.preview}
              </pre>
            </div>
            <div className="px-6 pb-5 flex flex-col gap-2">
              <div className="flex gap-3">
                <button
                  onClick={() => handleConfirmDecision('allow')}
                  className="flex-1 py-2.5 bg-green-600 text-white font-medium rounded-xl hover:bg-green-700 transition-colors"
                >
                  ✓ 允许执行
                </button>
                <button
                  onClick={() => handleConfirmDecision('skip')}
                  className="px-5 py-2.5 bg-gray-100 text-gray-700 font-medium rounded-xl hover:bg-gray-200 transition-colors"
                >
                  跳过
                </button>
                <button
                  onClick={() => handleConfirmDecision('cancel')}
                  className="px-5 py-2.5 bg-red-50 text-red-600 font-medium rounded-xl hover:bg-red-100 transition-colors"
                >
                  ✕ 取消
                </button>
              </div>
              <button
                onClick={() => handleConfirmDecision('allow', true)}
                className="w-full py-2 bg-blue-50 text-blue-600 text-sm font-medium rounded-xl hover:bg-blue-100 transition-colors"
              >
                ⚡ 全部允许同类（{previewConfirm.name}）
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

const SANDBOX_COLLAPSED_H = 400;

function SandboxApp({ html }: { html: string }) {
  const iframeRef = useRef<HTMLIFrameElement>(null);
  const [autoHeight, setAutoHeight] = useState(0);
  const [collapsed, setCollapsed] = useState(false);

  const handleLoad = () => {
    try {
      const h = iframeRef.current?.contentDocument?.body?.scrollHeight ?? 0;
      if (h > 0) setAutoHeight(h + 24);
    } catch {
      // cross-origin guard
    }
  };

  const fullHeight = autoHeight || 480;
  const iframeHeight = collapsed ? SANDBOX_COLLAPSED_H : fullHeight;
  const canCollapse = fullHeight > SANDBOX_COLLAPSED_H;

  return (
    <div className="my-2 rounded-xl border border-purple-100 overflow-hidden shadow-sm">
      <div className="flex items-center justify-between px-3 py-1.5 bg-purple-50 border-b border-purple-100">
        <div className="flex items-center gap-1.5 text-[10px] text-purple-500">
          <span>⚡</span><span>交互式应用</span>
          {autoHeight > 0 && <span className="text-purple-300">({autoHeight}px)</span>}
        </div>
        {canCollapse && (
          <button
            onClick={() => setCollapsed(v => !v)}
            className="p-0.5 rounded hover:bg-purple-100 text-purple-400 hover:text-purple-600 transition-colors"
            title={collapsed ? '展开全高' : '收起'}
          >
            {collapsed ? <Maximize2 size={12} /> : <Minimize2 size={12} />}
          </button>
        )}
      </div>
      <iframe
        ref={iframeRef}
        srcDoc={html}
        sandbox="allow-scripts allow-same-origin"
        className="w-full bg-white"
        style={{ height: iframeHeight, border: 'none', display: 'block', overflow: collapsed ? 'auto' : 'hidden' }}
        title="Generated App"
        onLoad={handleLoad}
      />
      {collapsed && canCollapse && (
        <button
          onClick={() => setCollapsed(false)}
          className="w-full py-1 text-[11px] text-purple-400 hover:text-purple-600 hover:bg-purple-50 transition-colors border-t border-purple-100"
        >
          ↓ 展开全部 ({fullHeight}px)
        </button>
      )}
    </div>
  );
}

function ThinkingBlock({ thinking, loading, thinkSeconds }: { thinking: string; loading?: boolean; thinkSeconds?: number }) {
  const [open, setOpen] = useState(false);
  const isStreaming = loading && !thinkSeconds;
  const wordCount = thinking.length;

  return (
    <div className="mb-3">
      {/* Header row */}
      <button
        onClick={() => setOpen(v => !v)}
        className="flex items-center gap-1.5 group w-full text-left"
      >
        <div className={`flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg border transition-colors ${
          isStreaming
            ? 'bg-violet-50 border-violet-200 text-violet-600'
            : 'bg-gray-50 border-gray-200 text-gray-500 hover:bg-gray-100'
        }`}>
          {isStreaming ? (
            <>
              <span className="text-[10px]">●</span>
              <span className="text-xs font-medium">正在思考</span>
              <span className="flex gap-0.5 items-end h-3">
                {[0,1,2].map(i => (
                  <span key={i} className="w-0.5 bg-violet-400 rounded-full animate-bounce"
                    style={{ height: `${6 + i * 2}px`, animationDelay: `${i * 0.15}s`, animationDuration: '0.8s' }} />
                ))}
              </span>
            </>
          ) : (
            <>
              <Brain size={11} />
              <span className="text-xs font-medium">
                {thinkSeconds ? `已思考 ${thinkSeconds}s` : '思考过程'}
              </span>
              <span className="text-[10px] text-gray-400 ml-0.5">· {wordCount > 999 ? `${(wordCount/1000).toFixed(1)}k` : wordCount} 字</span>
              {open ? <ChevronDown size={10} className="ml-0.5" /> : <ChevronRight size={10} className="ml-0.5" />}
            </>
          )}
        </div>
      </button>

      {/* Content */}
      {open && thinking && (
        <div className="mt-2 px-3 py-2.5 bg-gray-50 border border-gray-200 rounded-lg text-xs text-gray-500 max-h-56 overflow-y-auto leading-relaxed">
          <ReactMarkdown remarkPlugins={[remarkGfm]}>{thinking}</ReactMarkdown>
        </div>
      )}
    </div>
  );
}

function PreviewBubble({ msg, enableSandboxHtml }: { msg: ChatMsg; enableSandboxHtml?: boolean }) {
  const isUser = msg.role === 'user';
  const { thinking, answer } = useMemo(
    () => (!isUser ? parseThink(msg.content) : { thinking: '', answer: msg.content }),
    [msg.content, isUser],
  );
  const isThinking = !!thinking && msg.loading && !answer;

  return (
    <div className={`max-w-[85%] rounded-2xl px-4 py-2.5 text-sm leading-relaxed ${
      isUser
        ? 'bg-purple-600 text-white rounded-br-sm'
        : 'bg-white border border-gray-200 text-gray-800 rounded-bl-sm'
    }`}>
      {!isUser && (thinking || isThinking) && (
        <ThinkingBlock thinking={thinking} loading={msg.loading} thinkSeconds={msg.thinkSeconds} />
      )}
      {isUser ? (
        <span className="whitespace-pre-wrap">{msg.content}</span>
      ) : answer ? (
        <div className="prose prose-sm max-w-none prose-p:my-0.5">
          <ReactMarkdown
            remarkPlugins={[remarkGfm]}
            components={{
              code({ className, children, ...props }) {
                const lang = (className ?? '').replace('language-', '');
                const code = String(children).replace(/\n$/, '');
                if (lang && isDiagramLang(lang)) {
                  return <DiagramBlock lang={lang} code={code} />;
                }
                if (lang === 'html' && enableSandboxHtml) {
                  return <SandboxApp html={code} />;
                }
                return <code className={className} {...props}>{children}</code>;
              },
              img({ src, alt }) {
                return <LazyImage src={src ?? ''} alt={alt ?? ''} />;
              },
            }}
          >{answer}</ReactMarkdown>
        </div>
      ) : msg.loading && !thinking ? (
        <Loader2 size={15} className="animate-spin text-gray-400" />
      ) : null}
    </div>
  );
}
