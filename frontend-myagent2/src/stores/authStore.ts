import { create } from 'zustand';
import type { AuthUser } from '@/api/auth';

interface AuthState {
  token: string | null;
  user: AuthUser | null;
  isAuthenticated: boolean;
  setAuth: (token: string, user: AuthUser) => void;
  logout: () => void;
  hydrate: () => void;
}

function _loadFromStorage(): { token: string | null; user: AuthUser | null; isAuthenticated: boolean } {
  try {
    const token = localStorage.getItem('auth_token');
    const userStr = localStorage.getItem('auth_user');
    if (token && userStr) {
      return { token, user: JSON.parse(userStr) as AuthUser, isAuthenticated: true };
    }
  } catch {
    localStorage.removeItem('auth_token');
    localStorage.removeItem('auth_user');
  }
  return { token: null, user: null, isAuthenticated: false };
}

export const useAuthStore = create<AuthState>((set) => ({
  ..._loadFromStorage(),

  setAuth: (token, user) => {
    localStorage.setItem('auth_token', token);
    localStorage.setItem('auth_user', JSON.stringify(user));
    set({ token, user, isAuthenticated: true });
  },

  logout: () => {
    localStorage.removeItem('auth_token');
    localStorage.removeItem('auth_user');
    set({ token: null, user: null, isAuthenticated: false });
  },

  hydrate: () => {
    set(_loadFromStorage());
  },
}));
