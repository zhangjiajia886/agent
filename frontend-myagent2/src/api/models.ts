import { get, post, put, del } from './client';

export interface ModelDTO {
  id: string;
  provider: string;
  name: string;
  model_id: string;
  api_base: string;
  api_key_ref: string;
  is_default: boolean;
  max_tokens: number;
  config: Record<string, unknown>;
  created_at: string;
  updated_at: string;
}

export const modelApi = {
  list:       (provider?: string) => get<{ items: ModelDTO[] }>(`/api/models${provider ? `?provider=${provider}` : ''}`),
  create:     (data: { provider: string; name: string; model_id: string; api_base?: string; api_key_ref?: string; is_default?: boolean; max_tokens?: number; config?: Record<string, unknown> }) =>
    post<{ id: string }>('/api/models', data),
  update:     (id: string, data: Partial<Pick<ModelDTO, 'name' | 'api_base' | 'api_key_ref' | 'is_default' | 'max_tokens' | 'config'>>) =>
    put<{ ok: boolean }>(`/api/models/${id}`, data),
  delete:     (id: string) => del<{ ok: boolean }>(`/api/models/${id}`),
  setDefault: (id: string) => post<{ ok: boolean }>(`/api/models/${id}/set-default`),
  available:  () => get<{ items: { id: string; name: string; size: number }[] }>('/api/models/available'),
};
