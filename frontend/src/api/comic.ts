import request from './request'

export interface ComicGenerateParams {
  description: string
  num_frames?: number
  include_video?: boolean
  face_image?: File | null
}

export interface ComicTask {
  task_id: number
  status: 'pending' | 'processing' | 'completed' | 'failed'
  description: string
  style?: string
  num_frames: number
  storyboard?: string[]
  prompts?: string[]
  frame_urls?: string[]
  video_url?: string | null
  error_message?: string | null
  created_at?: string
  completed_at?: string | null
}

export interface ComicHealth {
  comfyui_reachable: boolean
  comfyui_url: string
  enabled: boolean
}

export const generateComic = (params: ComicGenerateParams): Promise<{ task_id: number; status: string }> => {
  const form = new FormData()
  form.append('description', params.description)
  form.append('num_frames', String(params.num_frames ?? 4))
  form.append('include_video', String(params.include_video ?? false))
  if (params.face_image) {
    form.append('face_image', params.face_image)
  }
  return request.post('/v1/comic/generate', form)
}

export const getComicTask = (taskId: number): Promise<ComicTask> =>
  request.get(`/v1/comic/tasks/${taskId}`)

export const getComicHealth = (): Promise<ComicHealth> =>
  request.get('/v1/comic/health')
