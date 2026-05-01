export interface ApiResponse<T = any> {
  data: T
  code?: number
  message?: string
}

export interface PageResult<T> {
  total: number
  items: T[]
}

export interface UserInfo {
  id: number
  username: string
  email: string
  full_name: string | null
  avatar_url: string | null
  is_active: boolean
  is_superuser: boolean
  created_at: string
  updated_at: string
}

export interface TokenInfo {
  access_token: string
  token_type: string
}

export interface VoiceModel {
  id: number
  fish_model_id: string
  title: string
  description: string | null
  language: string
  visibility: 'private' | 'public'
  sample_audio_url: string | null
  usage_count: number
  created_at: string
  updated_at: string
}

export interface TTSRequest {
  text: string
  voice_model_id?: number
  format?: 'mp3' | 'wav' | 'pcm' | 'opus'
  latency?: 'normal' | 'balanced' | 'low'
  streaming?: boolean
  mp3_bitrate?: number
  tts_model?: 's1' | 's2' | 's2-pro'
  normalize?: boolean
  style_prompt?: string
}

export interface TTSTask {
  id: number
  text: string
  format: string
  latency: string
  streaming: boolean
  audio_url: string | null
  audio_size: number | null
  duration: number | null
  status: 'pending' | 'processing' | 'completed' | 'failed'
  error_message: string | null
  cost_credits: number | null
  created_at: string
  completed_at: string | null
}

export interface ASRTask {
  id: number
  audio_url: string
  language: string
  recognized_text: string | null
  duration: number | null
  segments: ASRSegment[] | null
  status: 'pending' | 'processing' | 'completed' | 'failed'
  error_message: string | null
  cost_credits: number | null
  created_at: string
  completed_at: string | null
}

export interface ASRSegment {
  text: string
  start: number
  end: number
}

export interface ChatMessage {
  id: number
  role: 'user' | 'assistant' | 'system'
  content: string
  tts_audio_url: string | null
  created_at: string
}

export interface ChatSessionListItem {
  id: number
  title: string
  created_at: string
  updated_at: string
}

export interface ChatSessionSchema extends ChatSessionListItem {
  system_prompt: string | null
  messages: ChatMessage[]
}

// ---- Soul AI Lab ----

export interface SoulTaskDetail {
  id: number
  task_type: 'podcast' | 'singing_svs' | 'singing_svc' | 'digital_human'
  status: 'pending' | 'processing' | 'completed' | 'failed'
  input_text: string | null
  input_params: string | null
  ref_audio_url: string | null
  ref_audio2_url: string | null
  ref_image_url: string | null
  source_audio_url: string | null
  output_url: string | null
  output_size: number | null
  output_format: string | null
  error_message: string | null
  created_at: string
  completed_at: string | null
}

export interface SoulTaskResponse {
  task_id: number
  status: string
}

export interface TranscribeResult {
  prompt_metadata: string | null
  target_metadata: string | null
}
