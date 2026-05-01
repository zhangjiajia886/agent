/**
 * 漫剧 Agent 前端类型定义
 */

// ──────────── 任务状态 ────────────
export type TaskStatus = 'idle' | 'running' | 'awaiting_approval' | 'completed' | 'failed' | 'canceled'
export type StepStatus = 'pending' | 'running' | 'awaiting_approval' | 'completed' | 'failed' | 'canceled'
export type ArtifactType = 'image' | 'video' | 'audio' | 'file'

export interface TaskStep {
  id: string
  tool?: string
  toolCallId?: string
  title: string
  description: string
  status: StepStatus
  startedAt?: string
  finishedAt?: string
}

export interface TaskArtifact {
  id: string
  type: ArtifactType
  title: string
  url: string
  fromStep: string
}

export interface TaskLog {
  id: string
  stepId?: string
  title: string
  content: string
  timestamp: string
}

export interface AgentTaskViewModel {
  id: string
  taskUid?: string
  title: string
  userRequest: string
  intent: string
  analysis: string
  currentStage: string
  status: TaskStatus
  steps: TaskStep[]
  artifacts: TaskArtifact[]
  logs: TaskLog[]
  finalReport?: Record<string, any>
}

// ──────────── 图片附件 ────────────
export interface AttachedImage {
  file: File
  previewUrl: string
  uploading: boolean
  uploaded?: import('@/api/comic-agent').UploadResult
}

// ──────────── 工具显示名 ────────────
export const TOOL_NAMES: Record<string, string> = {
  generate_image: '图像生成',
  generate_image_with_face: '人像一致性生成',
  jimeng_generate_image: '即梦图像生成',
  jimeng_edit_image: '即梦图像编辑',
  edit_image: '图像编辑',
  upscale_image: '图像增强',
  jimeng_upscale_image: '即梦图像增强',
  image_to_video: '图生视频',
  jimeng_generate_video: '即梦视频生成',
  text_to_speech: '语音合成',
  merge_media: '音视频合成',
  add_subtitle: '字幕添加',
}
