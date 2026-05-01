import request from './request'
import type { VoiceModel, PageResult } from '@/types/api'

export const getModels = (skip = 0, limit = 20): Promise<PageResult<VoiceModel>> =>
  request.get('/v1/voice-models/', { params: { skip, limit } })

export const getModel = (id: number): Promise<VoiceModel> =>
  request.get(`/v1/voice-models/${id}`)

export const createModel = (data: { title: string; description?: string; language?: string; visibility?: string; audio_files: File[] }): Promise<VoiceModel> => {
  const formData = new FormData()
  formData.append('title', data.title)
  if (data.description) formData.append('description', data.description)
  if (data.language) formData.append('language', data.language)
  if (data.visibility) formData.append('visibility', data.visibility)
  data.audio_files.forEach((file) => formData.append('audio_files', file))
  return request.post('/v1/voice-models/', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
    timeout: 180000,
  })
}

export const updateModel = (id: number, data: { title?: string; description?: string; visibility?: string }): Promise<VoiceModel> =>
  request.patch(`/v1/voice-models/${id}`, data)

export const deleteModel = (id: number): Promise<{ message: string }> =>
  request.delete(`/v1/voice-models/${id}`)

export const searchOfficialVoices = (params: { title?: string; tag?: string; page_size?: number; page_number?: number }): Promise<{ total: number; items: OfficialVoiceItem[] }> =>
  request.get('/v1/voice-models/official/search', { params })

export const importOfficialVoices = (fish_model_ids: string[], language = 'zh'): Promise<{ imported: number; skipped: number }> =>
  request.post('/v1/voice-models/import-official', fish_model_ids, { params: { language } })

export interface OfficialVoiceItem {
  _id: string
  title: string
  description?: string
  cover_image?: string
  already_imported: boolean
}
