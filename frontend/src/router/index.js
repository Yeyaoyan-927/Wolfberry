import { createRouter, createWebHistory } from 'vue-router'
import { useAuthStore } from '../stores/auth'

const routes = [
  { path: '/login', name: 'login', component: () => import('../views/Login.vue'), meta: { bare: true } },
  // ---------- 交易端 ----------
  {
    path: '/',
    component: () => import('../layouts/WebLayout.vue'),
    children: [
      { path: '', name: 'home', component: () => import('../views/web/Home.vue') },
      { path: 'products', name: 'products', component: () => import('../views/web/Products.vue') },
      { path: 'products/:id', name: 'product-detail', component: () => import('../views/web/ProductDetail.vue') },
      { path: 'orders', name: 'orders', component: () => import('../views/web/Orders.vue'), meta: { auth: true } },
      { path: 'publish', name: 'publish', component: () => import('../views/web/Publish.vue'), meta: { auth: true, seller: true } },
      { path: 'chat', name: 'chat', component: () => import('../views/web/Chat.vue'), meta: { auth: true } },
    ],
  },
  // ---------- 后台 ----------
  {
    path: '/admin',
    component: () => import('../layouts/AdminLayout.vue'),
    meta: { auth: true, admin: true },
    children: [
      { path: '', redirect: '/admin/audit' },
      { path: 'audit', name: 'admin-audit', component: () => import('../views/admin/AuditQueue.vue') },
      { path: 'audit/:id', name: 'admin-audit-detail', component: () => import('../views/admin/AuditDetail.vue') },
      { path: 'products', name: 'admin-products', component: () => import('../views/admin/Products.vue') },
    ],
  },
  { path: '/:pathMatch(.*)*', redirect: '/' },
]

const router = createRouter({ history: createWebHistory(), routes })

router.beforeEach((to) => {
  const auth = useAuthStore()
  if (to.meta.auth && !auth.isLogin) return { name: 'login', query: { redirect: to.fullPath } }
  if (to.meta.admin && auth.role !== 'admin') return { name: 'home' }
  if (to.meta.seller && !['seller', 'admin'].includes(auth.role)) return { name: 'home' }
  return true
})

export default router
