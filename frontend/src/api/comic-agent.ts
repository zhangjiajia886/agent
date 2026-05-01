/**
 * 漫剧 Agent API — 对接后端 REST + WebSocket
 */
import request from '@/api/request'

// ──────────── 事件类型定义 ────────────

export interface AgentEvent {
  type: 'text' | 'delta' | 'tool_start' | 'tool_done' | 'tool_confirm' | 'error' | 'done' | 'conversation_created' | 'thinking' | 'incomplete' | 'task_created' | 'task_update' | 'step_update' | 'artifact_created'
  content?: string
  task_uid?: string
  step_uid?: string
  status?: string
  task?: Record<string, any>
  steps?: Record<string, any>[]
  step?: Record<string, any>
  artifact?: Record<string, any>
  final_report?: Record<string, any>
  remaining_steps?: Record<string, any>[]
  tool?: string
  input?: Record<string, any>
  description?: string
  tool_call_id?: string
  result?: string
  standard_result?: Record<string, any>
  image_url?: string
  video_url?: string
  audio_url?: string
  duration?: number
  conversation_id?: number
  session_id?: string
  metadata?: {
    model?: string
    iterations?: number
    total_tool_calls?: number
    tools_used?: string[]
    input_tokens?: number
    output_tokens?: number
    budget_usage?: Record<string, any>
  }
}

export interface AgentMessage {
  id: number
  type: 'user' | 'assistant' | 'tool_start' | 'tool_done' | 'tool_confirm' | 'error' | 'thinking'
  content?: string
  images?: string[]
  videos?: string[]
  tool?: string
  toolInput?: Record<string, any>
  description?: string
  toolCallId?: string
  toolResult?: string
  imageUrl?: string
  videoUrl?: string
  timestamp: string
  duration?: number
  isFinished?: boolean
  expanded?: boolean
  confirmed?: 'approve' | 'reject'
}

// ──────────── REST API: 配置管理 ────────────

export interface ModelConfigItem {
  id: number
  name: string
  category: string
  provider: string
  base_url: string | null
  api_key: string | null
  model_id: string
  model_params: Record<string, any> | null
  is_default: boolean
  is_enabled: boolean
}

export interface ToolRegistryItem {
  id: number
  name: string
  display_name: string
  description: string
  executor_type: string
  is_enabled: boolean
  sort_order: number
}

export interface WorkflowTemplateItem {
  id: number
  name: string
  display_name: string
  category: string
  style_tag: string | null
  test_time: number | null
  is_enabled: boolean
}

export function fetchModels(): Promise<ModelConfigItem[]> {
  return request.get('/v1/comic-agent/models')
}

export function updateModel(id: number, data: { is_enabled?: boolean; is_default?: boolean; model_params?: Record<string, any>; base_url?: string; api_key?: string; model_id?: string }) {
  return request.put(`/v1/comic-agent/models/${id}`, data)
}

export function fetchTools(): Promise<ToolRegistryItem[]> {
  return request.get('/v1/comic-agent/tools')
}

export function updateTool(id: number, data: { is_enabled?: boolean }) {
  return request.put(`/v1/comic-agent/tools/${id}`, data)
}

export function fetchWorkflows(): Promise<WorkflowTemplateItem[]> {
  return request.get('/v1/comic-agent/workflows')
}

export function updateWorkflow(id: number, data: { is_enabled?: boolean }) {
  return request.put(`/v1/comic-agent/workflows/${id}`, data)
}

// ──────────── REST API: Prompt 管理 ────────────

export interface AgentPromptItem {
  id: number
  node_name: string
  display_name: string
  prompt_type: string
  content: string
  description: string | null
  sort_order: number
  is_enabled: boolean
}

export function fetchPrompts(): Promise<AgentPromptItem[]> {
  return request.get('/v1/comic-agent/prompts')
}

export function updatePrompt(id: number, data: { content?: string; is_enabled?: boolean; display_name?: string; description?: string }) {
  return request.put(`/v1/comic-agent/prompts/${id}`, data)
}

// ──────────── REST API: 图片上传 ────────────

export interface UploadResult {
  file_path: string
  file_url: string
  filename: string
}

export async function uploadAgentImage(file: File): Promise<UploadResult> {
  const formData = new FormData()
  formData.append('file', file)
  return request.post('/v1/comic-agent/upload', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  })
}

// ──────────── REST API: 会话管理 ────────────

export interface ConversationItem {
  id: number
  session_id: string
  title: string | null
  status: string
  created_at: string
  updated_at: string
}

export function fetchConversations(): Promise<ConversationItem[]> {
  return request.get('/v1/comic-agent/conversations')
}

export function deleteConversation(id: number) {
  return request.delete(`/v1/comic-agent/conversations/${id}`)
}

// ──────────── REST API: 任务查询 ────────────

export interface TaskPayload {
  id: number
  task_uid: string
  conversation_id: number
  user_goal: string
  status: string
  current_step_uid: string | null
  created_at: string
  updated_at: string
  steps: StepPayload[]
  artifacts: ArtifactPayload[]
  events: EventPayload[]
}

export interface StepPayload {
  id: number
  step_uid: string
  task_id: number
  title: string
  description: string
  tool_name: string | null
  status: string
  inputs: Record<string, any> | null
  outputs: Record<string, any> | null
  error: Record<string, any> | null
  started_at: string | null
  finished_at: string | null
  created_at: string
}

export interface ArtifactPayload {
  id: number
  artifact_uid: string
  task_id: number
  step_uid: string | null
  artifact_type: string
  title: string
  url: string
  metadata: Record<string, any> | null
  created_at: string
}

export interface EventPayload {
  id: number
  event_uid: string
  task_id: number
  event_type: string
  payload: Record<string, any>
  created_at: string
}

export interface ToolInvocationPayload {
  id: number
  invocation_uid: string
  task_id: number
  step_uid: string | null
  tool_name: string
  status: string
  inputs: Record<string, any> | null
  outputs: Record<string, any> | null
  error: Record<string, any> | null
  started_at: string | null
  finished_at: string | null
  duration_ms: number | null
}

export interface TracePayload {
  task: TaskPayload
  tool_invocations: ToolInvocationPayload[]
  events: EventPayload[]
}

export interface ToolHealthItem {
  name: string
  display_name: string
  executor_type: string
  status: 'available' | 'degraded' | 'unavailable'
  is_enabled: boolean
}

export interface ToolStatsItem {
  tool_name: string
  total_calls: number
  succeeded: number
  failed: number
  avg_duration_ms: number | null
  success_rate: number
}

export function fetchTask(taskUid: string): Promise<TaskPayload> {
  return request.get(`/v1/comic-agent/tasks/${taskUid}`)
}

export function fetchTaskEvents(taskUid: string, skip = 0, limit = 100): Promise<EventPayload[]> {
  return request.get(`/v1/comic-agent/tasks/${taskUid}/events`, { params: { skip, limit } })
}

export function fetchTaskArtifacts(taskUid: string): Promise<ArtifactPayload[]> {
  return request.get(`/v1/comic-agent/tasks/${taskUid}/artifacts`)
}

export function fetchTaskTrace(taskUid: string): Promise<TracePayload> {
  return request.get(`/v1/comic-agent/tasks/${taskUid}/trace`)
}

export function cancelTask(taskUid: string): Promise<{ task_uid: string; status: string }> {
  return request.post(`/v1/comic-agent/tasks/${taskUid}/cancel`)
}

export function retryStep(taskUid: string, stepUid: string): Promise<{ task_uid: string; step_uid: string; status: string }> {
  return request.post(`/v1/comic-agent/tasks/${taskUid}/steps/${stepUid}/retry`)
}

export function fetchToolsHealth(): Promise<{ tools: ToolHealthItem[]; total: number }> {
  return request.get('/v1/comic-agent/tools/health')
}

export function fetchToolStats(): Promise<{ stats: ToolStatsItem[] }> {
  return request.get('/v1/comic-agent/tools/stats')
}

export function fetchConversationTasks(conversationId: number, skip = 0, limit = 50): Promise<TaskPayload[]> {
  return request.get(`/v1/comic-agent/conversations/${conversationId}/tasks`, { params: { skip, limit } })
}

// ──────────── WebSocket Agent 对话 ────────────

export interface AgentChatOptions {
  conversationId?: number
  style?: string
  frames?: number
  model?: string
  tts?: boolean
  autoVideo?: boolean
  auto_mode?: boolean
  image_paths?: string[]
}

export class ComicAgentWS {
  private ws: WebSocket | null = null
  private _onEvent: ((event: AgentEvent) => void) | null = null
  private _onDone: (() => void) | null = null
  private _onReconnect: (() => void) | null = null
  private _conversationId: number = 0
  private _autoReconnect = false
  private _reconnectAttempts = 0
  private _maxReconnectAttempts = 5
  private _reconnectTimer: ReturnType<typeof setTimeout> | null = null
  private _intentionalClose = false
  private _lastTaskUid: string | null = null

  get conversationId() { return this._conversationId }
  get connected() { return this.ws?.readyState === WebSocket.OPEN }

  /** 记录当前任务 UID，用于重连后回放 */
  set lastTaskUid(uid: string | null) { this._lastTaskUid = uid }
  get lastTaskUid() { return this._lastTaskUid }

  connect(
    onEvent: (event: AgentEvent) => void,
    onDone?: () => void,
    conversationId: number = 0,
    options?: { autoReconnect?: boolean; onReconnect?: () => void },
  ): Promise<void> {
    return new Promise((resolve, reject) => {
      const token = localStorage.getItem('access_token') || ''
      const protocol = location.protocol === 'https:' ? 'wss' : 'ws'
      const url = `${protocol}://${location.host}/api/v1/comic-agent/ws/chat?conversation_id=${conversationId}&token=${token}`

      this._onEvent = onEvent
      this._onDone = onDone || null
      this._onReconnect = options?.onReconnect || null
      this._autoReconnect = options?.autoReconnect ?? false
      this._conversationId = conversationId
      this._intentionalClose = false
      this.ws = new WebSocket(url)

      this.ws.onopen = () => {
        this._reconnectAttempts = 0
        resolve()
      }

      this.ws.onmessage = (e) => {
        try {
          const event: AgentEvent = JSON.parse(e.data)
          if (event.type === 'conversation_created') {
            this._conversationId = event.conversation_id || 0
          }
          if (event.task_uid) {
            this._lastTaskUid = event.task_uid
          }
          if (event.type === 'done') {
            this._onEvent?.(event)
            this._onDone?.()
          } else {
            this._onEvent?.(event)
          }
        } catch { /* ignore */ }
      }

      this.ws.onerror = () => {
        this._onEvent?.({ type: 'error', content: 'WebSocket 连接失败' })
        reject(new Error('WebSocket 连接失败'))
      }

      this.ws.onclose = () => {
        this.ws = null
        if (this._autoReconnect && !this._intentionalClose) {
          this._scheduleReconnect()
        }
      }
    })
  }

  private _scheduleReconnect() {
    if (this._reconnectAttempts >= this._maxReconnectAttempts) return
    const delay = Math.min(1000 * Math.pow(2, this._reconnectAttempts), 30000)
    this._reconnectAttempts++
    this._reconnectTimer = setTimeout(async () => {
      try {
        await this.connect(
          this._onEvent!,
          this._onDone || undefined,
          this._conversationId,
          { autoReconnect: true, onReconnect: this._onReconnect || undefined },
        )
        this._onReconnect?.()
      } catch { /* will retry via onclose */ }
    }, delay)
  }

  /** 回放历史事件（静默模式，不触发动画） */
  async replayEvents(taskUid: string, handler: (event: AgentEvent) => void): Promise<void> {
    const events = await fetchTaskEvents(taskUid)
    for (const ev of events) {
      handler(ev.payload as unknown as AgentEvent)
    }
  }

  send(message: string, options: Omit<AgentChatOptions, 'conversationId'> = {}) {
    if (this.ws?.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify({ message, ...options }))
    }
  }

  /** 发送原始 JSON（用于工具审批等非聊天消息） */
  sendRaw(data: Record<string, any>) {
    if (this.ws?.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify(data))
    }
  }

  disconnect() {
    this._intentionalClose = true
    this._autoReconnect = false
    if (this._reconnectTimer) {
      clearTimeout(this._reconnectTimer)
      this._reconnectTimer = null
    }
    this.ws?.close()
    this.ws = null
  }
}
