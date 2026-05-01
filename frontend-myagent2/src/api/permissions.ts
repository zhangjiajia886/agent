import { get, post, put, del } from './client';

export interface PermissionDTO {
  id: string;
  tool_name: string;
  policy: string;
  conditions: Record<string, unknown>;
  description: string;
  priority: number;
  is_enabled: boolean;
  created_at: string;
}

export const permissionApi = {
  list:   () => get<{ items: PermissionDTO[]; defaults: Record<string, string> }>('/api/permissions'),
  create: (data: { tool_name: string; policy?: string; conditions?: Record<string, unknown>; description?: string; priority?: number; is_enabled?: boolean }) =>
    post<{ id: string }>('/api/permissions', data),
  update: (id: string, data: Partial<Pick<PermissionDTO, 'policy' | 'conditions' | 'description' | 'priority' | 'is_enabled'>>) =>
    put<{ ok: boolean }>(`/api/permissions/${id}`, data),
  delete: (id: string) => del<{ ok: boolean }>(`/api/permissions/${id}`),
  resetDefaults: () => post<{ ok: boolean }>('/api/permissions/reset-defaults'),
};
