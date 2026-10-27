import axios from 'axios'

// 供需要直接调原始接口的页面使用（如 kb/search 测试）
export { default as http } from './http'

import http from './http'

export const login = (username, password) =>
  http.post('/auth/login', { username, password })

export const listProducts = (params) => http.get('/products', { params })

export const getProduct = (id) => http.get(`/products/${id}`)

export const myProducts = (params) => http.get('/products/mine', { params })

export const marketSummary = (params) => http.get('/market/summary', { params })
export const marketOrigins = () => http.get('/market/origins')

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
export const queueStats = () => http.get('/admin/audit/queue-stats')

// 管理端：用户 / 阈值 / 审计日志
export const adminUsers = (params) => http.get('/admin/users', { params })
export const setUserStatus = (id, isActive) =>
  http.patch(`/admin/users/${id}/status`, null, { params: { is_active: isActive } })
export const adminThresholds = () => http.get('/admin/thresholds')
export const adminAuditLogs = (params) => http.get('/admin/audit/logs', { params })

// 知识库
export const kbDocuments = (params) => http.get('/kb/documents', { params })
export const uploadKbDoc = (file, meta) => {
  const fd = new FormData()
  fd.append('file', file)
  if (meta?.title) fd.append('title', meta.title)
  fd.append('doc_type', meta?.doc_type || 'other')
  fd.append('chunk_strategy', meta?.chunk_strategy || 'auto')
  if (meta?.chunk_size) fd.append('chunk_size', String(meta.chunk_size))
  if (meta?.chunk_overlap !== undefined && meta?.chunk_overlap !== null) {
    fd.append('chunk_overlap', String(meta.chunk_overlap))
  }
  return http.post('/kb/documents', fd, { headers: { 'Content-Type': 'multipart/form-data' } })
}

/** 试切分：只看切片与质量报告，不入库 */
export const kbPreview = (file, meta) => {
  const fd = new FormData()
  fd.append('file', file)
  fd.append('doc_type', meta?.doc_type || 'other')
  fd.append('chunk_strategy', meta?.chunk_strategy || 'auto')
  fd.append('chunk_size', String(meta?.chunk_size || 0))
  fd.append('chunk_overlap', String(meta?.chunk_overlap ?? -1))
  return http.post('/kb/preview', fd, { headers: { 'Content-Type': 'multipart/form-data' } })
}

/** 重切：按新参数重新解析原文件并重新向量化入库 */
export const kbRechunk = (docId, params) => http.post(`/kb/documents/${docId}/rechunk`, null, { params })

export const kbDelete = (docId) => http.delete(`/kb/documents/${docId}`)

export const kbChunks = (docId, params) => http.get(`/kb/documents/${docId}/chunks`, { params })
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

/**
 * 流式问答：逐节点接收执行过程（意图识别 → 工具调用 → 汇总生成）。
 * 用 fetch + ReadableStream 而非 axios —— axios 会把响应整体缓冲，拿不到增量。
 *
 * @param {string} question
 * @param {(event: string, data: object) => void} onEvent
 * @param {AbortSignal} [signal]
 */
export async function kbAskStream(question, onEvent, signal) {
  const token = sessionStorage.getItem('wb_token') || ''
  const resp = await fetch('/api/v1/kb/ask/stream', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    body: JSON.stringify({ question }),
    signal,
  })
  if (!resp.ok || !resp.body) {
    throw new Error(`流式接口异常 HTTP ${resp.status}`)
  }

  const reader = resp.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''
  while (true) {
    const { done, value } = await reader.read()
    if (done) break
    buffer += decoder.decode(value, { stream: true })
    const blocks = buffer.split('\n\n')
    buffer = blocks.pop() || ''
    for (const block of blocks) {
      const evLine = /^event:\s*(.+)$/m.exec(block)
      const dataLine = /^data:\s*(.+)$/m.exec(block)
      if (!evLine || !dataLine) continue
      let payload
      try {
        payload = JSON.parse(dataLine[1])
      } catch {
        continue
      }
      onEvent(evLine[1].trim(), payload)
    }
  }
}

export const optimizeAdvice = (productId) => http.get(`/skills/products/${productId}/optimize`)
