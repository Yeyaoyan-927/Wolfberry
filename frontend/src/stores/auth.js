import { defineStore } from 'pinia'

// 登录态存 sessionStorage：新开标签页/重启浏览器即失效，入口永远是登录页
const store = sessionStorage

export const useAuthStore = defineStore('auth', {
  state: () => ({
    token: store.getItem('wb_token') || '',
    user: JSON.parse(store.getItem('wb_user') || 'null'),
  }),
  getters: {
    isLogin: (s) => !!s.token,
    role: (s) => s.user?.role || '',
    displayName: (s) => s.user?.name || s.user?.username || '',
  },
  actions: {
    setAuth(token, user) {
      // 清掉历史版本遗留的 localStorage 凭据，防止新旧 token 混用
      localStorage.removeItem('wb_token')
      localStorage.removeItem('wb_user')
      this.token = token
      this.user = user
      store.setItem('wb_token', token)
      store.setItem('wb_user', JSON.stringify(user))
    },
    logout() {
      this.token = ''
      this.user = null
      store.removeItem('wb_token')
      store.removeItem('wb_user')
    },
  },
})
