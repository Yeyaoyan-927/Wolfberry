<template>
  <div class="page">
    <div class="card profile">
      <div class="avatar">{{ (auth.displayName || 'U').slice(0, 1) }}</div>
      <div class="info">
        <div class="name">{{ auth.displayName || auth.user?.username }}</div>
        <div class="dim">@{{ auth.user?.username }} · {{ roleLabel }} · ID {{ auth.user?.id }}</div>
        <div class="dim" v-if="auth.user?.org_name">{{ auth.user.org_name }}</div>
      </div>
      <div class="ops">
        <el-button v-if="auth.role === 'seller' || auth.role === 'admin'" type="primary" plain @click="$router.push('/my-products')">我的商品</el-button>
        <el-button v-if="auth.role === 'seller' || auth.role === 'admin'" type="primary" @click="$router.push('/publish')">发布货源</el-button>
        <el-button @click="$router.push('/orders')">我的订单</el-button>
      </div>
    </div>

    <el-row :gutter="14" class="row2">
      <el-col :span="12">
        <div class="card block">
          <div class="b-head">账号信息</div>
          <div class="kv">
            <div class="kv-row"><span class="k">用户名</span><span class="v">{{ auth.user?.username }}</span></div>
            <div class="kv-row"><span class="k">角色</span><span class="v">{{ roleLabel }}</span></div>
            <div class="kv-row"><span class="k">组织 / 店铺</span><span class="v">{{ auth.user?.org_name || '—' }}</span></div>
            <div class="kv-row"><span class="k">登录态</span><span class="v">会话级（关闭标签页自动退出）</span></div>
          </div>
          <el-alert type="info" :closable="false" class="tip"
                    title="账号由平台开通；如需修改资料或新增角色，请联系平台运营" />
        </div>
      </el-col>
      <el-col :span="12">
        <div class="card block">
          <div class="b-head">常用入口</div>
          <div class="quick">
            <div class="q" @click="$router.push('/products')">货源市场<span class="dim">浏览与筛选在售货源</span></div>
            <div class="q" @click="$router.push('/market')">行情中心<span class="dim">品种/等级价格走势</span></div>
            <div class="q" @click="$router.push('/chat')">智能问答<span class="dim">标准、行情、选品建议</span></div>
            <div class="q" @click="onLogout">退出登录<span class="dim">清除本标签页登录态</span></div>
          </div>
        </div>
      </el-col>
    </el-row>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '../../stores/auth'

const auth = useAuthStore()
const router = useRouter()
const roleLabel = computed(() => ({ admin: '管理员', seller: '卖家', buyer: '买家' }[auth.role] || '—'))

function onLogout() {
  auth.logout()
  router.push('/')
}
</script>

<style scoped>
.profile { display: flex; align-items: center; gap: 18px; padding: 24px 28px; }
.avatar { width: 64px; height: 64px; border-radius: 50%; flex: none;
  background: radial-gradient(ellipse at 32% 28%, #ee7a5f 0%, #c22f27 52%, #8e1d18 100%);
  color: #fff; font-size: 26px; font-weight: 700; display: grid; place-items: center; }
.name { font-size: 20px; font-weight: 700; }
.dim { font-size: 12.5px; color: var(--ink-3); margin-top: 2px; }
.ops { margin-left: auto; display: flex; gap: 10px; }
.row2 { margin-top: 14px; }
.block { padding: 16px 20px; }
.b-head { font-weight: 700; margin-bottom: 12px; }
.kv-row { display: flex; justify-content: space-between; font-size: 13px; padding: 6px 0;
  border-bottom: 1px dashed var(--line); }
.kv-row:last-child { border-bottom: none; }
.kv-row .k { color: var(--ink-3); }
.tip { margin-top: 12px; }
.quick { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; }
.q { border: 1px solid var(--line); border-radius: 8px; padding: 10px 12px; font-size: 13.5px;
  font-weight: 600; cursor: pointer; }
.q:hover { border-color: var(--brand); color: var(--brand); }
.q .dim { display: block; font-weight: 400; margin-top: 3px; }
</style>
