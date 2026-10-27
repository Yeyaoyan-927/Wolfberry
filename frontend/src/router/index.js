import { createRouter, createWebHistory } from 'vue-router'
import { useAuthStore } from '../stores/auth'

const routes = [
  // 根路径即登录页（未登录的唯一入口）
  { path: '/', name: 'login', component: () => import('../views/Login.vue'), meta: { bare: true } },
  // ---------- 交易端（子路由用绝对路径，URL 保持 /products 等短形式） ----------
  {
    path: '/home',
    component: () => import('../layouts/WebLayout.vue'),
    children: [
      { path: '/home', name: 'home', component: () => import('../views/web/Home.vue') },
      { path: '/products', name: 'products', component: () => import('../views/web/Products.vue') },
      { path: '/products/:id', name: 'product-detail', component: () => import('../views/web/ProductDetail.vue') },
      { path: '/orders', name: 'orders', component: () => import('../views/web/Orders.vue') },
      { path: '/publish', name: 'publish', component: () => import('../views/web/Publish.vue'), meta: { seller: true } },
      { path: '/chat', name: 'chat', component: () => import('../views/web/Chat.vue') },
    ],
  },
  // ---------- 后台（每个子路由显式声明 admin，不依赖 meta 合并） ----------
  {
    path: '/admin',
    component: () => import('../layouts/AdminLayout.vue'),
    children: [
      { path: '', redirect: '/admin/audit' },
      { path: 'audit', name: 'admin-audit', component: () => import('../views/admin/AuditQueue.vue'), meta: { admin: true } },
      { path: 'audit/:id', name: 'admin-audit-detail', component: () => import('../views/admin/AuditDetail.vue'), meta: { admin: true } },
      { path: 'products', name: 'admin-products', component: () => import('../views/admin/Products.vue'), meta: { admin: true } },
    ],
  },
  { path: '/:pathMatch(.*)*', redirect: '/' },
]

const router = createRouter({ history: createWebHistory(), routes })

router.beforeEach((to) => {
  const auth = useAuthStore()
  // 未登录：一律回根路径登录页
  if (to.name !== 'login' && !auth.isLogin) {
    return { name: 'login', query: { redirect: to.fullPath } }
  }
  // 已登录访问登录页 → 按角色进系统
  if (to.name === 'login' && auth.isLogin) {
    return auth.role === 'admin' ? '/admin/audit' : '/home'
  }
  // 管理端：用 matched 链判断，任何一层声明 admin 即生效
  if (to.matched.some((r) => r.meta.admin) && auth.role !== 'admin') return '/home'
  if (to.matched.some((r) => r.meta.seller) && !['seller', 'admin'].includes(auth.role)) return '/home'
  return true
})

export default router
