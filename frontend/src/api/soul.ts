import request from './request'
import type { SoulTaskDetail, SoulTaskResponse, TranscribeResult } from '@/types/api'

// ---- Podcast ----

export const podcastSynthesize = (formData: FormData): Promise<SoulTaskResponse> =>
  request.post('/v1/podcast/synthesize', formData, { timeout: 30000 })

export const podcastHealth = (): Promise<{ space: string; online: boolean }> =>
  request.get('/v1/podcast/health')

// ---- Singing ----

export const singingTranscribe = (formData: FormData): Promise<TranscribeResult> =>
  request.post('/v1/singing/transcribe', formData, { timeout: 300000 })

export const singingSvs = (formData: FormData): Promise<SoulTaskResponse> =>
  request.post('/v1/singing/svs', formData, { timeout: 30000 })

export const singingSvc = (formData: FormData): Promise<SoulTaskResponse> =>
  request.post('/v1/singing/svc', formData, { timeout: 30000 })

export const singingHealth = (): Promise<{ space: string; online: boolean }> =>
  request.get('/v1/singing/health')

// ---- Digital Human ----

export const digitalHumanGenerate = (formData: FormData): Promise<SoulTaskResponse> =>
  request.post('/v1/digital-human/generate', formData, { timeout: 30000 })

export const digitalHumanHealth = (): Promise<{ space: string; online: boolean }> =>
  request.get('/v1/digital-human/health')

// ---- 通用任务查询 ----

export const getSoulTasks = (
  module: 'podcast' | 'singing' | 'digital-human',
  skip = 0,
  limit = 20
): Promise<SoulTaskDetail[]> =>
  request.get(`/v1/${module}/tasks`, { params: { skip, limit } })

export const getSoulTask = (
  module: 'podcast' | 'singing' | 'digital-human',
  taskId: number
): Promise<SoulTaskDetail> =>
  request.get(`/v1/${module}/tasks/${taskId}`)
