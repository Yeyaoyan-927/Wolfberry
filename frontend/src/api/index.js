import axios from 'axios'

// 供需要直接调原始接口的页面使用（如 kb/search 测试）
export { default as http } from './http'

import http from './http'

export const login = (username, password) =>
  http.post('/auth/login', { username, password })

export const listProducts = (params) => http.get('/products', { params })

export const getProduct = (id) => http.get(`/products/${id}`)

export const createProduct = (payload) => http.post('/products', payload)

export const uploadProductImage = (id, file) => {
  const fd = new FormData()
  fd.append('file', file)
  return http.post(`/products/${id}/images`, fd, {
    headers: { 'Content-Type': 'multipart/form-data' },
  })
}

export const createOrder = (productId, quantity) =>
  http.post('/orders', { product_id: productId, quantity })

export const listOrders = (params) => http.get('/orders', { params })

export const confirmOrder = (id) => http.post(`/orders/${id}/confirm`)
export const shipOrder = (id, data) => http.post(`/orders/${id}/ship`, data)
export const receiveOrder = (id) => http.post(`/orders/${id}/receive`)
export const cancelOrder = (id, reason) => http.post(`/orders/${id}/cancel`, { reason })
export const registerPay = (id, voucher_key) => http.post(`/orders/${id}/pay`, { voucher_key })

export const auditQueue = (params) => http.get('/admin/audit/queue', { params })
export const adminStats = () => http.get('/admin/audit/stats')

// 知识库
export const kbDocuments = (params) => http.get('/kb/documents', { params })
export const uploadKbDoc = (file, meta) => {
  const fd = new FormData()
  fd.append('file', file)
  if (meta?.title) fd.append('title', meta.title)
  if (meta?.doc_type) fd.append('doc_type', meta.doc_type)
  return http.post('/kb/documents', fd, { headers: { 'Content-Type': 'multipart/form-data' } })
}
export const kbChunks = (docId) => http.get(`/kb/documents/${docId}/chunks`)
export const kbEval = (params) => http.get('/kb/eval', { params })
export const auditDetail = (id) => http.get(`/admin/audit/products/${id}`)
export const auditApprove = (id, gradePlatform) =>
  http.post(`/admin/audit/products/${id}/approve`, null, {
    params: gradePlatform ? { grade_platform: gradePlatform } : {},
  })
export const auditReject = (id, reasonCode, note) =>
  http.post(`/admin/audit/products/${id}/reject`, null, {
    params: { reason_code: reasonCode, note: note || '' },
  })
export const auditReassess = (id) => http.post(`/admin/audit/products/${id}/reassess`)

export const kbAsk = (question) => http.post('/kb/ask', { question })

export const optimizeAdvice = (productId) => http.get(`/skills/products/${productId}/optimize`)
