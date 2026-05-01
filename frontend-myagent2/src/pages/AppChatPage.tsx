import { useState, useEffect, useRef, useMemo } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { ArrowLeft, Send, Loader2, Plus, History, Wrench, ChevronDown, ChevronRight, Settings, Maximize2, Minimize2 } from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { appApi, streamAppChat, type AppDTO, type AppMessage, type AppSession } from '@/api/apps';
import { ThinkingBlock } from '@/components/ThinkingBlock';
import { DiagramBlock, isDiagramLang } from '@/components/DiagramBlock';
import { LazyImage } from '@/components/LazyImage';

function parseThink(raw: string): { thinking: string; answer: string } {
  // Handle both <thinking> (Claude) and <think> (Qwen3) tags
  for (const tag of ['thinking', 'think']) {
    const open = `<${tag}>`, close = `</${tag}>`;
    const startM = raw.match(new RegExp(`^${open}([\\s\\S]*?)(${close}|$)`));
    if (startM) return { thinking: startM[1].trim(), answer: raw.slice(startM[0].length).trim() };
    const anyM = raw.match(new RegExp(`^([\\s\\S]*?)${open}([\\s\\S]*?)${close}([\\s\\S]*)$`));
    if (anyM) return { thinking: anyM[2].trim(), answer: (anyM[1] + anyM[3]).trim() };
  }
  return { thinking: '', answer: raw };
}

interface FileUrl {
  url: string;
  name: string;
  type: 'image' | 'document' | 'file';
}

interface ToolCall {
  name: string;
  status: 'running' | 'done';
  output?: string;
  fileUrls?: FileUrl[];
}

interface ToolConfirmRequest {
  tool_call_id: string;
  name: string;
  preview: string;
}

interface ChatMsg {
  id?: string;
  role: 'user' | 'assistant';
  content: string;
  thinkingContent?: string;
  loading?: boolean;
  thinkSeconds?: number;
  toolCalls?: ToolCall[];
  pendingConfirm?: ToolConfirmRequest | null;
}

const API_BASE = (import.meta as unknown as { env?: Record<string, string> }).env?.VITE_API_BASE ?? 'http://localhost:8001';

const SANDBOX_COLLAPSED_H = 400;

function SandboxApp({ html }: { html: string }) {
  const iframeRef = useRef<HTMLIFrameElement>(null);
  const [autoHeight, setAutoHeight] = useState(0);
  const [collapsed, setCollapsed] = useState(false);

  const handleLoad = () => {
    try {
      const h = iframeRef.current?.contentDocument?.body?.scrollHeight ?? 0;
      if (h > 0) setAutoHeight(h + 24);
    } catch { /* cross-origin guard */ }
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

function ConfirmModal({
  req,
  onDecision,
  onAllowAll,
}: {
  req: ToolConfirmRequest;
  onDecision: (action: string) => void;
  onAllowAll?: () => void;
}) {
  const [busy, setBusy] = useState(false);

  const decide = async (action: 'allow' | 'skip' | 'cancel', allowAll = false) => {
    setBusy(true);
    const token = localStorage.getItem('auth_token');
    await fetch(`${API_BASE}/api/chat/confirm/${req.tool_call_id}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', ...(token ? { Authorization: `Bearer ${token}` } : {}) },
      body: JSON.stringify({ action }),
    });
    if (allowAll && onAllowAll) onAllowAll();
    onDecision(action);
    setBusy(false);
  };

  const isHigh = ['bash', 'python_exec', 'multi_bash'].includes(req.name);

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm">
      <div className="bg-white rounded-2xl shadow-2xl w-full max-w-lg mx-4 overflow-hidden">
        {/* Header */}
        <div className={`px-6 py-4 flex items-center gap-3 ${
          isHigh ? 'bg-orange-50 border-b border-orange-200' : 'bg-yellow-50 border-b border-yellow-200'
        }`}>
          <span className="text-2xl">{isHigh ? '⚠️' : '📝'}</span>
          <div>
            <div className="font-semibold text-gray-900">Agent 请求执行操作</div>
            <div className="text-sm text-gray-500">工具：<span className="font-mono font-bold text-gray-800">{req.name}</span></div>
          </div>
        </div>
        {/* Preview */}
        <div className="px-6 py-4">
          <div className="text-xs text-gray-500 mb-2 font-medium">执行内容预览</div>
          <pre className="text-xs bg-gray-50 border border-gray-200 rounded-lg p-3 max-h-56 overflow-y-auto whitespace-pre-wrap font-mono leading-relaxed">
            {req.preview}
          </pre>
        </div>
        {/* Actions */}
        <div className="px-6 pb-5 flex flex-col gap-2">
          <div className="flex gap-3">
            <button
              onClick={() => decide('allow')}
              disabled={busy}
              className="flex-1 py-2.5 bg-green-600 text-white font-medium rounded-xl hover:bg-green-700 disabled:opacity-50 transition-colors"
            >
              ✓ 允许执行
            </button>
            <button
              onClick={() => decide('skip')}
              disabled={busy}
              className="px-5 py-2.5 bg-gray-100 text-gray-700 font-medium rounded-xl hover:bg-gray-200 disabled:opacity-50 transition-colors"
            >
              跳过
            </button>
            <button
              onClick={() => decide('cancel')}
              disabled={busy}
              className="px-5 py-2.5 bg-red-50 text-red-600 font-medium rounded-xl hover:bg-red-100 disabled:opacity-50 transition-colors"
            >
              ✕ 取消
            </button>
          </div>
          <button
            onClick={() => decide('allow', true)}
            disabled={busy}
            className="w-full py-2 bg-blue-50 text-blue-600 text-sm font-medium rounded-xl hover:bg-blue-100 disabled:opacity-50 transition-colors"
          >
            ⚡ 全部允许同类（{req.name}）
          </button>
        </div>
      </div>
    </div>
  );
}

function ToolBlock({ tc }: { tc: ToolCall }) {
  const hasContent = !!(tc.output || (tc.fileUrls && tc.fileUrls.length > 0));
  const [open, setOpen] = useState(false);
  useEffect(() => {
    if (tc.status === 'done' && hasContent) setOpen(true);
  }, [tc.status, hasContent]);
  return (
    <div className={`rounded-xl border text-xs overflow-hidden ${
      tc.status === 'running'
        ? 'border-yellow-200 bg-yellow-50'
        : 'border-gray-200 bg-gray-50'
    }`}>
      <button
        onClick={() => hasContent && setOpen(v => !v)}
        className="w-full flex items-center gap-2 px-3 py-1.5 text-left"
        disabled={!hasContent}
      >
        {tc.status === 'running'
          ? <Loader2 size={11} className="animate-spin text-yellow-500 shrink-0" />
          : <Wrench size={11} className="text-green-500 shrink-0" />}
        <span className={tc.status === 'running' ? 'text-yellow-700' : 'text-gray-600'}>
          {tc.name} {tc.status === 'running' ? '执行中⋯' : '✓'}
          {tc.fileUrls && tc.fileUrls.length > 0 && (
            <span className="ml-1 text-blue-500">· {tc.fileUrls.length} 个文件</span>
          )}
        </span>
        {hasContent && (open
          ? <ChevronDown size={11} className="ml-auto text-gray-400" />
          : <ChevronRight size={11} className="ml-auto text-gray-400" />)}
      </button>
      {open && (
        <div className="border-t border-gray-200 bg-white">
          {tc.output && (
            <div className="px-3 py-2 font-mono text-[11px] text-gray-600 max-h-48 overflow-y-auto whitespace-pre-wrap">
              {tc.output}
            </div>
          )}
          {tc.fileUrls && tc.fileUrls.length > 0 && (
            <div className="px-3 py-2 space-y-2">
              {tc.fileUrls.map((f, i) => (
                f.type === 'image' ? (
                  <img
                    key={i}
                    src={API_BASE + f.url}
                    alt={f.name}
                    className="max-w-full rounded border border-gray-200 block"
                    loading="lazy"
                  />
                ) : (
                  <a
                    key={i}
                    href={API_BASE + f.url}
                    target="_blank"
                    rel="noreferrer"
                    className="flex items-center gap-1 text-blue-600 hover:underline text-[11px]"
                  >
                    📄 {f.name}
                  </a>
                )
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

export default function AppChatPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();

  const [app, setApp] = useState<AppDTO | null>(null);
  const [sessions, setSessions] = useState<AppSession[]>([]);
  const [currentSession, setCurrentSession] = useState<string | null>(null);
  const [msgs, setMsgs] = useState<ChatMsg[]>([]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [varValues, setVarValues] = useState<Record<string, string>>({});
  const [varsSubmitted, setVarsSubmitted] = useState(false);
  const [showHistory, setShowHistory] = useState(false);

  const chatEndRef = useRef<HTMLDivElement>(null);
  const abortRef = useRef<AbortController | null>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const autoAllowRef = useRef<Set<string>>(new Set());

  // 从消息列表中提取当前挂起的确认请求
  const activePendingConfirm = useMemo(
    () => msgs.find(m => m.pendingConfirm)?.pendingConfirm ?? null,
    [msgs]
  );

  useEffect(() => {
    if (id) loadApp(id);
  }, [id]);

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [msgs]);

  async function loadApp(appId: string) {
    const data = await appApi.get(appId);
    setApp(data);
    // init var defaults
    const defaults: Record<string, string> = {};
    (data.variables ?? []).forEach(v => { defaults[v.key] = v.default ?? ''; });
    setVarValues(defaults);
    // load sessions first to decide whether to restore or create
    const sessData = await appApi.listSessions(appId);
    setSessions(sessData.items);
    // if no variables, skip var screen
    if ((data.variables ?? []).length === 0) {
      setVarsSubmitted(true);
      if (sessData.items.length > 0) {
        // restore most recent session
        const latest = sessData.items[0];
        setCurrentSession(latest.id);
        const msgData = await appApi.getMessages(appId, latest.id);
        const converted: ChatMsg[] = msgData.items.map((m: AppMessage) => ({
          id: m.id,
          role: m.role === 'user' ? 'user' : 'assistant',
          content: m.content,
          thinkingContent: (m as unknown as Record<string, string>).thinking_content ?? undefined,
        }));
        setMsgs(converted.length > 0 ? converted : (data.opening_msg ? [{ role: 'assistant', content: data.opening_msg }] : []));
      } else {
        await startNewSession(appId, data, {});
      }
    }
  }

  async function startNewSession(appId: string, appData: AppDTO, vars: Record<string, string>) {
    const sess = await appApi.createSession(appId);
    setCurrentSession(sess.id);
    setSessions(prev => [sess, ...prev]);
    setMsgs(appData.opening_msg ? [{ role: 'assistant', content: appData.opening_msg }] : []);
    setVarValues(vars);
  }

  async function handleVarsSubmit() {
    if (!id || !app) return;
    setVarsSubmitted(true);
    await startNewSession(id, app, varValues);
  }

  async function handleNewChat() {
    if (!id || !app) return;
    setVarsSubmitted((app.variables ?? []).length === 0);
    if ((app.variables ?? []).length === 0) {
      await startNewSession(id, app, varValues);
    } else {
      // reset to var screen
      const defaults: Record<string, string> = {};
      (app.variables ?? []).forEach(v => { defaults[v.key] = v.default ?? ''; });
      setVarValues(defaults);
      setMsgs([]);
      setCurrentSession(null);
      setVarsSubmitted(false);
    }
    setShowHistory(false);
  }

  async function handleLoadSession(sessId: string) {
    if (!id) return;
    setCurrentSession(sessId);
    setVarsSubmitted(true);
    setShowHistory(false);
    const data = await appApi.getMessages(id, sessId);
    const converted: ChatMsg[] = data.items.map((m: AppMessage) => ({
      id: m.id,
      role: m.role === 'user' ? 'user' : 'assistant',
      content: m.content,
      thinkingContent: (m as unknown as Record<string, string>).thinking_content ?? undefined,
    }));
    setMsgs(converted.length > 0 ? converted : (app?.opening_msg ? [{ role: 'assistant', content: app.opening_msg }] : []));
  }

  async function handleSend() {
    if (!input.trim() || loading || !currentSession || !id) return;
    const userMsg = input.trim();
    setInput('');
    setMsgs(prev => [
      ...prev,
      { role: 'user', content: userMsg },
      { role: 'assistant', content: '', loading: true },
    ]);
    setLoading(true);
    abortRef.current = new AbortController();

    try {
      let content = '';
      let thinkStartedAt: number | null = null;
      const toolCallMap: Record<string, ToolCall> = {};

      for await (const event of streamAppChat(id, currentSession, userMsg, varValues, abortRef.current.signal)) {
        const e = event as Record<string, unknown>;

        if (e.type === 'content_replace') {
          content = (e.content as string) ?? '';
          setMsgs(prev => {
            const msgs = [...prev];
            msgs[msgs.length - 1] = { role: 'assistant', content, loading: true };
            return msgs;
          });
        } else if (e.type === 'delta') {
          const chunk = (e.content as string) ?? '';
          if ((chunk.includes('<thinking>') || chunk.includes('<think>')) && thinkStartedAt === null) {
            thinkStartedAt = Date.now();
          }
          content += chunk;
          setMsgs(prev => {
            const msgs = [...prev];
            msgs[msgs.length - 1] = { role: 'assistant', content, loading: true };
            return msgs;
          });
        } else if (e.type === 'tool_start') {
          const name = (e.name as string) ?? 'tool';
          toolCallMap[name] = { name, status: 'running' };
          setMsgs(prev => {
            const msgs = [...prev];
            msgs[msgs.length - 1] = { role: 'assistant', content, loading: true, toolCalls: Object.values(toolCallMap) };
            return msgs;
          });
        } else if (e.type === 'tool_result') {
          const name = (e.name as string) ?? 'tool';
          if (toolCallMap[name]) {
            toolCallMap[name].status = 'done';
            const res = e.result as Record<string, unknown> | undefined;
            if (res) {
              const out = res.output ?? res.stdout ?? res.result ?? res.content ?? res.error;
              toolCallMap[name].output = out != null ? String(out).slice(0, 2000) : undefined;
              if (Array.isArray(res.file_urls)) {
                toolCallMap[name].fileUrls = res.file_urls as FileUrl[];
                // 开关开启时，图片/文档自动注入回复正文（Markdown 格式，MsgBubble LazyImage 渲染）
                const inlineEnabled = (app?.model_params as Record<string,unknown>)?.enable_inline_images !== false;
                if (inlineEnabled) {
                  for (const f of res.file_urls as FileUrl[]) {
                    if (f.type === 'image') {
                      content += `\n\n![${f.name}](${API_BASE}${f.url})\n`;
                    } else if (f.type === 'document') {
                      content += `\n\n📄 [${f.name}](${API_BASE}${f.url})\n`;
                    }
                  }
                }
              }
            }
          }
          setMsgs(prev => {
            const msgs = [...prev];
            msgs[msgs.length - 1] = { role: 'assistant', content, loading: true, toolCalls: Object.values(toolCallMap) };
            return msgs;
          });
        } else if (e.type === 'tool_confirm_request') {
          const toolName = e.name as string;
          const tcId = e.tool_call_id as string;
          if (autoAllowRef.current.has(toolName)) {
            const token = localStorage.getItem('auth_token');
            await fetch(`${API_BASE}/api/chat/confirm/${tcId}`, {
              method: 'POST',
              headers: { 'Content-Type': 'application/json', ...(token ? { Authorization: `Bearer ${token}` } : {}) },
              body: JSON.stringify({ action: 'allow' }),
            });
          } else {
            const confirmReq: ToolConfirmRequest = { tool_call_id: tcId, name: toolName, preview: e.preview as string };
            setMsgs(prev => {
              const msgs = [...prev];
              msgs[msgs.length - 1] = { ...msgs[msgs.length - 1], pendingConfirm: confirmReq };
              return msgs;
            });
          }
        } else if (e.type === 'error') {
          const errMsg = (e.message as string) ?? '模型调用失败';
          setMsgs(prev => {
            const msgs = [...prev];
            msgs[msgs.length - 1] = {
              role: 'assistant',
              content: `⚠️ ${errMsg}`,
              loading: false,
              toolCalls: Object.values(toolCallMap),
            };
            return msgs;
          });
          return;
        } else if (e.type === 'done') {
          const thinkSeconds = thinkStartedAt ? Math.round((Date.now() - thinkStartedAt) / 1000) : undefined;
          setMsgs(prev => {
            const msgs = [...prev];
            msgs[msgs.length - 1] = { role: 'assistant', content, thinkSeconds, toolCalls: Object.values(toolCallMap) };
            return msgs;
          });
        }
      }
      // ensure final state is not loading
      setMsgs(prev => {
        const msgs = [...prev];
        if (msgs[msgs.length - 1]?.loading) {
          msgs[msgs.length - 1] = { ...msgs[msgs.length - 1], loading: false };
        }
        return msgs;
      });
    } catch (err: unknown) {
      if ((err as Error)?.name !== 'AbortError') {
        setMsgs(prev => {
          const msgs = [...prev];
          msgs[msgs.length - 1] = { role: 'assistant', content: '⚠️ 请求失败，请重试' };
          return msgs;
        });
      }
    } finally {
      setLoading(false);
    }
  }

  if (!app) {
    return <div className="flex items-center justify-center h-full text-gray-400">加载中...</div>;
  }

  // ── Variable screen ─────────────────────────────────────────────────────────
  if (!varsSubmitted && (app.variables ?? []).length > 0) {
    return (
      <div className="flex flex-col h-full bg-gray-50">
        <div className="bg-white border-b border-gray-200 px-6 py-4 flex items-center gap-3">
          <button onClick={() => navigate('/apps')} className="text-gray-500 hover:text-gray-800">
            <ArrowLeft size={18} />
          </button>
          <span className="text-lg">{app.icon}</span>
          <span className="font-semibold text-gray-900">{app.name}</span>
        </div>
        <div className="flex-1 flex items-center justify-center p-8">
          <div className="bg-white rounded-2xl border border-gray-200 shadow-sm p-8 w-full max-w-md">
            <div className="text-center mb-6">
              <span className="text-4xl">{app.icon}</span>
              <h2 className="text-xl font-bold text-gray-900 mt-3">{app.name}</h2>
              {app.description && <p className="text-sm text-gray-500 mt-1">{app.description}</p>}
            </div>
            <div className="space-y-4">
              {app.variables.map(v => (
                <div key={v.key}>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    {v.label} {v.required && <span className="text-red-500">*</span>}
                  </label>
                  {v.type === 'textarea' ? (
                    <textarea
                      value={varValues[v.key] ?? ''}
                      onChange={e => setVarValues(p => ({ ...p, [v.key]: e.target.value }))}
                      rows={3}
                      placeholder={v.default || `请输入${v.label}`}
                      className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm resize-none focus:outline-none focus:ring-2 focus:ring-purple-300"
                    />
                  ) : v.type === 'select' ? (
                    <select
                      value={varValues[v.key] ?? ''}
                      onChange={e => setVarValues(p => ({ ...p, [v.key]: e.target.value }))}
                      className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-purple-300"
                    >
                      {(v.options ?? []).map(o => <option key={o}>{o}</option>)}
                    </select>
                  ) : (
                    <input
                      value={varValues[v.key] ?? ''}
                      onChange={e => setVarValues(p => ({ ...p, [v.key]: e.target.value }))}
                      placeholder={v.default || `请输入${v.label}`}
                      className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-purple-300"
                    />
                  )}
                </div>
              ))}
            </div>
            <button
              onClick={handleVarsSubmit}
              className="w-full mt-6 py-3 bg-purple-600 text-white rounded-xl font-medium hover:bg-purple-700"
            >
              开始对话
            </button>
          </div>
        </div>
      </div>
    );
  }

  // ── Chat screen ─────────────────────────────────────────────────────────────
  return (
    <div className="flex flex-col h-screen w-screen bg-gray-50">
      {/* 模态确认弹框：当有待确认操作时全屏显示 */}
      {activePendingConfirm && (
        <ConfirmModal
          req={activePendingConfirm}
          onAllowAll={() => autoAllowRef.current.add(activePendingConfirm.name)}
          onDecision={() =>
            setMsgs(prev =>
              prev.map(m =>
                m.pendingConfirm?.tool_call_id === activePendingConfirm.tool_call_id
                  ? { ...m, pendingConfirm: null }
                  : m
              )
            )
          }
        />
      )}
      {/* Header */}
      <div className="bg-white border-b border-gray-200 px-6 py-3 flex items-center gap-3 shrink-0 shadow-sm">
        <button onClick={() => navigate('/apps')} className="text-gray-500 hover:text-gray-800">
          <ArrowLeft size={18} />
        </button>
        <span className="text-xl">{app.icon}</span>
        <div className="flex-1 min-w-0">
          <h1 className="font-semibold text-gray-900 text-sm truncate">{app.name}</h1>
          {app.description && <p className="text-xs text-gray-500 truncate">{app.description}</p>}
        </div>
        {/* Tool badges */}
        {app.tools.length > 0 && (
          <div className="hidden sm:flex gap-1">
            {app.tools.slice(0, 2).map(t => (
              <span key={t} className="text-[10px] bg-blue-50 text-blue-500 px-1.5 py-0.5 rounded-full flex items-center gap-0.5">
                <Wrench size={9} /> {t}
              </span>
            ))}
            {app.tools.length > 2 && (
              <span className="text-[10px] bg-gray-50 text-gray-400 px-1.5 py-0.5 rounded-full">+{app.tools.length - 2}</span>
            )}
          </div>
        )}
        <button
          onClick={() => navigate(`/apps/${id}/build`)}
          className="flex items-center gap-1.5 px-3 py-1.5 text-xs text-gray-600 border border-gray-200 rounded-lg hover:bg-gray-50"
          title="配置应用"
        >
          <Settings size={13} /> 配置
        </button>
        <button
          onClick={handleNewChat}
          className="flex items-center gap-1.5 px-3 py-1.5 text-xs text-gray-600 border border-gray-200 rounded-lg hover:bg-gray-50"
        >
          <Plus size={13} /> 新对话
        </button>
        <div className="relative">
          <button
            onClick={() => setShowHistory(h => !h)}
            className="flex items-center gap-1.5 px-3 py-1.5 text-xs text-gray-600 border border-gray-200 rounded-lg hover:bg-gray-50"
          >
            <History size={13} /> 历史 <ChevronDown size={12} />
          </button>
          {showHistory && (
            <div className="absolute right-0 top-full mt-1 w-64 bg-white border border-gray-200 rounded-xl shadow-lg z-20 overflow-hidden">
              <div className="px-3 py-2 border-b border-gray-100 text-xs font-medium text-gray-500">历史对话</div>
              <div className="max-h-60 overflow-y-auto">
                {sessions.length === 0 ? (
                  <div className="px-4 py-3 text-xs text-gray-400">暂无历史记录</div>
                ) : sessions.map(s => (
                  <button
                    key={s.id}
                    onClick={() => handleLoadSession(s.id)}
                    className={`w-full text-left px-4 py-2.5 text-xs hover:bg-gray-50 ${s.id === currentSession ? 'bg-purple-50 text-purple-700' : 'text-gray-700'}`}
                  >
                    <div className="font-medium truncate">{s.title}</div>
                    <div className="text-gray-400 mt-0.5">{new Date(s.created_at).toLocaleString('zh-CN')}</div>
                  </button>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto py-6">
        <div className="max-w-5xl mx-auto px-6 space-y-6">
        {msgs.map((msg, i) => (
          <div key={i} className={`flex gap-3 ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
            {msg.role === 'assistant' && (
              <div className="w-9 h-9 rounded-full bg-purple-100 flex items-center justify-center text-lg shrink-0 mt-0.5">
                {app.icon}
              </div>
            )}
            <div className="max-w-[85%] space-y-2">
              {/* Tool calls */}
              {msg.toolCalls && msg.toolCalls.length > 0 && (
                <div className="space-y-1.5">
                  {msg.toolCalls.map((tc, ti) => (
                    <ToolBlock key={ti} tc={tc} />
                  ))}
                </div>
              )}
              <MsgBubble msg={msg} enableSandboxHtml={!!(app.model_params as Record<string,unknown>)?.enable_sandbox_html} />
            </div>
          </div>
        ))}
        <div ref={chatEndRef} />
        </div>
      </div>

      {/* Input */}
      <div className="bg-white border-t border-gray-200 px-6 py-4 shrink-0 shadow-[0_-1px_8px_rgba(0,0,0,0.04)]">
        <div className="max-w-5xl mx-auto flex gap-3 items-end">
          <textarea
            ref={inputRef}
            value={input}
            onChange={e => setInput(e.target.value)}
            onKeyDown={e => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); handleSend(); } }}
            placeholder={`向 ${app.name} 发送消息... (Enter 发送，Shift+Enter 换行)`}
            rows={2}
            className="flex-1 border border-gray-200 rounded-2xl px-4 py-3 text-sm resize-none focus:outline-none focus:ring-2 focus:ring-purple-300 max-h-48 min-h-[52px]"
          />
          <button
            onClick={handleSend}
            disabled={loading || !input.trim()}
            className="p-3 bg-purple-600 text-white rounded-2xl hover:bg-purple-700 disabled:opacity-40 transition-colors"
          >
            {loading ? <Loader2 size={20} className="animate-spin" /> : <Send size={20} />}
          </button>
        </div>
      </div>
    </div>
  );
}

function MsgBubble({ msg, enableSandboxHtml }: { msg: ChatMsg; enableSandboxHtml?: boolean }) {
  const isUser = msg.role === 'user';
  // 历史消息优先用 DB 存储的 thinkingContent；流式消息 fallback 到解析 <think> 标签
  const { thinking, answer } = useMemo(() => {
    if (isUser) return { thinking: '', answer: msg.content };
    if (msg.thinkingContent) return { thinking: msg.thinkingContent, answer: msg.content };
    return parseThink(msg.content);
  }, [msg.content, msg.thinkingContent, isUser]);

  return (
    <div className={`rounded-2xl px-4 py-3 text-sm leading-relaxed ${
      isUser
        ? 'bg-purple-600 text-white rounded-br-sm'
        : 'bg-white border border-gray-200 text-gray-800 rounded-bl-sm shadow-sm'
    }`}>
      {!isUser && (thinking || (msg.loading && !answer)) && (
        <ThinkingBlock thinking={thinking} loading={msg.loading} thinkSeconds={msg.thinkSeconds} />
      )}

      {/* Main content */}
      {isUser ? (
        <span className="whitespace-pre-wrap">{msg.content}</span>
      ) : answer ? (
        <div className="prose prose-sm max-w-none prose-p:my-1 prose-pre:bg-gray-50 prose-pre:border prose-pre:border-gray-200">
          <ReactMarkdown
            remarkPlugins={[remarkGfm]}
            components={{
              code({ className, children, ...props }) {
                const lang = (className ?? '').replace('language-', '');
                const code = String(children).replace(/\n$/, '');
                if (lang && isDiagramLang(lang)) {
                  return <DiagramBlock lang={lang} code={code} />;
                }
                // HTML 沙箱渲染（需开关开启）流式期间不渲染，防止 iframe 每帧重载
                if (lang === 'html' && enableSandboxHtml) {
                  if (msg.loading) return <code className="block text-xs text-gray-400 bg-gray-50 border border-gray-200 rounded p-2">⏳ HTML 渲染中，等待完成...</code>;
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
      ) : msg.loading ? (
        <Loader2 size={16} className="animate-spin text-gray-400" />
      ) : null}
    </div>
  );
}
