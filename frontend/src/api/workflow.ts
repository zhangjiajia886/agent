/**
 * 工作流 DAG 引擎 API
 */
import request from '@/api/request'

// ──────────── 类型定义 ────────────

export interface WorkflowDefinition {
  id: string
  name: string
  description?: string
  definition: WorkflowDef
  is_enabled: boolean
  created_at?: string
  updated_at?: string
}

export interface WorkflowDef {
  nodes: WfNode[]
  edges: WfEdge[]
  variables: Record<string, any>
}

export interface WfNode {
  id: string
  type: string
  data: Record<string, any>
  position?: { x: number; y: number }
}

export interface WfEdge {
  source: string
  target: string
  sourceHandle?: string
}

export interface WorkflowExecution {
  id: string
  workflow_id: string
  user_id?: string
  status: 'running' | 'done' | 'error' | 'cancelled'
  inputs?: Record<string, any>
  outputs?: Record<string, any>
  node_statuses?: Record<string, any>
  started_at?: string
  finished_at?: string
}

export interface CheckpointInfo {
  has_checkpoint: boolean
  checkpoint_id?: string
  last_node_id?: string
  completed_nodes: string[]
  completed_count: number
  checkpoint_at?: string
}

// ──────────── REST API ────────────

export function listWorkflows(): Promise<WorkflowDefinition[]> {
  return request.get('/v1/workflows/dag')
}

export function getWorkflow(id: string): Promise<WorkflowDefinition> {
  return request.get(`/v1/workflows/dag/${id}`)
}

export function createWorkflow(data: {
  name: string
  description?: string
  definition: WorkflowDef
}): Promise<WorkflowDefinition> {
  return request.post('/v1/workflows/dag', data)
}

export function updateWorkflow(id: string, data: Partial<{
  name: string
  description: string
  definition: WorkflowDef
  is_enabled: boolean
}>): Promise<WorkflowDefinition> {
  return request.put(`/v1/workflows/dag/${id}`, data)
}

export function deleteWorkflow(id: string): Promise<void> {
  return request.delete(`/v1/workflows/dag/${id}`)
}

export function executeWorkflow(id: string, inputs: Record<string, any> = {}): Promise<WorkflowExecution> {
  return request.post(`/v1/workflows/dag/${id}/execute`, { inputs })
}

export function listExecutions(wfId: string): Promise<WorkflowExecution[]> {
  return request.get(`/v1/workflows/dag/${wfId}/executions`)
}

export function getExecution(execId: string): Promise<WorkflowExecution> {
  return request.get(`/v1/workflows/executions/${execId}`)
}

export function getCheckpointInfo(execId: string): Promise<CheckpointInfo> {
  return request.get(`/v1/workflows/executions/${execId}/checkpoint`)
}

export function resumeExecution(execId: string): Promise<WorkflowExecution> {
  return request.post(`/v1/workflows/executions/${execId}/resume`)
}

// ──────────── WebSocket 执行 ────────────

export interface WfEvent {
  type: 'execution_started' | 'execution_finished' | 'execution_error'
    | 'node_status' | 'llm_stream' | 'loop_iteration' | 'done' | 'error'
  execution_id?: string
  node_id?: string
  status?: string
  delta?: string
  error?: string
  content?: string
  [key: string]: any
}

export function connectWorkflowWS(
  wfId: string,
  inputs: Record<string, any>,
  onEvent: (event: WfEvent) => void,
  onDone?: () => void,
  resume = false,
  executionId?: string,
): WebSocket {
  const proto = location.protocol === 'https:' ? 'wss:' : 'ws:'
  const token = localStorage.getItem('access_token') || ''
  const ws = new WebSocket(`${proto}//${location.host}/api/v1/workflows/dag/${wfId}/ws?token=${token}`)

  ws.onopen = () => {
    ws.send(JSON.stringify({ inputs, resume, execution_id: executionId }))
  }

  ws.onmessage = (e) => {
    try {
      const event: WfEvent = JSON.parse(e.data)
      onEvent(event)
      if (event.type === 'done' || event.type === 'execution_finished') {
        onDone?.()
      }
    } catch { /* ignore parse errors */ }
  }

  ws.onerror = () => {
    onEvent({ type: 'error', content: 'WebSocket 连接失败' })
    onDone?.()
  }

  ws.onclose = () => onDone?.()

  return ws
}
