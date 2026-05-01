import { get, post, del } from './client';

export type TaskStatus = 'pending' | 'in_progress' | 'completed' | 'cancelled' | 'failed';
export type TaskPriority = 'low' | 'medium' | 'high' | 'urgent';

export interface Task {
  id: string;
  parent_id?: string | null;
  root_id: string;
  depth: number;
  order_index: number;
  title: string;
  description?: string | null;
  status: TaskStatus;
  priority: TaskPriority;
  session_id?: string | null;
  session_type?: string | null;
  execution_id?: string | null;
  tool_hint?: string | null;
  due_at?: string | null;
  started_at?: string | null;
  finished_at?: string | null;
  result?: string | null;
  children?: Task[];
  created_at: string;
  updated_at: string;
}

export interface TaskCreate {
  title: string;
  description?: string;
  priority?: TaskPriority;
  parent_id?: string;
  session_id?: string;
  session_type?: string;
  execution_id?: string;
  tool_hint?: string;
  due_at?: string;
}

export interface TaskUpdate {
  title?: string;
  description?: string;
  status?: TaskStatus;
  priority?: TaskPriority;
  result?: string;
  progress?: number;
}

export const tasksApi = {
  list: (params?: {
    session_id?: string;
    session_type?: string;
    status?: string;
    execution_id?: string;
    root_only?: boolean;
    limit?: number;
  }) => {
    const qs = new URLSearchParams();
    if (params) {
      Object.entries(params).forEach(([k, v]) => {
        if (v !== undefined && v !== '') qs.set(k, String(v));
      });
    }
    const query = qs.toString() ? `?${qs.toString()}` : '';
    return get<{ items: Task[] }>(`/api/tasks${query}`);
  },

  create: (data: TaskCreate) =>
    post<{ id: string; root_id: string; depth: number; created_at: string }>('/api/tasks', data),

  get: (id: string) =>
    get<Task>(`/api/tasks/${id}`),

  tree: (id: string) =>
    get<Task>(`/api/tasks/${id}/tree`),

  update: (id: string, data: TaskUpdate) =>
    fetch(`/api/tasks/${id}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data),
    }).then(r => r.json() as Promise<{ ok: boolean; updated_at: string }>),

  delete: (id: string) =>
    del<{ ok: boolean }>(`/api/tasks/${id}`),
};
