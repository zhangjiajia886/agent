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
  private _conversationId: number = 0

  get conversationId() { return this._conversationId }
  get connected() { return this.ws?.readyState === WebSocket.OPEN }

  connect(
    onEvent: (event: AgentEvent) => void,
    onDone?: () => void,
    conversationId: number = 0,
  ): Promise<void> {
    return new Promise((resolve, reject) => {
      const token = localStorage.getItem('access_token') || ''
      const protocol = location.protocol === 'https:' ? 'wss' : 'ws'
      const url = `${protocol}://${location.host}/api/v1/comic-agent/ws/chat?conversation_id=${conversationId}&token=${token}`

      this._onEvent = onEvent
      this._onDone = onDone || null
      this._conversationId = conversationId
      this.ws = new WebSocket(url)

      this.ws.onopen = () => resolve()

      this.ws.onmessage = (e) => {
        try {
          const event: AgentEvent = JSON.parse(e.data)
          if (event.type === 'conversation_created') {
            this._conversationId = event.conversation_id || 0
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
      }
    })
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
    this.ws?.close()
    this.ws = null
  }
}
