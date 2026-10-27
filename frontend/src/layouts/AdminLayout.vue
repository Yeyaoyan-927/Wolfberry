<template>
  <el-container class="admin-shell">
    <el-aside width="220px" class="aside">
      <div class="brand">
        <span class="berry"></span>
        <div>
          <div class="name">杞市后台</div>
          <div class="sub">平台运营</div>
        </div>
      </div>
      <el-menu :default-active="active" router class="menu" background-color="#221510"
               text-color="#c9b8a8" active-text-color="#ffffff">
        <el-menu-item index="/admin/dashboard">
          <el-icon><DataBoard /></el-icon>运营看板
        </el-menu-item>
        <el-menu-item-group>
          <template #title><span class="grp-title">交易</span></template>
          <el-menu-item index="/admin/audit"><el-icon><Stamp /></el-icon>商品审核</el-menu-item>
          <el-menu-item index="/admin/products"><el-icon><Goods /></el-icon>商品管理</el-menu-item>
          <el-menu-item index="/admin/orders"><el-icon><Tickets /></el-icon>订单管理</el-menu-item>
        </el-menu-item-group>
        <el-menu-item-group>
          <template #title><span class="grp-title">卖家与用户</span></template>
          <el-menu-item index="/admin/users"><el-icon><UserFilled /></el-icon>用户管理</el-menu-item>
        </el-menu-item-group>
        <el-menu-item-group>
          <template #title><span class="grp-title">智能体</span></template>
          <el-menu-item index="/admin/kb"><el-icon><Collection /></el-icon>知识库</el-menu-item>
        </el-menu-item-group>
        <el-menu-item-group>
          <template #title><span class="grp-title">系统</span></template>
          <el-menu-item index="/admin/thresholds"><el-icon><SetUp /></el-icon>模型与阈值</el-menu-item>
          <el-menu-item index="/admin/logs"><el-icon><Document /></el-icon>审计日志</el-menu-item>
        </el-menu-item-group>
      </el-menu>
    </el-aside>
    <el-container>
      <el-header class="admin-top" height="56px">
        <div class="crumb">{{ pageTitle }}</div>
        <div class="right">
          <span class="who">{{ auth.displayName }}（管理员）</span>
          <el-button size="small" plain @click="onLogout">
            <el-icon style="margin-right:4px"><SwitchButton /></el-icon>退出
          </el-button>
        </div>
      </el-header>
      <el-main class="admin-main">
        <router-view />
      </el-main>
    </el-container>
  </el-container>
</template>

<script setup>
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAuthStore } from '../stores/auth'

const auth = useAuthStore()
const route = useRoute()
const router = useRouter()
const active = computed(() => '/admin/' + (route.path.split('/')[2] || 'dashboard').split('/')[0])
const TITLES = {
  dashboard: '运营看板', audit: '商品审核', products: '商品管理', orders: '订单管理',
  users: '用户管理', kb: '知识库', thresholds: '模型与阈值', logs: '审计日志',
}
const pageTitle = computed(() => TITLES[active.value.split('/')[2]] || '运营后台')

function onLogout() {
  auth.logout()
  router.push('/')
}
</script>

<style scoped>
.admin-shell { min-height: 100vh; }
.aside { background: #221510; }
.brand { display: flex; gap: 10px; align-items: center; padding: 18px 20px 14px; }
.berry { width: 26px; height: 26px; border-radius: 46% 54% 50% 50% / 58% 58% 42% 42%;
  background: radial-gradient(ellipse at 32% 28%, #ee7a5f 0%, #c22f27 52%, #8e1d18 100%); position: relative; flex: none; }
.berry::before { content: ""; position: absolute; top: -6px; left: 52%; width: 3px; height: 8px;
  background: #7a5c33; border-radius: 2px; transform: rotate(-14deg); }
.name { color: #fff; font-weight: 700; font-size: 16px; letter-spacing: 1px; }
.sub { color: #a08b78; font-size: 11px; }
.menu { border-right: none; }
.menu :deep(.el-menu-item-group__title) { padding: 10px 20px 2px; }
.grp-title { font-size: 10.5px; color: #7a6553; letter-spacing: .1em; }
.admin-top { background: #fff; border-bottom: 1px solid var(--line); display: flex; align-items: center;
  justify-content: space-between; padding: 0 24px; }
.crumb { font-weight: 600; }
.who { font-size: 13px; color: var(--ink-3); }
.admin-main { background: var(--bg); padding: 20px 24px; }
</style>
