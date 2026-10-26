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
        <el-menu-item index="/admin/audit">
          <el-icon><Stamp /></el-icon>审核工作台
        </el-menu-item>
        <el-menu-item index="/admin/products">
          <el-icon><Goods /></el-icon>商品管理
        </el-menu-item>
        <el-divider style="border-color:#4a382b" />
        <el-menu-item index="/">
          <el-icon><Position /></el-icon>返回交易端
        </el-menu-item>
      </el-menu>
    </el-aside>
    <el-container>
      <el-header class="admin-top" height="56px">
        <div class="crumb">{{ pageTitle }}</div>
        <div class="who">{{ auth.displayName }}（管理员）</div>
      </el-header>
      <el-main class="admin-main">
        <router-view />
      </el-main>
    </el-container>
  </el-container>
</template>

<script setup>
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import { useAuthStore } from '../stores/auth'

const auth = useAuthStore()
const route = useRoute()
const active = computed(() => '/admin/' + (route.path.split('/')[2] || 'audit').split('/')[0])
const pageTitle = computed(() => ({ audit: '审核工作台', products: '商品管理' }[active.value.split('/')[2]] || '运营后台'))
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
.admin-top { background: #fff; border-bottom: 1px solid var(--line); display: flex; align-items: center;
  justify-content: space-between; padding: 0 24px; }
.crumb { font-weight: 600; }
.who { font-size: 13px; color: var(--ink-3); }
.admin-main { background: var(--bg); padding: 20px 24px; }
</style>
