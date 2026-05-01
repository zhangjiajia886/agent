import { get, post, put, del } from './client';

export interface WorkflowDTO {
  id: string;
  name: string;
  description: string;
  definition: Record<string, unknown>;
  status: string;
  tags: string[];
  version: number;
  created_at: string;
  updated_at: string;
}

interface ListResult { items: WorkflowDTO[]; total: number }

export const workflowApi = {
  list:   (params?: { search?: string; status?: string; skip?: number; limit?: number }) => {
    const q = new URLSearchParams();
    if (params?.search) q.set('search', params.search);
    if (params?.status) q.set('status', params.status);
    if (params?.skip)   q.set('skip', String(params.skip));
    if (params?.limit)  q.set('limit', String(params.limit));
    const qs = q.toString();
    return get<ListResult>(`/api/workflows${qs ? `?${qs}` : ''}`);
  },
  get:    (id: string) => get<WorkflowDTO>(`/api/workflows/${id}`),
  create: (data: { name: string; description?: string; definition?: Record<string, unknown>; tags?: string[] }) =>
    post<{ id: string }>('/api/workflows', data),
  update: (id: string, data: Partial<Pick<WorkflowDTO, 'name' | 'description' | 'definition' | 'tags' | 'status'>>) =>
    put<{ ok: boolean }>(`/api/workflows/${id}`, data),
  delete: (id: string) => del<{ ok: boolean }>(`/api/workflows/${id}`),
  clone:  (id: string) => post<{ id: string }>(`/api/workflows/${id}/clone`),
  execute: (id: string, inputs?: Record<string, unknown>) =>
    post<{ execution_id: string; status: string }>(`/api/workflows/${id}/execute`, { inputs: inputs ?? {} }),
};
