import { get, post, put, del } from './client';

export interface ChatSession {
  id: string;
  title: string;
  model: string;
  system_prompt: string;
  metadata: Record<string, unknown>;
  created_at: string;
  updated_at: string;
}

export interface ChatMessage {
  id: string;
  session_id: string;
  role: 'user' | 'assistant' | 'tool' | 'system';
  content: string;
  thinking_content?: string | null;
  model?: string | null;
  input_tokens?: number;
  output_tokens?: number;
  latency_ms?: number;
  tool_rounds?: number;
  tool_calls?: ToolCallInfo[] | null;
  tool_call_id?: string | null;
  name?: string;
  metadata?: Record<string, unknown>;
  created_at: string;
}

export interface ToolCallInfo {
  id: string;
  type: string;
  function: {
    name: string;
    arguments: string;
  };
}

export interface SessionDetail extends ChatSession {
  messages: ChatMessage[];
}

export interface SSEEvent {
  type: 'delta' | 'tool_start' | 'tool_result' | 'tool_calls' | 'done' | 'error';
  content?: string;
  name?: string;
  tool_call_id?: string;
  arguments?: Record<string, unknown>;
  result?: Record<string, unknown>;
  tool_calls?: ToolCallInfo[];
  message?: string;
  metadata?: Record<string, unknown>;
}

export const chatApi = {
  listSessions: () =>
    get<{ items: ChatSession[] }>('/api/chat/sessions'),

  createSession: (data?: { title?: string; model?: string; system_prompt?: string }) =>
    post<{ id: string; title: string; created_at: string }>('/api/chat/sessions', data ?? {}),

  getSession: (id: string) =>
    get<SessionDetail>(`/api/chat/sessions/${id}`),

  updateSession: (id: string, data: { title?: string; model?: string; system_prompt?: string }) =>
    put<{ ok: boolean }>(`/api/chat/sessions/${id}`, data),

  deleteSession: (id: string) =>
    del<{ ok: boolean }>(`/api/chat/sessions/${id}`),
};

/**
 * Send a message and receive SSE events via streaming.
 * Returns an async generator of SSEEvent objects.
 */
export async function* sendMessage(
  sessionId: string,
  content: string,
  model?: string,
): AsyncGenerator<SSEEvent> {
  const body: Record<string, string> = { content };
  if (model) body.model = model;

  const response = await fetch(`/api/chat/sessions/${sessionId}/messages`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });

  if (!response.ok) {
    const text = await response.text().catch(() => '');
    yield { type: 'error', message: text || response.statusText };
    return;
  }

  const reader = response.body?.getReader();
  if (!reader) {
    yield { type: 'error', message: 'No response body' };
    return;
  }

  const decoder = new TextDecoder();
  let buffer = '';

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;

    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split('\n');
    buffer = lines.pop() || '';

    for (const line of lines) {
      const trimmed = line.trim();
      if (trimmed.startsWith('data: ')) {
        const jsonStr = trimmed.slice(6);
        try {
          const event: SSEEvent = JSON.parse(jsonStr);
          yield event;
        } catch {
          // skip malformed JSON
        }
      }
    }
  }

  // Process remaining buffer
  if (buffer.trim().startsWith('data: ')) {
    try {
      const event: SSEEvent = JSON.parse(buffer.trim().slice(6));
      yield event;
    } catch {
      // skip
    }
  }
}
