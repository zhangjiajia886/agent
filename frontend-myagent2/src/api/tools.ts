import { get, post } from './client';

export interface ToolDTO {
  name: string;
  description: string;
  category: string;
  type: string;
  risk_level: string;
  input_schema: Record<string, unknown>;
  is_enabled: boolean;
  call_count?: number;
  avg_duration_ms?: number;
}

export const toolApi = {
  list: (params?: { category?: string; search?: string }) => {
    const q = new URLSearchParams();
    if (params?.category) q.set('category', params.category);
    if (params?.search)   q.set('search', params.search);
    const qs = q.toString();
    return get<{ items: ToolDTO[] }>(`/api/tools${qs ? `?${qs}` : ''}`);
  },
  test: (name: string, args: Record<string, unknown>) =>
    post<{ result?: unknown; error?: string }>(`/api/tools/${name}/test`, { arguments: args }),
};
