import { ref, computed } from 'vue'
import { defineStore } from 'pinia'
import { login as apiLogin, getMe } from '@/api/auth'
import type { User } from '@/types/auth'
import { ApiError } from '@/api/client'
import router from '@/router'

export const useAuthStore = defineStore('auth', () => {
  const user = ref<User | null>(null)
  const token = ref<string | null>(localStorage.getItem('token'))
  const isAuthenticated = computed(() => !!user.value && !!token.value)

  async function login(email: string, password: string) {
    const res = await apiLogin({ email, password })
    token.value = res.access_token
    user.value = res.user
    localStorage.setItem('token', res.access_token)
  }

  async function init() {
    if (!token.value) return
    try {
      user.value = await getMe()
    } catch (e) {
      if (e instanceof ApiError && e.status === 401) {
        logout()
      }
    }
  }

  function logout() {
    user.value = null
    token.value = null
    localStorage.removeItem('token')
    router.push('/login')
  }

  return { user, token, isAuthenticated, login, init, logout }
})
