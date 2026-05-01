import { defineStore } from 'pinia'
import { ref } from 'vue'
import { getMe, login as apiLogin } from '@/api/auth'
import type { UserInfo } from '@/types/api'

export const useUserStore = defineStore('user', () => {
  const userInfo = ref<UserInfo | null>(null)
  const token = ref<string>(localStorage.getItem('access_token') || '')

  const isLoggedIn = () => !!token.value

  async function login(username: string, password: string) {
    const res = await apiLogin(username, password)
    token.value = res.access_token
    localStorage.setItem('access_token', res.access_token)
    await fetchUserInfo()
  }

  async function fetchUserInfo() {
    userInfo.value = await getMe()
  }

  function logout() {
    token.value = ''
    userInfo.value = null
    localStorage.removeItem('access_token')
  }

  return { userInfo, token, isLoggedIn, login, fetchUserInfo, logout }
})
