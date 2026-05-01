import { get, post, put, del } from './client';

export interface PromptDTO {
  id: string;
  name: string;
  description: string;
  type: string;
  content: string;
  variables: string[];
  tags: string[];
  is_builtin: boolean;
  created_at: string;
  updated_at: string;
}

export const promptApi = {
  list:   (params?: { type?: string; search?: string }) => {
    const q = new URLSearchParams();
    if (params?.type)   q.set('type', params.type);
    if (params?.search) q.set('search', params.search);
    const qs = q.toString();
    return get<{ items: PromptDTO[] }>(`/api/prompts${qs ? `?${qs}` : ''}`);
  },
  get:    (id: string) => get<PromptDTO>(`/api/prompts/${id}`),
  create: (data: { name: string; description?: string; type?: string; content?: string; variables?: string[]; tags?: string[] }) =>
    post<{ id: string }>('/api/prompts', data),
  update: (id: string, data: Partial<Pick<PromptDTO, 'name' | 'description' | 'type' | 'content' | 'variables' | 'tags'>>) =>
    put<{ ok: boolean }>(`/api/prompts/${id}`, data),
  delete: (id: string) => del<{ ok: boolean }>(`/api/prompts/${id}`),
};
