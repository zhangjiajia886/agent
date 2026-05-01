import request from './request'
import type { TTSRequest, TTSTask } from '@/types/api'

export const synthesize = (data: TTSRequest): Promise<{ task_id: number; status: string }> =>
  request.post('/v1/tts/synthesize', data)

export const getTasks = (skip = 0, limit = 20): Promise<TTSTask[]> =>
  request.get('/v1/tts/tasks', { params: { skip, limit } })

export const getTask = (taskId: number): Promise<TTSTask> =>
  request.get(`/v1/tts/tasks/${taskId}`)

export interface EmotionTestParams {
  text: string
  model?: string
  reference_id?: string
  latency?: string
  normalize?: boolean
}

export const testEmotion = (params: EmotionTestParams): Promise<ArrayBuffer> =>
  request.post('/v1/tts/test-emotion', params, { responseType: 'arraybuffer' })
