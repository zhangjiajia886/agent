import request from './request'
import type { ChatSessionSchema, ChatSessionListItem } from '@/types/api'

export const getSessions = (skip = 0, limit = 50): Promise<ChatSessionListItem[]> =>
  request.get('/v1/chat/sessions', { params: { skip, limit } })

export const createSession = (data: { title?: string; system_prompt?: string }): Promise<ChatSessionSchema> =>
  request.post('/v1/chat/sessions', data)

export const getSession = (id: number): Promise<ChatSessionSchema> =>
  request.get(`/v1/chat/sessions/${id}`)

export const updateSession = (id: number, data: { title?: string; system_prompt?: string }): Promise<ChatSessionSchema> =>
  request.patch(`/v1/chat/sessions/${id}`, data)

export const deleteSession = (id: number): Promise<{ message: string }> =>
  request.delete(`/v1/chat/sessions/${id}`)

export const sendMessage = (data: { session_id: number; message: string }): Promise<{ role: string; content: string; message_id: number }> =>
  request.post('/v1/chat/send', data)
