<template>
  <el-container class="web-shell">
    <el-header class="topbar" height="60px">
      <div class="topbar-inner">
        <router-link to="/home" class="logo">
          <span class="berry"></span>
          <span class="logo-name">杞市</span>
          <span class="logo-sub">枸杞交易平台</span>
        </router-link>
        <el-menu mode="horizontal" :default-active="active" class="nav" router>
          <el-menu-item index="/home">首页</el-menu-item>
          <el-menu-item index="/products">货源市场</el-menu-item>
          <el-menu-item index="/market">行情中心</el-menu-item>
          <el-menu-item index="/chat">智能问答</el-menu-item>
          <el-menu-item v-if="auth.isLogin" index="/orders">我的订单</el-menu-item>
          <el-menu-item v-if="auth.isLogin" index="/after-sales">售后服务</el-menu-item>
          <el-menu-item v-if="auth.role === 'seller'" index="/my-products">我的商品</el-menu-item>
          <el-menu-item v-if="auth.role === 'seller'" index="/publish">发布货源</el-menu-item>
          <el-menu-item v-if="auth.role === 'seller'" index="/seller/qualification">
            资质认证
            <span v-if="auth.sellerStatus !== 2" class="dot-warn"></span>
          </el-menu-item>
        </el-menu>
        <div class="right">
          <template v-if="auth.isLogin">
            <el-tag v-if="auth.role === 'admin'" size="small" @click="$router.push('/admin/audit')"
                    class="admin-entry" effect="dark">后台管理</el-tag>
            <span class="who link" @click="$router.push('/profile')">{{ auth.displayName }}</span>
            <el-button link @click="onLogout">退出</el-button>
          </template>
        </div>
      </div>
    </el-header>
    <el-main class="main">
      <router-view />
    </el-main>
    <el-footer class="footer" height="48px">
      仅图像外观辅助筛查 · 不检测硫/水分/多糖等内在品质 · 结果仅供交易参考
    </el-footer>
  </el-container>
</template>

<script setup>
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAuthStore } from '../stores/auth'

const auth = useAuthStore()
const route = useRoute()
const router = useRouter()
const active = computed(() => '/' + (route.path.split('/')[1] || ''))

function onLogout() {
  auth.logout()
  router.push('/')
}
</script>

<style scoped>
.web-shell { min-height: 100vh; }
.topbar { background: #fff; border-bottom: 1px solid var(--line); padding: 0; position: sticky; top: 0; z-index: 20; }
.topbar::after {
  content: ""; display: block; height: 2px; margin-top: -1px;
  background: linear-gradient(90deg, transparent, var(--brand) 30%, var(--brand) 70%, transparent);
  opacity: .55;
}
.topbar-inner { max-width: 1200px; margin: 0 auto; display: flex; align-items: center; gap: 28px; height: 58px; padding: 0 16px; }
.logo { display: flex; align-items: center; gap: 8px; }
.berry { width: 22px; height: 22px; border-radius: 46% 54% 50% 50% / 58% 58% 42% 42%;
  background: radial-gradient(ellipse at 32% 28%, #ee7a5f 0%, #c22f27 52%, #8e1d18 100%); position: relative; }
.berry::before { content: ""; position: absolute; top: -5px; left: 52%; width: 3px; height: 7px;
  background: #7a5c33; border-radius: 2px; transform: rotate(-14deg); }
.logo-name { font-weight: 800; font-size: 18px; letter-spacing: 2px; color: var(--brand); }
.logo-sub { font-size: 12px; color: var(--ink-3); margin-top: 3px; }
.nav { flex: 1; border-bottom: none !important; }
.nav .el-menu-item { font-weight: 500; }
.right { display: flex; align-items: center; gap: 10px; }
.admin-entry { cursor: pointer; }
.who { font-size: 13px; color: var(--ink-2); }
.dot-warn { display: inline-block; width: 6px; height: 6px; border-radius: 50%;
  background: var(--brand); margin-left: 4px; vertical-align: super; }
.who.link { cursor: pointer; }
.who.link:hover { color: var(--brand); }
.main { padding: 0; }
.footer { display: flex; align-items: center; justify-content: center; font-size: 12px; color: var(--ink-4);
  border-top: 1px solid var(--line); background: #fff; }
</style>
