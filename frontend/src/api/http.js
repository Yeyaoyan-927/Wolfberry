import axios from 'axios'
import { ElMessage } from 'element-plus'
import router from '../router'

/** 统一响应 {code, message, data, trace_id}；HTTP 错误与业务错误统一收敛 */
const http = axios.create({ baseURL: '/api/v1', timeout: 30000 })

http.interceptors.request.use((cfg) => {
  // 与 auth store 一致：token 存 sessionStorage
  const token = sessionStorage.getItem('wb_token') || localStorage.getItem('wb_token')
  if (token) cfg.headers.Authorization = `Bearer ${token}`
  return cfg
})

http.interceptors.response.use(
  (resp) => {
    const body = resp.data
    if (body && typeof body === 'object' && 'code' in body) {
      if (body.code === 0) return body.data
      if (body.code === 40101) {
        localStorage.removeItem('wb_token')
        localStorage.removeItem('wb_user')
        sessionStorage.removeItem('wb_token')
        sessionStorage.removeItem('wb_user')
        if (router.currentRoute.value.name !== 'login') router.push({ name: 'login' })
        return Promise.reject(new Error(body.message || '未登录'))
      }
      // 越权访问：送回自己有权限的首页，而不是停在报错页面
      if (body.code === 40301) {
        ElMessage.error(body.message || '无权限')
        const path = router.currentRoute.value.path
        if (path.startsWith('/admin')) router.push('/home')
        return Promise.reject(new Error(body.message || '无权限'))
      }
      ElMessage.error(body.message || '请求失败')
      return Promise.reject(new Error(body.message || '请求失败'))
    }
    return body
  },
  (err) => {
    const msg = err.response?.data?.message || err.message || '网络异常'
    ElMessage.error(msg)
    return Promise.reject(err)
  },
)

export default http
