import { get, post, put, del } from './client';

export interface McpServerDTO {
  id: string;
  name: string;
  command: string;
  args: string[];
  env: Record<string, string>;
  auto_start: boolean;
  status: string;
  tools_count: number;
  tools: unknown[];
  created_at: string;
  updated_at: string;
}

export const mcpApi = {
  list:       () => get<{ items: McpServerDTO[] }>('/api/mcp'),
  get:        (id: string) => get<McpServerDTO>(`/api/mcp/${id}`),
  create:     (data: { name: string; command: string; args?: string[]; env?: Record<string, string>; auto_start?: boolean }) =>
    post<{ id: string }>('/api/mcp', data),
  update:     (id: string, data: Partial<Pick<McpServerDTO, 'command' | 'args' | 'env' | 'auto_start'>>) =>
    put<{ ok: boolean }>(`/api/mcp/${id}`, data),
  delete:     (id: string) => del<{ ok: boolean }>(`/api/mcp/${id}`),
  connect:    (id: string) => post<{ ok: boolean }>(`/api/mcp/${id}/connect`),
  disconnect: (id: string) => post<{ ok: boolean }>(`/api/mcp/${id}/disconnect`),
};
