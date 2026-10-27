<template>
  <div class="login-wrap">
    <div class="login-card">
      <div class="head">
        <span class="berry"></span>
        <div>
          <div class="t">杞市 · 枸杞交易平台</div>
          <div class="s">卖家上传实拍 → AI 外观评估 → 平台审核 → 买家下单</div>
        </div>
      </div>

      <el-form @keyup.enter="onSubmit">
        <el-form-item>
          <el-input v-model="form.username" placeholder="用户名" size="large">
            <template #prefix><el-icon><User /></el-icon></template>
          </el-input>
        </el-form-item>
        <el-form-item>
          <el-input v-model="form.password" type="password" show-password placeholder="密码" size="large">
            <template #prefix><el-icon><Lock /></el-icon></template>
          </el-input>
        </el-form-item>
        <el-button type="primary" size="large" class="btn" :loading="loading" @click="onSubmit">
          登 录
        </el-button>
      </el-form>

      <el-divider>演示账号（点击填入）</el-divider>
      <div class="demo">
        <el-tag v-for="acc in demos" :key="acc.u" class="demo-tag" effect="plain"
                @click="fill(acc.u, acc.p)">{{ acc.label }}</el-tag>
      </div>

      <div class="disclaimer">
        本系统仅基于图片做枸杞外观辅助筛查，无法检测熏硫、水分、多糖等内在品质；结果仅供交易参考。
      </div>
    </div>
  </div>
</template>

<script setup>
import { reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { login } from '../api'
import { useAuthStore } from '../stores/auth'

const form = reactive({ username: '', password: '' })
const loading = ref(false)
const router = useRouter()
const route = useRoute()
const auth = useAuthStore()

const demos = [
  { label: '买家 buyer1', u: 'buyer1', p: 'buyer123' },
  { label: '卖家 seller1', u: 'seller1', p: 'seller123' },
  { label: '卖家 seller2', u: 'seller2', p: 'seller123' },
  { label: '管理员 admin', u: 'admin', p: 'admin123' },
]

function fill(u, p) {
  form.username = u
  form.password = p
}

async function onSubmit() {
  if (!form.username || !form.password) return ElMessage.warning('请输入用户名与密码')
  loading.value = true
  try {
    const data = await login(form.username, form.password)
    auth.setAuth(data.access_token, data.user || { username: form.username, role: data.role })
    ElMessage.success('登录成功')
    router.push(route.query.redirect || (auth.role === 'admin' ? '/admin/audit' : '/home'))
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.login-wrap { min-height: 100vh; display: flex; align-items: center; justify-content: center;
  background:
    radial-gradient(circle at 88% -8%, rgba(194,47,39,.10), rgba(194,47,39,.03) 38%, transparent 60%),
    var(--bg); }
.login-card { width: 400px; background: #fff; border: 1px solid var(--line); border-radius: 16px;
  padding: 32px 34px 24px; box-shadow: 0 10px 40px rgba(120,60,40,.08); }
.head { display: flex; gap: 12px; align-items: center; margin-bottom: 24px; }
.berry { width: 40px; height: 40px; border-radius: 46% 54% 50% 50% / 58% 58% 42% 42%;
  background: radial-gradient(ellipse at 32% 28%, #ee7a5f 0%, #c22f27 52%, #8e1d18 100%); position: relative; flex: none; }
.berry::before { content: ""; position: absolute; top: -9px; left: 52%; width: 4px; height: 12px;
  background: #7a5c33; border-radius: 2px; transform: rotate(-14deg); }
.t { font-weight: 800; font-size: 17px; }
.s { font-size: 12px; color: var(--ink-3); margin-top: 2px; }
.btn { width: 100%; }
.demo { display: flex; flex-wrap: wrap; gap: 8px; justify-content: center; }
.demo-tag { cursor: pointer; }
.disclaimer { margin-top: 18px; font-size: 11.5px; color: var(--ink-4); line-height: 1.6; text-align: center; }
</style>
