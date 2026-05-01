import { get } from './client';

export interface UsageItem {
  stat_date: string;
  model: string;
  input_tokens: number;
  output_tokens: number;
  messages: number;
  tool_calls: number;
}

export interface UsageSummary {
  total_input: number;
  total_output: number;
  total_messages: number;
  total_tokens: number;
}

export interface ModelUsage {
  model: string;
  input_tokens: number;
  output_tokens: number;
  messages: number;
  tool_calls: number;
}

export interface UserUsage {
  user_id: string;
  input_tokens: number;
  output_tokens: number;
  messages: number;
}

export const analyticsApi = {
  getUsage: (params?: { days?: number; user_id?: string; model?: string }) => {
    const qs = new URLSearchParams();
    if (params?.days) qs.set('days', String(params.days));
    if (params?.user_id) qs.set('user_id', params.user_id);
    if (params?.model) qs.set('model', params.model);
    const q = qs.toString() ? `?${qs.toString()}` : '';
    return get<{ items: UsageItem[]; summary: UsageSummary }>(`/api/analytics/usage${q}`);
  },

  getByModel: (days = 30) =>
    get<{ items: ModelUsage[] }>(`/api/analytics/usage/models?days=${days}`),

  getByUser: (days = 30, limit = 20) =>
    get<{ items: UserUsage[] }>(`/api/analytics/usage/users?days=${days}&limit=${limit}`),
};
