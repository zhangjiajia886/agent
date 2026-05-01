import { useState, useMemo } from 'react';
import { ChevronDown, ChevronRight, Bot, Loader2, Check, AlertCircle, Wrench, Zap } from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';

export interface AgentEvent {
  type: string;
  agent_name?: string;
  run_id?: string;
  content?: string;
  message?: string;
  tool_call_id?: string;
  name?: string;
  result?: unknown;
  input_tokens?: number;
  output_tokens?: number;
  from_agent?: string;
  to_agent?: string;
  task?: string;
}

export interface AgentState {
  name: string;
  status: 'waiting' | 'running' | 'done' | 'error';
  content: string;
  toolCalls: { id: string; name: string; status: 'running' | 'done'; result?: unknown }[];
  inputTokens?: number;
  outputTokens?: number;
  runId?: string;
}

const STATUS_CONFIG = {
  waiting: { label: '等待中', cls: 'text-gray-400', dot: 'bg-gray-300' },
  running: { label: '运行中', cls: 'text-blue-500', dot: 'bg-blue-400 animate-pulse' },
  done:    { label: '已完成', cls: 'text-green-600', dot: 'bg-green-400' },
  error:   { label: '失败',   cls: 'text-red-500',  dot: 'bg-red-400' },
};

function AgentCard({ agent, agentIndex }: { agent: AgentState; agentIndex: number }) {
  const [expanded, setExpanded] = useState(agentIndex === 0);
  const st = STATUS_CONFIG[agent.status];

  return (
    <div className="border border-gray-200 rounded-xl overflow-hidden">
      {/* Header */}
      <button
        onClick={() => setExpanded(v => !v)}
        className="w-full flex items-center gap-2.5 px-4 py-2.5 bg-gray-50 hover:bg-gray-100 transition-colors text-left"
      >
        <span className={`w-2 h-2 rounded-full shrink-0 ${st.dot}`} />
        <Bot size={14} className="text-purple-500 shrink-0" />
        <span className="text-sm font-medium text-gray-700 flex-1">{agent.name}</span>
        <span className={`text-[11px] ${st.cls}`}>{st.label}</span>
        {agent.status === 'running' && <Loader2 size={12} className="animate-spin text-blue-400" />}
        {agent.status === 'done' && <Check size={12} className="text-green-500" />}
        {agent.status === 'error' && <AlertCircle size={12} className="text-red-500" />}
        {agent.inputTokens != null && (
          <span className="text-[10px] text-gray-400 hidden sm:inline">
            {agent.inputTokens}↑ {agent.outputTokens}↓
          </span>
        )}
        {expanded ? <ChevronDown size={13} className="text-gray-400" /> : <ChevronRight size={13} className="text-gray-400" />}
      </button>

      {/* Body */}
      {expanded && (
        <div className="px-4 py-3 bg-white space-y-2">
          {/* Tool calls */}
          {agent.toolCalls.length > 0 && (
            <div className="space-y-1">
              {agent.toolCalls.map(tc => (
                <div key={tc.id} className="flex items-center gap-1.5 text-xs text-gray-500 bg-gray-50 rounded-lg px-3 py-1.5">
                  <Wrench size={11} className="text-blue-400 shrink-0" />
                  <span className="font-medium">{tc.name}</span>
                  {tc.status === 'running'
                    ? <Loader2 size={10} className="animate-spin ml-auto" />
                    : <Check size={10} className="text-green-500 ml-auto" />}
                </div>
              ))}
            </div>
          )}

          {/* Content */}
          {agent.content ? (
            <div className="prose prose-sm max-w-none text-gray-700 text-sm">
              <ReactMarkdown remarkPlugins={[remarkGfm]}>{agent.content}</ReactMarkdown>
            </div>
          ) : agent.status === 'running' ? (
            <div className="flex items-center gap-1.5 text-sm text-gray-400">
              <Loader2 size={13} className="animate-spin" />
              <span>思考中…</span>
            </div>
          ) : null}

          {agent.status === 'error' && agent.content && (
            <div className="text-sm text-red-500 bg-red-50 rounded-lg px-3 py-2">
              {agent.content}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

export function useMultiAgentState(agentNames: string[]) {
  const [states, setStates] = useState<Record<string, AgentState>>(() =>
    Object.fromEntries(agentNames.map((name) => [name, {
      name, status: 'waiting', content: '', toolCalls: [],
    }]))
  );
  const [routes, setRoutes] = useState<{ from: string; to: string; task: string }[]>([]);
  const [done, setDone] = useState(false);

  function applyEvent(event: AgentEvent) {
    const name = event.agent_name;
    if (!name) {
      if (event.type === 'multi_agent_done') setDone(true);
      return;
    }

    setStates(prev => {
      const agent = prev[name] ?? { name, status: 'waiting', content: '', toolCalls: [] };
      let next = { ...agent };

      switch (event.type) {
        case 'agent_start':
          next.status = 'running';
          next.runId = event.run_id;
          break;
        case 'delta':
          next.content += event.content ?? '';
          break;
        case 'tool_start':
          next.toolCalls = [...next.toolCalls, {
            id: event.tool_call_id ?? '',
            name: event.name ?? '',
            status: 'running',
          }];
          break;
        case 'tool_result':
          next.toolCalls = next.toolCalls.map(tc =>
            tc.id === event.tool_call_id ? { ...tc, status: 'done', result: event.result } : tc
          );
          break;
        case 'agent_done':
          next.status = 'done';
          next.inputTokens = event.input_tokens;
          next.outputTokens = event.output_tokens;
          break;
        case 'agent_error':
          next.status = 'error';
          if (event.message) next.content = event.message;
          break;
      }
      return { ...prev, [name]: next };
    });

    if (event.type === 'agent_route' && event.from_agent && event.to_agent) {
      setRoutes(prev => [...prev, {
        from: event.from_agent!,
        to: event.to_agent!,
        task: event.task ?? '',
      }]);
    }
  }

  return { states, routes, done, applyEvent };
}

interface Props {
  agentNames: string[];
  mode: string;
  states: Record<string, AgentState>;
  routes: { from: string; to: string; task: string }[];
  done: boolean;
}

export default function MultiAgentBubble({ agentNames, mode, states, routes, done }: Props) {
  const orderedNames = useMemo(() =>
    agentNames.filter(n => n in states).sort((a, b) =>
      (states[a].status === 'done' ? 0 : 1) - (states[b].status === 'done' ? 0 : 1)
    ),
    [agentNames, states]
  );

  return (
    <div className="bg-white border border-gray-200 rounded-2xl shadow-sm overflow-hidden max-w-[90%]">
      {/* Header */}
      <div className="flex items-center gap-2 px-4 py-2.5 bg-gradient-to-r from-purple-50 to-blue-50 border-b border-gray-100">
        <Zap size={14} className="text-purple-500" />
        <span className="text-xs font-semibold text-purple-700">
          Multi-Agent {mode === 'sequential' ? '串行' : mode === 'parallel' ? '并行' : 'Supervisor'} 模式
        </span>
        <span className="ml-auto text-[11px] text-gray-400">
          {agentNames.length} 个 Agent
        </span>
        {done && <Check size={12} className="text-green-500" />}
      </div>

      {/* Route events (supervisor) */}
      {routes.length > 0 && (
        <div className="px-4 py-2 bg-blue-50 border-b border-blue-100 space-y-1">
          {routes.map((r, i) => (
            <div key={i} className="text-[11px] text-blue-600 flex items-center gap-1">
              <span className="font-medium">{r.from}</span>
              <span>→</span>
              <span className="font-medium">{r.to}</span>
              <span className="text-blue-400 truncate ml-1">{r.task.slice(0, 60)}</span>
            </div>
          ))}
        </div>
      )}

      {/* Agent cards */}
      <div className="p-3 space-y-2">
        {orderedNames.map((name, idx) => (
          <AgentCard key={name} agent={states[name]} agentIndex={idx} />
        ))}
      </div>
    </div>
  );
}
