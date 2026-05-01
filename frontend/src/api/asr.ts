import request from './request'
import type { ASRTask } from '@/types/api'

export const recognize = (file: File, language = 'zh'): Promise<{ task_id: number; status: string }> => {
  const formData = new FormData()
  formData.append('audio', file)
  formData.append('language', language)
  return request.post('/v1/asr/recognize', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  })
}

export const getTasks = (skip = 0, limit = 20): Promise<ASRTask[]> =>
  request.get('/v1/asr/tasks', { params: { skip, limit } })

export const getTask = (taskId: number): Promise<ASRTask> =>
  request.get(`/v1/asr/tasks/${taskId}`)
