import { post, get } from './client';

export interface AuthUser {
  id: string;
  username: string;
  display_name: string;
  is_admin?: number;
  created_at?: string;
}

export interface AuthResponse {
  token: string;
  user: AuthUser;
}

export function apiRegister(username: string, password: string, display_name?: string) {
  return post<AuthResponse>('/api/auth/register', { username, password, display_name });
}

export function apiLogin(username: string, password: string) {
  return post<AuthResponse>('/api/auth/login', { username, password });
}

export function apiMe() {
  return get<AuthUser>('/api/auth/me');
}
