import { get, post, put, del } from './client';

export interface AppVariable {
  key: string;
  label: string;
  type: 'text' | 'textarea' | 'select';
  required: boolean;
  default: string;
  options?: string[];
}

export interface AppDTO {
  id: string;
  name: string;
  description: string;
  icon: string;
  opening_msg: string;
  system_prompt: string;
  variables: AppVariable[];
  tools: string[];
  model: string;
  model_params: Record<string, unknown>;
  is_published: boolean;
  created_at: string;
  updated_at: string;
}

export interface AppSession {
  id: string;
  app_id: string;
  title: string;
  created_at: string;
}

export interface AppMessage {
  id: string;
  session_id: string;
  role: 'user' | 'assistant' | 'tool';
  content: string;
  tool_calls?: unknown[];
  metadata?: Record<string, unknown>;
  created_at: string;
}

export type AppCreateBody = Pick<AppDTO, 'name' | 'description' | 'icon' | 'opening_msg' | 'system_prompt' | 'variables' | 'tools' | 'model'>;
export type AppUpdateBody = Partial<AppCreateBody & { is_published: boolean; model_params: Record<string, unknown> }>;

const API_BASE = (import.meta as unknown as { env: Record<string, string> }).env?.VITE_API_BASE ?? 'http://localhost:8001';

export const appApi = {
  list: () => get<{ items: AppDTO[] }>('/api/apps'),
  get:  (id: string) => get<AppDTO>(`/api/apps/${id}`),
  create: (data: Partial<AppCreateBody> & { name: string }) =>
    post<AppDTO>('/api/apps', data),
  update: (id: string, data: AppUpdateBody) =>
    put<AppDTO>(`/api/apps/${id}`, data),
  delete: (id: string) => del<{ ok: boolean }>(`/api/apps/${id}`),
  createSession: (appId: string) =>
    post<AppSession>(`/api/apps/${appId}/sessions`, {}),
  listSessions: (appId: string) =>
    get<{ items: AppSession[] }>(`/api/apps/${appId}/sessions`),
  getMessages: (appId: string, sessionId: string) =>
    get<{ items: AppMessage[] }>(`/api/apps/${appId}/sessions/${sessionId}/messages`),
};

async function* _sseGen(url: string, body: unknown, signal?: AbortSignal) {
  const res = await fetch(`${API_BASE}${url}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
    signal,
  });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  const reader = res.body!.getReader();
  const dec = new TextDecoder();
  let buf = '';
  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buf += dec.decode(value, { stream: true });
    const lines = buf.split('\n');
    buf = lines.pop()!;
    for (const line of lines) {
      if (line.startsWith('data: ')) {
        try { yield JSON.parse(line.slice(6)); } catch { /* skip */ }
      }
    }
  }
}

export function streamAppChat(
  appId: string, sessionId: string, content: string,
  varValues: Record<string, string> = {}, signal?: AbortSignal,
) {
  return _sseGen(
    `/api/apps/${appId}/sessions/${sessionId}/chat`,
    { content, session_id: sessionId, var_values: varValues },
    signal,
  );
}

export function streamPreviewChat(
  appId: string, sessionId: string, content: string,
  appConfig: Partial<AppDTO>, varValues: Record<string, string> = {}, signal?: AbortSignal,
) {
  return _sseGen(
    `/api/apps/${appId}/preview/chat`,
    { content, session_id: sessionId, var_values: varValues, app_config: appConfig },
    signal,
  );
}
