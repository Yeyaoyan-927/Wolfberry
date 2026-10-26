import { defineStore } from 'pinia'

export const useAuthStore = defineStore('auth', {
  state: () => ({
    token: localStorage.getItem('wb_token') || '',
    user: JSON.parse(localStorage.getItem('wb_user') || 'null'),
  }),
  getters: {
    isLogin: (s) => !!s.token,
    role: (s) => s.user?.role || '',
    displayName: (s) => s.user?.name || s.user?.username || '',
  },
  actions: {
    setAuth(token, user) {
      this.token = token
      this.user = user
      localStorage.setItem('wb_token', token)
      localStorage.setItem('wb_user', JSON.stringify(user))
    },
    logout() {
      this.token = ''
      this.user = null
      localStorage.removeItem('wb_token')
      localStorage.removeItem('wb_user')
    },
  },
})
