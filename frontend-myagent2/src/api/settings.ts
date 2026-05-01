import { get, put, post, del } from './client';

export const settingsApi = {
  list:   () => get<{ items: Record<string, unknown>; defaults: Record<string, unknown> }>('/api/settings'),
  get:    (key: string) => get<{ key: string; value: unknown }>(`/api/settings/${key}`),
  update: (key: string, value: unknown) => put<{ ok: boolean }>(`/api/settings/${key}`, { value }),
  delete: (key: string) => del<{ ok: boolean }>(`/api/settings/${key}`),
  reset:  () => post<{ ok: boolean; defaults: Record<string, unknown> }>('/api/settings/reset'),
};
