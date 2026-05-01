import { get, post, del } from './client';

export interface Schedule {
  id: string;
  workflow_id: string;
  app_id?: string | null;
  created_by?: string | null;
  name: string;
  cron_expr: string;
  timezone: string;
  inputs?: Record<string, unknown> | null;
  is_enabled: number;
  last_run_at?: string | null;
  last_run_status?: string | null;
  next_run_at?: string | null;
  run_count: number;
  fail_count: number;
  created_at: string;
  updated_at: string;
}

export interface ScheduleCreate {
  workflow_id: string;
  name: string;
  cron_expr: string;
  timezone?: string;
  inputs?: Record<string, unknown>;
  app_id?: string;
}

export const schedulesApi = {
  list: (params?: { workflow_id?: string; enabled_only?: boolean }) => {
    const qs = new URLSearchParams();
    if (params?.workflow_id) qs.set('workflow_id', params.workflow_id);
    if (params?.enabled_only) qs.set('enabled_only', 'true');
    const q = qs.toString() ? `?${qs.toString()}` : '';
    return get<{ items: Schedule[] }>(`/api/schedules${q}`);
  },

  create: (data: ScheduleCreate) =>
    post<{ id: string; created_at: string }>('/api/schedules', data),

  get: (id: string) => get<Schedule>(`/api/schedules/${id}`),

  update: (id: string, data: Partial<Pick<Schedule, 'name' | 'cron_expr' | 'timezone' | 'inputs' | 'is_enabled'>>) =>
    fetch(`/api/schedules/${id}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data),
    }).then(r => r.json() as Promise<{ ok: boolean }>),

  toggle: (id: string) =>
    post<{ ok: boolean; is_enabled: boolean }>(`/api/schedules/${id}/toggle`, {}),

  delete: (id: string) => del<{ ok: boolean }>(`/api/schedules/${id}`),
};
