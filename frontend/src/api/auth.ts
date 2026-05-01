import request from './request'
import type { TokenInfo, UserInfo } from '@/types/api'

export const login = (username: string, password: string): Promise<TokenInfo> => {
  const formData = new URLSearchParams()
  formData.append('username', username)
  formData.append('password', password)
  return request.post('/v1/auth/login', formData, {
    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
  })
}

export const register = (data: { username: string; email: string; password: string; full_name?: string }): Promise<UserInfo> =>
  request.post('/v1/auth/register', data)

export const getMe = (): Promise<UserInfo> =>
  request.get('/v1/auth/me')
