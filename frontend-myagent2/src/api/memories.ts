import { get, post, put, del } from './client';

export interface Memory {
  id: string;
  title: string;
  content: string;
  type: string;
  scope: string;
  scope_id?: string | null;
  tags?: string | null;
  version: number;
  prev_id?: string | null;
  is_active: number;
  created_by?: string | null;
  source_session_id?: string | null;
  source_message_id?: string | null;
  created_at: string;
  updated_at: string;
}

export interface MemoryListResponse {
  items: Memory[];
  total: number;
}

export interface MemoryCreate {
  title: string;
  content: string;
  type?: string;
  tags?: string;
  scope?: string;
  scope_id?: string;
  created_by?: string;
  source_session_id?: string;
  source_message_id?: string;
}

export const memoriesApi = {
  list: (params?: {
    scope?: string;
    scope_id?: string;
    type?: string;
    tags?: string;
    created_by?: string;
    limit?: number;
    offset?: number;
  }) => {
    const qs = new URLSearchParams();
    if (params) {
      Object.entries(params).forEach(([k, v]) => {
        if (v !== undefined && v !== '') qs.set(k, String(v));
      });
    }
    const query = qs.toString() ? `?${qs.toString()}` : '';
    return get<MemoryListResponse>(`/api/memories${query}`);
  },

  create: (data: MemoryCreate) =>
    post<{ id: string; created_at: string }>('/api/memories', data),

  get: (id: string, includeHistory = false) =>
    get<Memory & { history?: Memory[] }>(
      `/api/memories/${id}${includeHistory ? '?include_history=true' : ''}`
    ),

  update: (id: string, data: Partial<Pick<Memory, 'title' | 'content' | 'type' | 'tags'>>) =>
    put<{ id: string; prev_id: string; updated_at: string }>(`/api/memories/${id}`, data),

  delete: (id: string) =>
    del<{ ok: boolean }>(`/api/memories/${id}`),
};
