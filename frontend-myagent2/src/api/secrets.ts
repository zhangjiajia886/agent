import { get, post, put, del } from './client';

export interface SecretDTO {
  id: string;
  name: string;
  description: string;
  created_at: string;
  updated_at: string;
}

export const secretApi = {
  list:   () => get<{ items: SecretDTO[] }>('/api/secrets'),
  create: (data: { name: string; value: string; description?: string }) =>
    post<{ id: string }>('/api/secrets', data),
  update: (name: string, data: { value?: string; description?: string }) =>
    put<{ ok: boolean }>(`/api/secrets/${name}`, data),
  delete: (name: string) => del<{ ok: boolean }>(`/api/secrets/${name}`),
};
