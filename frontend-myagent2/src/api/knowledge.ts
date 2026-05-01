import { get, post, put, del } from './client';

export interface KnowledgeDTO {
  id: string;
  name: string;
  description: string;
  type: string;
  config: Record<string, unknown>;
  doc_count: number;
  status: string;
  created_at: string;
  updated_at: string;
}

export const knowledgeApi = {
  list:   (search?: string) => get<{ items: KnowledgeDTO[] }>(`/api/knowledge${search ? `?search=${search}` : ''}`),
  get:    (id: string) => get<KnowledgeDTO>(`/api/knowledge/${id}`),
  create: (data: { name: string; description?: string; type?: string; config?: Record<string, unknown> }) =>
    post<{ id: string }>('/api/knowledge', data),
  update: (id: string, data: Partial<Pick<KnowledgeDTO, 'name' | 'description' | 'config' | 'status'>>) =>
    put<{ ok: boolean }>(`/api/knowledge/${id}`, data),
  delete: (id: string) => del<{ ok: boolean }>(`/api/knowledge/${id}`),
};
