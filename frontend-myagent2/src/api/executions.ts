import { get, post, del } from './client';

export interface ExecutionDTO {
  id: string;
  workflow_id: string;
  workflow_name: string;
  status: string;
  inputs: Record<string, unknown>;
  outputs: Record<string, unknown>;
  node_statuses: Record<string, unknown>;
  logs: unknown[];
  error: string;
  started_at: string;
  finished_at: string;
  total_tokens: number;
  total_cost: number;
  created_at: string;
}

interface ListResult { items: ExecutionDTO[]; total: number }

export const executionApi = {
  list: (params?: { workflow_id?: string; status?: string; skip?: number; limit?: number }) => {
    const q = new URLSearchParams();
    if (params?.workflow_id) q.set('workflow_id', params.workflow_id);
    if (params?.status)      q.set('status', params.status);
    if (params?.skip)        q.set('skip', String(params.skip));
    if (params?.limit)       q.set('limit', String(params.limit));
    const qs = q.toString();
    return get<ListResult>(`/api/executions${qs ? `?${qs}` : ''}`);
  },
  get:     (id: string) => get<ExecutionDTO>(`/api/executions/${id}`),
  traces:  (id: string) => get<{ items: unknown[] }>(`/api/executions/${id}/traces`),
  cancel:  (id: string) => post<{ ok: boolean }>(`/api/executions/${id}/cancel`),
  kill:    (id: string) => post<{ ok: boolean }>(`/api/executions/${id}/kill`),
  getCheckpoint: (id: string) => get<CheckpointInfo>(`/api/executions/${id}/checkpoint`),
  deleteCheckpoint: (id: string) => del<{ ok: boolean }>(`/api/executions/${id}/checkpoint`),
  resume:  (id: string) => post<{ execution_id: string; status: string; resumed: boolean }>(
    `/api/executions/${id}/resume`, {}
  ),
};

export interface CheckpointInfo {
  has_checkpoint: boolean;
  checkpoint_id?: string;
  last_node_id?: string;
  completed_nodes: string[];
  completed_count: number;
  total_nodes?: number;
  progress_pct?: number;
  checkpoint_at?: string;
}

export interface AgentRun {
  id: string;
  execution_id: string;
  agent_name: string;
  agent_index: number;
  status: string;
  model?: string;
  input_tokens?: number;
  output_tokens?: number;
  started_at?: string;
  finished_at?: string;
  created_at: string;
}

export const agentRunsApi = {
  list: (execution_id?: string) => {
    const q = execution_id ? `?execution_id=${execution_id}` : '';
    return get<{ items: AgentRun[] }>(`/api/agent-runs${q}`);
  },
  get: (run_id: string) => get<AgentRun & { messages: unknown[] }>(`/api/agent-runs/${run_id}`),
  byExecution: (execution_id: string) =>
    get<{ items: AgentRun[] }>(`/api/agent-runs/by-execution/${execution_id}`),
};

export interface MultiAgentConfig {
  name: string;
  system_prompt?: string;
  model?: string;
  allowed_tools?: string[];
  input_var?: string;
  output_var?: string;
}

export function streamMultiAgent(
  session_id: string,
  mode: string,
  agents: MultiAgentConfig[],
  user_content: string,
  signal?: AbortSignal,
): AsyncIterable<Record<string, unknown>> {
  return {
    [Symbol.asyncIterator]: async function* () {
      const resp = await fetch(`/api/chat/sessions/${session_id}/multi-agent`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ mode, agents, user_content }),
        signal,
      });
      if (!resp.ok || !resp.body) return;
      const reader = resp.body.getReader();
      const decoder = new TextDecoder();
      let buf = '';
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buf += decoder.decode(value, { stream: true });
        const lines = buf.split('\n');
        buf = lines.pop() ?? '';
        for (const line of lines) {
          if (line.startsWith('data: ')) {
            try { yield JSON.parse(line.slice(6)); } catch {}
          }
        }
      }
    },
  };
}
