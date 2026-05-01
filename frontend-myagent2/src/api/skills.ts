import { get, post, put, del } from './client';

export interface SkillDTO {
  id: string;
  name: string;
  description: string;
  category: string;
  content: string;
  tags: string[];
  is_builtin: boolean;
  source_type: string;
  source_path: string;
  source_repo: string;
  allowed_tools: string[];
  arguments: string[];
  argument_hint: string;
  when_to_use: string;
  context_mode: string;
  agent: string;
  model: string;
  variables: string[];
  required_tools: string[];
  migration_status: string;
  migration_notes: string;
  content_hash: string;
  created_at: string;
  updated_at: string;
}

export interface SkillListParams {
  category?: string;
  search?: string;
  source_type?: string;
  migration_status?: string;
  context_mode?: string;
}

export interface SkillStats {
  total: number;
  by_source_type: Record<string, number>;
  by_migration_status: Record<string, number>;
  by_context_mode: Record<string, number>;
}

export interface InvocationRecord {
  id: string;
  skill_id: string;
  session_id: string;
  execution_mode: string;
  args_text: string;
  status: string;
  duration_ms: number;
  result_preview: string;
  invoked_at: string;
}

export const skillApi = {
  list: (params?: SkillListParams) => {
    const q = new URLSearchParams();
    if (params?.category)         q.set('category', params.category);
    if (params?.search)           q.set('search', params.search);
    if (params?.source_type)      q.set('source_type', params.source_type);
    if (params?.migration_status) q.set('migration_status', params.migration_status);
    if (params?.context_mode)     q.set('context_mode', params.context_mode);
    const qs = q.toString();
    return get<{ items: SkillDTO[] }>(`/api/skills${qs ? `?${qs}` : ''}`);
  },
  get:    (id: string) => get<SkillDTO>(`/api/skills/${id}`),
  create: (data: Omit<SkillDTO, 'id' | 'created_at' | 'updated_at'>) =>
    post<{ id: string }>('/api/skills', data),
  update: (id: string, data: Partial<SkillDTO>) =>
    put<{ ok: boolean }>(`/api/skills/${id}`, data),
  delete: (id: string) => del<{ ok: boolean }>(`/api/skills/${id}`),
  stats:  () => get<SkillStats>('/api/skills/stats'),
  importBatch: (data: Omit<SkillDTO, 'id' | 'created_at' | 'updated_at'>[]) =>
    post<{ inserted: number; skipped: number }>('/api/skills/import', data),
  invoke: (skillId: string, data?: Record<string, unknown>) =>
    post<{ id: string }>(`/api/skills/${skillId}/invoke`, data ?? {}),
  invocations: (skillId: string, limit = 50) =>
    get<{ items: InvocationRecord[] }>(`/api/skills/${skillId}/invocations?limit=${limit}`),
};
