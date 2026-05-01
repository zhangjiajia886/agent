import { get, post, del } from './client';

export interface EvalDataset {
  id: string;
  name: string;
  description?: string;
  app_id?: string | null;
  created_by?: string | null;
  created_at: string;
}

export interface EvalCase {
  id: string;
  dataset_id: string;
  question: string;
  expected_answer?: string;
  context?: string;
  tags?: string;
  difficulty: string;
  created_at: string;
}

export interface EvalRun {
  id: string;
  dataset_id: string;
  app_id?: string | null;
  model?: string | null;
  label?: string;
  status: string;
  total_cases: number;
  passed_cases: number;
  avg_score?: number | null;
  avg_latency_ms?: number | null;
  total_tokens: number;
  started_at?: string | null;
  finished_at?: string | null;
  created_at: string;
  results?: EvalResult[];
}

export interface EvalResult {
  id: number;
  run_id: string;
  case_id: string;
  actual_answer?: string;
  score?: number | null;
  passed: number;
  eval_method?: string;
  judge_reasoning?: string;
  latency_ms?: number | null;
  input_tokens?: number | null;
  output_tokens?: number | null;
  error?: string | null;
  created_at: string;
}

export const evalsApi = {
  listDatasets: (app_id?: string) => {
    const q = app_id ? `?app_id=${app_id}` : '';
    return get<{ items: EvalDataset[] }>(`/api/evals/datasets${q}`);
  },
  createDataset: (data: { name: string; description?: string; app_id?: string }) =>
    post<{ id: string; created_at: string }>('/api/evals/datasets', data),
  deleteDataset: (id: string) => del<{ ok: boolean }>(`/api/evals/datasets/${id}`),

  listCases: (dataset_id: string, limit = 100, offset = 0) =>
    get<{ items: EvalCase[]; total: number }>(
      `/api/evals/datasets/${dataset_id}/cases?limit=${limit}&offset=${offset}`
    ),
  createCase: (data: { dataset_id: string; question: string; expected_answer?: string; tags?: string; difficulty?: string }) =>
    post<{ id: string; created_at: string }>('/api/evals/cases', data),
  deleteCase: (id: string) => del<{ ok: boolean }>(`/api/evals/cases/${id}`),

  listRuns: (dataset_id?: string) => {
    const q = dataset_id ? `?dataset_id=${dataset_id}` : '';
    return get<{ items: EvalRun[] }>(`/api/evals/runs${q}`);
  },
  createRun: (data: { dataset_id: string; app_id?: string; model?: string; label?: string }) =>
    post<{ id: string; total_cases: number; created_at: string }>('/api/evals/runs', data),
  getRun: (id: string) => get<EvalRun>(`/api/evals/runs/${id}`),
  deleteRun: (id: string) => del<{ ok: boolean }>(`/api/evals/runs/${id}`),
};
