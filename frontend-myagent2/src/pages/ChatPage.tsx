import { useState, useEffect, useRef, useCallback, useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  MessageSquare, Plus, Trash2, Send, Loader2, ChevronDown, ChevronRight,
  Wrench, AlertCircle, Cpu, Brain, FileText, Workflow, Zap,
} from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { toast } from 'sonner';
import { chatApi, sendMessage } from '@/api/chat';
import { streamMultiAgent } from '@/api/executions';
import type { MultiAgentConfig } from '@/api/executions';
import AgentConfigDrawer from '@/components/AgentConfigDrawer';
import MultiAgentBubble from '@/components/MultiAgentBubble';
import type { AgentEvent, AgentState } from '@/components/MultiAgentBubble';
import { skillApi } from '@/api/skills';
import { workflowApi } from '@/api/workflows';
import { executionApi } from '@/api/executions';
import RunWorkflowDialog from '@/components/workflow/RunWorkflowDialog';
import { ThinkingBlock } from '@/components/ThinkingBlock';
import { DiagramBlock, isDiagramLang } from '@/components/DiagramBlock';
import { LazyImage } from '@/components/LazyImage';
import { get } from '@/api/client';
import type { ChatSession, SSEEvent } from '@/api/chat';
import type { SkillDTO } from '@/api/skills';
import type { WorkflowDTO as FullWorkflowDTO } from '@/api/workflows';

// ── Types ──

interface ModelConfig {
  id: string;
  provider: string;
  name: string;
  model_id: string;
  api_base: string;
  is_default: boolean;
  config: Record<string, unknown>;
}

interface PromptDTO { id: string; name: string; description: string; content: string; }
interface WorkflowDTO { id: string; name: string; description: string; }

interface ToolCallUI {
  id: string;
  name: string;
  arguments: Record<string, unknown>;
  result?: Record<string, unknown>;
  status: 'running' | 'done' | 'error';
}

interface UIMessage {
  id: string;
  role: 'user' | 'assistant' | 'tool' | 'system';
  content: string;
  thinkingContent?: string;
  toolCalls?: ToolCallUI[];
  metadata?: Record<string, unknown>;
  isStreaming?: boolean;
  thinkSeconds?: number;
  isMultiAgent?: boolean;
  multiAgentMode?: string;
  multiAgentNames?: string[];
}

// ── Helpers: parse <think> tags ──

function parseThinkContent(raw: string): { thinking: string; answer: string } {
  // Handle both <think> (Qwen3) and <thinking> (Claude) tags
  for (const tag of ['thinking', 'think']) {
    const open = `<${tag}>`, close = `</${tag}>`;
    const startM = raw.match(new RegExp(`^${open}([\\s\\S]*?)(${close}|$)`));
    if (startM) return { thinking: startM[1].trim(), answer: raw.slice(startM[0].length).trim() };
    const anyM = raw.match(new RegExp(`^([\\s\\S]*?)${open}([\\s\\S]*?)${close}([\\s\\S]*)$`));
    if (anyM) return { thinking: anyM[2].trim(), answer: (anyM[1] + anyM[3]).trim() };
  }
  return { thinking: '', answer: raw };
}

// ── Main Component ──

export default function ChatPage() {
  const navigate = useNavigate();
  const [sessions, setSessions] = useState<ChatSession[]>([]);
  const [activeSessionId, setActiveSessionId] = useState<string | null>(null);
  const [messages, setMessages] = useState<UIMessage[]>([]);
  const [input, setInput] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [isSending, setIsSending] = useState(false);

  // Model selector
  const [models, setModels] = useState<ModelConfig[]>([]);
  const [selectedModel, setSelectedModel] = useState('');

  // Resources for toolbar selectors
  const [skills, setSkills] = useState<SkillDTO[]>([]);
  const [prompts, setPrompts] = useState<PromptDTO[]>([]);
  const [workflows, setWorkflows] = useState<WorkflowDTO[]>([]);
  const [selectedSkillId, setSelectedSkillId] = useState('');
  const [selectedPromptId, setSelectedPromptId] = useState('');
  const [selectedWorkflowId, setSelectedWorkflowId] = useState('');

  // Multi-Agent
  const [showAgentDrawer, setShowAgentDrawer] = useState(false);
  type MaSnapshot = { states: Record<string, AgentState>; routes: { from: string; to: string; task: string }[]; done: boolean; applyEvent: () => void };
  const [maStates, setMaStates] = useState<Map<string, MaSnapshot>>(new Map());

  // ── Multi-Agent send ──
  const handleMultiAgentSend = useCallback(async (mode: string, agents: MultiAgentConfig[]) => {
    if (!input.trim() || !activeSessionId || isSending) return;
    const userContent = input.trim();
    setInput('');
    setIsSending(true);

    const userMsgId = `msg_${Date.now()}_u`;
    const maMsgId = `msg_${Date.now()}_ma`;
    const agentNames = agents.map(a => a.name);

    // 注入用户消息 + Multi-Agent 占位消息
    setMessages(prev => [
      ...prev,
      { id: userMsgId, role: 'user', content: userContent },
      { id: maMsgId, role: 'assistant', content: '', isMultiAgent: true, multiAgentMode: mode, multiAgentNames: agentNames },
    ]);

    type MaRunState = { states: Record<string, AgentState>; routes: { from: string; to: string; task: string }[]; done: boolean };
    const maState: MaRunState = {
      states: Object.fromEntries(agentNames.map(n => [n, { name: n, status: 'waiting' as const, content: '', toolCalls: [] } satisfies AgentState])),
      routes: [],
      done: false,
    };
    const statesRef = { current: maState };

    try {
      for await (const event of streamMultiAgent(activeSessionId, mode, agents, userContent)) {
        const e = event as unknown as AgentEvent;
        const eName = e.agent_name;
        if (!eName) {
          if (e.type === 'multi_agent_done') statesRef.current = { ...statesRef.current, done: true };
          continue;
        }
        const prev: AgentState = statesRef.current.states[eName] ?? { name: eName, status: 'waiting', content: '', toolCalls: [] };
        let next: AgentState = { ...prev };
        if (e.type === 'agent_start') next = { ...next, status: 'running' };
        else if (e.type === 'delta') next = { ...next, content: next.content + (e.content ?? '') };
        else if (e.type === 'tool_start') next = { ...next, toolCalls: [...next.toolCalls, { id: e.tool_call_id ?? '', name: e.name ?? '', status: 'running' }] };
        else if (e.type === 'tool_result') next = { ...next, toolCalls: next.toolCalls.map(tc => tc.id === e.tool_call_id ? { ...tc, status: 'done' as const } : tc) };
        else if (e.type === 'agent_done') next = { ...next, status: 'done', inputTokens: e.input_tokens, outputTokens: e.output_tokens };
        else if (e.type === 'agent_error') next = { ...next, status: 'error', content: e.message ?? '' };
        if (e.type === 'agent_route' && e.from_agent && e.to_agent) {
          statesRef.current = { ...statesRef.current, routes: [...statesRef.current.routes, { from: e.from_agent, to: e.to_agent, task: e.task ?? '' }] };
        }
        statesRef.current = { ...statesRef.current, states: { ...statesRef.current.states, [eName]: next } };

        setMaStates(prev => {
          const map = new Map(prev);
          map.set(maMsgId, { ...statesRef.current, applyEvent: () => {} });
          return map;
        });
      }
    } catch (err) {
      toast.error('Multi-Agent 执行失败');
    } finally {
      setIsSending(false);
    }
  }, [input, activeSessionId, isSending]);

  // Workflow run dialog
  const [wfRunOpen, setWfRunOpen] = useState(false);
  const [wfRunDef, setWfRunDef] = useState<FullWorkflowDTO | null>(null);
  const [wfRunPrefill, setWfRunPrefill] = useState('');

  // Slash command autocomplete
  const [showSlash, setShowSlash] = useState(false);
  const [slashFilter, setSlashFilter] = useState('');

  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const thinkStartedAtRef = useRef<number | null>(null);

  // ── LLM models (filter out embedding) ──
  const llmModels = useMemo(
    () => models.filter(m => {
      const role = (m.config as Record<string, string>)?.role;
      return role !== 'embedding';
    }),
    [models]
  );

  // ── Load resources on mount ──
  useEffect(() => {
    get<{ items: ModelConfig[] }>('/api/models').then(res => {
      setModels(res.items);
      const def = res.items.find(m => m.is_default);
      if (def) setSelectedModel(def.model_id);
    }).catch(() => {});

    skillApi.list().then(res => setSkills(res.items)).catch(() => {});
    get<{ items: PromptDTO[] }>('/api/prompts').then(res => setPrompts(res.items)).catch(() => {});
    get<{ items: WorkflowDTO[] }>('/api/workflows').then(res => setWorkflows(res.items)).catch(() => {});
  }, []);

  // ── Fetch full workflow definition when selector changes ──
  useEffect(() => {
    if (!selectedWorkflowId) {
      setWfRunDef(null);
      return;
    }
    workflowApi.get(selectedWorkflowId).then(res => setWfRunDef(res)).catch(() => setWfRunDef(null));
  }, [selectedWorkflowId]);

  // ── Load sessions ──
  const loadSessions = useCallback(async () => {
    try {
      const res = await chatApi.listSessions();
      setSessions(res.items);
    } catch (e) {
      console.error('Load sessions error:', e);
    }
  }, []);

  useEffect(() => { loadSessions(); }, [loadSessions]);

  // ── Load session messages ──
  const loadSession = useCallback(async (sid: string) => {
    setActiveSessionId(sid);
    setIsLoading(true);
    try {
      const detail = await chatApi.getSession(sid);
      const uiMsgs: UIMessage[] = detail.messages
        .filter(m => m.role !== 'tool')
        .map(m => ({
          id: m.id,
          role: m.role,
          content: m.content,
          thinkingContent: m.thinking_content ?? undefined,
          metadata: {
            ...(m.metadata ?? {}),
            ...(m.model ? { model: m.model } : {}),
            ...(m.input_tokens != null ? { input_tokens: m.input_tokens } : {}),
            ...(m.output_tokens != null ? { output_tokens: m.output_tokens } : {}),
            ...(m.latency_ms != null ? { latency_ms: m.latency_ms } : {}),
          },
        }));
      setMessages(uiMsgs);
      // Restore model from session if set
      if (detail.model) setSelectedModel(detail.model);
    } catch {
      toast.error('加载会话失败');
    } finally {
      setIsLoading(false);
    }
  }, []);

  // ── Create session ──
  const createSession = useCallback(async () => {
    try {
      const res = await chatApi.createSession({ model: selectedModel });
      await loadSessions();
      setActiveSessionId(res.id);
      setMessages([]);
    } catch {
      toast.error('创建会话失败');
    }
  }, [loadSessions, selectedModel]);

  // ── Delete session ──
  const deleteSession = useCallback(async (sid: string, e: React.MouseEvent) => {
    e.stopPropagation();
    try {
      await chatApi.deleteSession(sid);
      if (activeSessionId === sid) {
        setActiveSessionId(null);
        setMessages([]);
      }
      await loadSessions();
    } catch {
      toast.error('删除失败');
    }
  }, [activeSessionId, loadSessions]);

  // ── Build message content with context ──
  const buildContent = useCallback((raw: string): string => {
    const parts: string[] = [];

    // Prepend selected prompt
    if (selectedPromptId) {
      const prompt = prompts.find(p => p.id === selectedPromptId);
      if (prompt) parts.push(`[Prompt: ${prompt.name}]\n${prompt.content}`);
    }

    // Prepend selected skill as slash command
    if (selectedSkillId && !raw.startsWith('/')) {
      const skill = skills.find(s => s.id === selectedSkillId);
      if (skill) parts.push(`/${skill.name}`);
    }

    parts.push(raw);
    return parts.join('\n\n');
  }, [selectedPromptId, selectedSkillId, prompts, skills]);

  // ── Workflow run from chat ──
  const wfInputFields = useMemo(() => {
    if (!wfRunDef) return [];
    const def = wfRunDef.definition as { nodes?: Array<{ type?: string; data?: { outputs?: string[] } }> } | undefined;
    return (def?.nodes ?? []).find(n => n.type === 'start')?.data?.outputs ?? [];
  }, [wfRunDef]);

  // Run workflow and show result inline in chat (no page navigation)
  const executeWorkflowInChat = useCallback(async (inputs: Record<string, unknown>) => {
    if (!wfRunDef) return;
    setWfRunOpen(false);

    const msgId = `wf_${Date.now()}`;
    const wfName = wfRunDef.name;
    setMessages(prev => [...prev, {
      id: msgId,
      role: 'assistant' as const,
      content: '',
      isStreaming: true,
    }]);
    setIsSending(true);

    try {
      const res = await workflowApi.execute(wfRunDef.id, inputs);
      const execId = res.execution_id;

      // Poll until terminal state (max 120s)
      let resultText = '';
      for (let i = 0; i < 120; i++) {
        await new Promise(r => setTimeout(r, 1000));
        const exec = await executionApi.get(execId);
        const s = exec.status;
        if (s === 'done' || s === 'error' || s === 'failed' || s === 'cancelled') {
          if (s === 'done') {
            const outs = (exec as unknown as Record<string, unknown>).outputs as Record<string, unknown> ?? {};
            const first = Object.values(outs).find(v => typeof v === 'string' && (v as string).length > 0) as string ?? '';
            resultText = first.replace(/<think>[\s\S]*?<\/think>/g, '').trim() || JSON.stringify(outs, null, 2);
          } else {
            resultText = `❌ ${wfName} 执行${s === 'cancelled' ? '已取消' : '失败'}: ${
              (exec as unknown as Record<string, unknown>).error ?? '未知错误'
            }`;
          }
          break;
        }
      }
      if (!resultText) resultText = `⌛ ${wfName} 执行超时（超过 2 分钟）`;

      setMessages(prev => prev.map(m =>
        m.id === msgId ? { ...m, content: resultText, isStreaming: false } : m
      ));
    } catch {
      setMessages(prev => prev.map(m =>
        m.id === msgId ? { ...m, content: `❌ 工作流 ${wfName} 执行失败`, isStreaming: false } : m
      ));
      toast.error('工作流执行失败');
    } finally {
      setIsSending(false);
    }
  }, [wfRunDef]);

  const handleWorkflowRun = useCallback(async (inputs: Record<string, unknown>) => {
    await executeWorkflowInChat(inputs);
  }, [executeWorkflowInChat]);

  // ── Send message ──
  const handleSend = useCallback(async () => {
    if (!input.trim() || !activeSessionId || isSending) return;

    // If a workflow is selected: smart dispatch based on input variable count
    if (selectedWorkflowId && wfRunDef) {
      const userText = input.trim();
      setInput('');
      setShowSlash(false);
      setMessages(prev => [...prev, {
        id: `user_${Date.now()}`,
        role: 'user' as const,
        content: userText,
      }]);
      if (wfInputFields.length === 0) {
        // No inputs needed — run directly
        executeWorkflowInChat({});
      } else if (wfInputFields.length === 1) {
        // Single input — auto-map chat message to that variable
        executeWorkflowInChat({ [wfInputFields[0]]: userText });
      } else {
        // Multiple inputs — open form dialog, prefill first field
        setWfRunPrefill(userText);
        setWfRunOpen(true);
      }
      return;
    }

    const userContent = input.trim();
    const sendContent = buildContent(userContent);
    setInput('');
    setShowSlash(false);

    // Add user message to UI (show raw input, not with prepended context)
    const userMsg: UIMessage = {
      id: `temp_${Date.now()}`,
      role: 'user',
      content: userContent,
    };
    setMessages(prev => [...prev, userMsg]);

    // Add streaming assistant placeholder
    const assistantMsg: UIMessage = {
      id: `temp_assistant_${Date.now()}`,
      role: 'assistant',
      content: '',
      isStreaming: true,
      toolCalls: [],
    };
    setMessages(prev => [...prev, assistantMsg]);

    setIsSending(true);
    thinkStartedAtRef.current = null;

    // Update session model if changed
    if (selectedModel) {
      chatApi.updateSession(activeSessionId, { model: selectedModel }).catch(() => {});
    }

    try {
      for await (const event of sendMessage(activeSessionId, sendContent, selectedModel || undefined)) {
        handleSSEEvent(event, assistantMsg.id);
      }
    } catch (e) {
      console.error('Send error:', e);
      setMessages(prev =>
        prev.map(m =>
          m.id === assistantMsg.id
            ? { ...m, content: m.content + '\n\n⚠️ 发生错误', isStreaming: false }
            : m
        )
      );
    } finally {
      setIsSending(false);
      setMessages(prev =>
        prev.map(m =>
          m.id === assistantMsg.id ? { ...m, isStreaming: false } : m
        )
      );
      loadSessions();
    }
  }, [input, activeSessionId, isSending, selectedModel, buildContent, selectedWorkflowId, wfRunDef]);

  const handleSSEEvent = useCallback((event: SSEEvent, assistantMsgId: string) => {
    switch (event.type) {
      case 'delta': {
        const chunk = event.content || '';
        if ((chunk.includes('<thinking>') || chunk.includes('<think>')) && thinkStartedAtRef.current === null) {
          thinkStartedAtRef.current = Date.now();
        }
        setMessages(prev =>
          prev.map(m =>
            m.id === assistantMsgId
              ? { ...m, content: m.content + chunk }
              : m
          )
        );
        break;
      }

      case 'tool_start':
        setMessages(prev =>
          prev.map(m => {
            if (m.id !== assistantMsgId) return m;
            const tc: ToolCallUI = {
              id: event.tool_call_id || '',
              name: event.name || '',
              arguments: event.arguments || {},
              status: 'running',
            };
            return { ...m, toolCalls: [...(m.toolCalls || []), tc] };
          })
        );
        break;

      case 'tool_result':
        setMessages(prev =>
          prev.map(m => {
            if (m.id !== assistantMsgId) return m;
            const toolCalls = (m.toolCalls || []).map(tc =>
              tc.id === event.tool_call_id
                ? { ...tc, result: event.result, status: 'done' as const }
                : tc
            );
            return { ...m, toolCalls };
          })
        );
        break;

      case 'done': {
        const thinkSeconds = thinkStartedAtRef.current
          ? Math.round((Date.now() - thinkStartedAtRef.current) / 1000)
          : undefined;
        setMessages(prev =>
          prev.map(m =>
            m.id === assistantMsgId
              ? { ...m, metadata: event.metadata, isStreaming: false, thinkSeconds }
              : m
          )
        );
        break;
      }

      case 'error':
        setMessages(prev =>
          prev.map(m =>
            m.id === assistantMsgId
              ? { ...m, content: m.content + `\n\n⚠️ ${event.message || '未知错误'}`, isStreaming: false }
              : m
          )
        );
        break;
    }
  }, []);

  // ── Auto scroll ──
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  // ── Slash command handling ──
  const handleInputChange = useCallback((val: string) => {
    setInput(val);
    if (val.startsWith('/')) {
      setShowSlash(true);
      setSlashFilter(val.slice(1).toLowerCase());
    } else {
      setShowSlash(false);
    }
  }, []);

  const filteredSkills = skills.filter(s =>
    s.name.toLowerCase().includes(slashFilter) ||
    s.description.toLowerCase().includes(slashFilter)
  );

  const selectSkill = useCallback((skill: SkillDTO) => {
    setInput(`/${skill.name} `);
    setShowSlash(false);
    inputRef.current?.focus();
  }, []);

  // ── Keyboard ──
  const handleKeyDown = useCallback((e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
    if (e.key === 'Escape') {
      setShowSlash(false);
    }
  }, [handleSend]);

  return (
    <div className="flex h-full">
      {/* ── Session Sidebar ── */}
      <aside className="w-64 bg-white border-r border-gray-200 flex flex-col shrink-0">
        <div className="p-3 border-b border-gray-100">
          <button
            onClick={createSession}
            className="w-full flex items-center justify-center gap-2 px-3 py-2 text-sm bg-purple-600 hover:bg-purple-700 text-white rounded-lg transition-colors"
          >
            <Plus size={16} />
            新对话
          </button>
        </div>

        <div className="flex-1 overflow-y-auto py-2">
          {sessions.length === 0 && (
            <div className="text-center text-gray-400 text-xs py-8">暂无会话</div>
          )}
          {sessions.map(s => (
            <div
              key={s.id}
              onClick={() => loadSession(s.id)}
              className={`group flex items-center gap-2 px-3 py-2.5 mx-2 rounded-lg cursor-pointer text-sm transition-colors ${
                activeSessionId === s.id
                  ? 'bg-purple-50 text-purple-700'
                  : 'text-gray-600 hover:bg-gray-50'
              }`}
            >
              <MessageSquare size={14} className="shrink-0" />
              <span className="flex-1 truncate">{s.title || '新对话'}</span>
              <button
                onClick={(e) => deleteSession(s.id, e)}
                className="opacity-0 group-hover:opacity-100 p-0.5 rounded hover:bg-red-50 hover:text-red-500 transition-all"
              >
                <Trash2 size={12} />
              </button>
            </div>
          ))}
        </div>
      </aside>

      {/* ── Main Chat Area ── */}
      <div className="flex-1 flex flex-col bg-gray-50">
        {!activeSessionId ? (
          <EmptyState onNew={createSession} />
        ) : (
          <>
            {/* ── Toolbar: model + skill + prompt + workflow selectors ── */}
            <div className="flex items-center gap-3 px-4 py-2 bg-white border-b border-gray-200 text-xs">
              {/* Model selector */}
              <label className="flex items-center gap-1.5 text-gray-500">
                <Cpu size={13} />
                <select
                  value={selectedModel}
                  onChange={(e) => setSelectedModel(e.target.value)}
                  className="bg-gray-50 border border-gray-200 rounded-md px-2 py-1 text-xs text-gray-700 outline-none focus:border-purple-400"
                >
                  {llmModels.map(m => (
                    <option key={m.id} value={m.model_id}>{m.name}</option>
                  ))}
                </select>
              </label>

              <div className="w-px h-4 bg-gray-200" />

              {/* Skill selector */}
              <label className="flex items-center gap-1.5 text-gray-500">
                <Brain size={13} />
                <select
                  value={selectedSkillId}
                  onChange={(e) => setSelectedSkillId(e.target.value)}
                  className="bg-gray-50 border border-gray-200 rounded-md px-2 py-1 text-xs text-gray-700 outline-none focus:border-purple-400 max-w-[120px]"
                >
                  <option value="">技能 (无)</option>
                  {skills.map(s => (
                    <option key={s.id} value={s.id}>{s.name}</option>
                  ))}
                </select>
              </label>

              {/* Prompt selector */}
              <label className="flex items-center gap-1.5 text-gray-500">
                <FileText size={13} />
                <select
                  value={selectedPromptId}
                  onChange={(e) => setSelectedPromptId(e.target.value)}
                  className="bg-gray-50 border border-gray-200 rounded-md px-2 py-1 text-xs text-gray-700 outline-none focus:border-purple-400 max-w-[120px]"
                >
                  <option value="">Prompt (无)</option>
                  {prompts.map(p => (
                    <option key={p.id} value={p.id}>{p.name}</option>
                  ))}
                </select>
              </label>

              {/* Workflow selector */}
              <label className={`flex items-center gap-1.5 ${selectedWorkflowId ? 'text-purple-600' : 'text-gray-500'}`}>
                <Workflow size={13} />
                <select
                  value={selectedWorkflowId}
                  onChange={(e) => setSelectedWorkflowId(e.target.value)}
                  className={`rounded-md px-2 py-1 text-xs outline-none max-w-[140px] ${selectedWorkflowId ? 'bg-purple-50 border border-purple-300 text-purple-700 focus:border-purple-500' : 'bg-gray-50 border border-gray-200 text-gray-700 focus:border-purple-400'}`}
                >
                  <option value="">工作流 (无)</option>
                  {workflows.map(w => (
                    <option key={w.id} value={w.id}>{w.name}</option>
                  ))}
                </select>
              </label>
              {selectedWorkflowId && (
                <span className="text-[10px] px-1.5 py-0.5 rounded bg-purple-100 text-purple-600 font-medium">工作流模式</span>
              )}
            </div>

            {/* Messages */}
            <div className="flex-1 overflow-y-auto px-4 py-6">
              {isLoading ? (
                <div className="flex items-center justify-center py-20">
                  <Loader2 className="animate-spin text-purple-500" size={24} />
                </div>
              ) : messages.length === 0 ? (
                <div className="flex flex-col items-center justify-center py-20 text-gray-400">
                  <MessageSquare size={40} className="mb-3 opacity-50" />
                  <p className="text-sm">开始对话吧</p>
                  <p className="text-xs mt-1">输入 / 可触发技能命令</p>
                </div>
              ) : (
                <div className="max-w-3xl mx-auto space-y-4">
                  {messages.map(msg => {
                    if (msg.isMultiAgent) {
                      const ma = maStates.get(msg.id);
                      return (
                        <div key={msg.id} className="flex justify-start">
                          <MultiAgentBubble
                            agentNames={msg.multiAgentNames ?? []}
                            mode={msg.multiAgentMode ?? 'sequential'}
                            states={ma?.states ?? {}}
                            routes={ma?.routes ?? []}
                            done={ma?.done ?? false}
                          />
                        </div>
                      );
                    }
                    return <MessageBubble key={msg.id} message={msg} />;
                  })}
                  <div ref={messagesEndRef} />
                </div>
              )}
            </div>

            {/* Input Area */}
            <div className="border-t border-gray-200 bg-white p-4">
              <div className="max-w-3xl mx-auto relative">
                {/* Slash autocomplete */}
                {showSlash && filteredSkills.length > 0 && (
                  <div className="absolute bottom-full mb-2 left-0 right-0 bg-white rounded-lg shadow-lg border border-gray-200 max-h-60 overflow-y-auto z-10">
                    {filteredSkills.map(s => (
                      <button
                        key={s.id}
                        onClick={() => selectSkill(s)}
                        className="w-full flex items-start gap-3 px-4 py-2.5 hover:bg-purple-50 text-left transition-colors"
                      >
                        <span className="text-purple-600 font-mono text-sm">/{s.name}</span>
                        <span className="text-gray-500 text-xs truncate">{s.description}</span>
                      </button>
                    ))}
                  </div>
                )}

                <div className="flex items-end gap-2 bg-gray-50 rounded-xl border border-gray-200 focus-within:border-purple-400 focus-within:ring-1 focus-within:ring-purple-200 transition-all">
                  <textarea
                    ref={inputRef}
                    value={input}
                    onChange={(e) => handleInputChange(e.target.value)}
                    onKeyDown={handleKeyDown}
                    placeholder={
                      selectedWorkflowId
                        ? wfInputFields.length <= 1
                          ? `直接输入发送给「${workflows.find(w => w.id === selectedWorkflowId)?.name ?? '工作流'}」...`
                          : `输入主要内容，回车填写其余 ${wfInputFields.length} 个参数...`
                        : '输入消息... (/bash /search /python 直接调用工具，/ 触发技能)'
                    }
                    rows={1}
                    className="flex-1 bg-transparent resize-none px-4 py-3 text-sm outline-none max-h-32 min-h-[44px]"
                    style={{ height: 'auto', overflow: 'auto' }}
                    disabled={isSending}
                  />
                  <button
                    onClick={() => setShowAgentDrawer(true)}
                    disabled={!input.trim() || isSending}
                    title="Multi-Agent 模式"
                    className="m-2 p-2 rounded-lg border border-purple-200 hover:bg-purple-50 text-purple-500 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
                  >
                    <Zap size={16} />
                  </button>
                  <button
                    onClick={handleSend}
                    disabled={!input.trim() || isSending}
                    className="m-2 p-2 rounded-lg bg-purple-600 hover:bg-purple-700 text-white disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
                  >
                    {isSending ? (
                      <Loader2 size={16} className="animate-spin" />
                    ) : (
                      <Send size={16} />
                    )}
                  </button>
                </div>
              </div>
            </div>
          </>
        )}
      </div>
      <AgentConfigDrawer
        open={showAgentDrawer}
        onClose={() => setShowAgentDrawer(false)}
        onStart={handleMultiAgentSend}
      />
      <RunWorkflowDialog
        open={wfRunOpen}
        title={wfRunDef?.name ?? ''}
        inputFields={wfInputFields}
        defaultValues={wfInputFields.length > 0 ? { [wfInputFields[0]]: wfRunPrefill } : undefined}
        onClose={() => setWfRunOpen(false)}
        onSubmit={handleWorkflowRun}
      />
    </div>
  );
}

// ── Empty State ──

function EmptyState({ onNew }: { onNew: () => void }) {
  return (
    <div className="flex-1 flex flex-col items-center justify-center text-gray-400">
      <MessageSquare size={48} className="mb-4 opacity-40" />
      <h2 className="text-lg text-gray-600 font-medium mb-2">AgentFlow 对话</h2>
      <p className="text-sm mb-6">选择已有会话或创建新对话</p>
      <button
        onClick={onNew}
        className="flex items-center gap-2 px-4 py-2 bg-purple-600 hover:bg-purple-700 text-white rounded-lg text-sm transition-colors"
      >
        <Plus size={16} />
        开始新对话
      </button>
    </div>
  );
}

// ── Message Bubble with <think> separation ──

function MessageBubble({ message }: { message: UIMessage }) {
  const isUser = message.role === 'user';

  // 历史消息优先用 DB 中独立存储的 thinking_content；
  // 流式消息 fallback 到从 content 解析 <think> 标签
  const { thinking, answer } = useMemo(() => {
    if (isUser) return { thinking: '', answer: message.content };
    if (message.thinkingContent) return { thinking: message.thinkingContent, answer: message.content };
    return parseThinkContent(message.content);
  }, [message.content, message.thinkingContent, isUser]);

  return (
    <div className={`flex ${isUser ? 'justify-end' : 'justify-start'}`}>
      <div
        className={`max-w-[85%] rounded-2xl px-4 py-3 ${
          isUser
            ? 'bg-purple-600 text-white'
            : 'bg-white border border-gray-200 text-gray-800'
        }`}
      >
        {!isUser && (thinking || (message.isStreaming && !answer)) && (
          <ThinkingBlock
            thinking={thinking}
            loading={message.isStreaming}
            thinkSeconds={message.thinkSeconds}
          />
        )}

        {/* Main text content (answer only, no <think>) */}
        {(isUser ? message.content : answer) && (
          <div className={`text-sm leading-relaxed ${isUser ? '' : 'prose prose-sm max-w-none'}`}>
            {isUser ? (
              <p className="whitespace-pre-wrap">{message.content}</p>
            ) : (
              <ReactMarkdown
                remarkPlugins={[remarkGfm]}
                components={{
                  code({ className, children, ...props }) {
                    const lang = (className ?? '').replace('language-', '');
                    const code = String(children).replace(/\n$/, '');
                    if (lang && isDiagramLang(lang)) {
                      return <DiagramBlock lang={lang} code={code} />;
                    }
                    const isInline = !className;
                    if (isInline) {
                      return (
                        <code className="bg-gray-100 text-purple-700 px-1 py-0.5 rounded text-xs" {...props}>
                          {children}
                        </code>
                      );
                    }
                    return (
                      <pre className="bg-gray-900 text-gray-100 rounded-lg p-3 overflow-x-auto my-2">
                        <code className={`text-xs ${className || ''}`} {...props}>
                          {children}
                        </code>
                      </pre>
                    );
                  },
                  img({ src, alt }) {
                    return <LazyImage src={src ?? ''} alt={alt ?? ''} />;
                  },
                }}
              >
                {answer}
              </ReactMarkdown>
            )}
          </div>
        )}

        {/* Streaming indicator */}
        {message.isStreaming && !message.content && (
          <div className="flex items-center gap-2 text-gray-400 text-sm">
            <Loader2 size={14} className="animate-spin" />
            <span>思考中...</span>
          </div>
        )}

        {/* Tool calls */}
        {message.toolCalls && message.toolCalls.length > 0 && (
          <div className="mt-2 space-y-1.5">
            {message.toolCalls.map(tc => (
              <ToolCallCard key={tc.id} toolCall={tc} />
            ))}
          </div>
        )}

        {/* Metadata */}
        {message.metadata && !message.isStreaming && message.role === 'assistant' && (
          <div className="mt-2 pt-2 border-t border-gray-100 flex items-center gap-3 text-[10px] text-gray-400">
            {message.metadata.model && <span>模型: {String(message.metadata.model)}</span>}
            {message.metadata.latency_ms && <span>{String(message.metadata.latency_ms)}ms</span>}
            {(message.metadata.input_tokens || message.metadata.output_tokens) && (
              <span>
                {String(message.metadata.input_tokens || 0)}→{String(message.metadata.output_tokens || 0)} tokens
              </span>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

// ── Tool Call Card ──

function ToolCallCard({ toolCall }: { toolCall: ToolCallUI }) {
  const [expanded, setExpanded] = useState(false);

  return (
    <div className="bg-gray-50 rounded-lg border border-gray-200 text-xs">
      <button
        onClick={() => setExpanded(!expanded)}
        className="w-full flex items-center gap-2 px-3 py-2 hover:bg-gray-100 rounded-lg transition-colors"
      >
        {toolCall.status === 'running' ? (
          <Loader2 size={12} className="animate-spin text-blue-500" />
        ) : toolCall.status === 'error' ? (
          <AlertCircle size={12} className="text-red-500" />
        ) : (
          <Wrench size={12} className="text-green-600" />
        )}
        <span className="font-mono font-medium text-gray-700">{toolCall.name}</span>
        <span className="text-gray-400 flex-1 text-right">
          {toolCall.status === 'running' ? '执行中...' : '完成'}
        </span>
        {expanded ? <ChevronDown size={12} /> : <ChevronRight size={12} />}
      </button>

      {expanded && (
        <div className="px-3 pb-2 space-y-2">
          <div>
            <div className="text-[10px] text-gray-400 mb-0.5">参数</div>
            <pre className="bg-white border border-gray-200 rounded p-2 text-[10px] overflow-x-auto max-h-32">
              {JSON.stringify(toolCall.arguments, null, 2)}
            </pre>
          </div>
          {toolCall.result && (() => {
            const fileUrls = Array.isArray(toolCall.result.file_urls)
              ? (toolCall.result.file_urls as { url: string; name: string; type: string }[])
              : [];
            const textResult = { ...toolCall.result };
            delete (textResult as Record<string, unknown>).file_urls;
            const API_BASE = (import.meta as unknown as { env?: Record<string, string> }).env?.VITE_API_BASE ?? 'http://localhost:8001';
            return (
              <div className="space-y-2">
                {Object.keys(textResult).length > 0 && (
                  <div>
                    <div className="text-[10px] text-gray-400 mb-0.5">结果</div>
                    <pre className="bg-white border border-gray-200 rounded p-2 text-[10px] overflow-x-auto max-h-40">
                      {JSON.stringify(textResult, null, 2)}
                    </pre>
                  </div>
                )}
                {fileUrls.length > 0 && (
                  <div>
                    <div className="text-[10px] text-gray-400 mb-0.5">输出文件</div>
                    <div className="space-y-2">
                      {fileUrls.map((f, i) => (
                        f.type === 'image' ? (
                          <img key={i} src={API_BASE + f.url} alt={f.name}
                            className="max-w-full rounded border border-gray-200 block" loading="lazy" />
                        ) : (
                          <a key={i} href={API_BASE + f.url} target="_blank" rel="noreferrer"
                            className="flex items-center gap-1 text-blue-600 hover:underline text-[10px]">
                            📄 {f.name}
                          </a>
                        )
                      ))}
                    </div>
                  </div>
                )}
              </div>
            );
          })()}
        </div>
      )}
    </div>
  );
}
