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

      <el-radio-group v-model="mode" class="mode">
        <el-radio-button value="login">登录</el-radio-button>
        <el-radio-button value="register">注册</el-radio-button>
      </el-radio-group>

      <!-- 登录 -->
      <el-form v-if="mode === 'login'" @keyup.enter="onSubmit">
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

      <!-- 注册：先选身份，再填资料 -->
      <el-form v-else label-position="top" @keyup.enter="onRegister">
        <el-form-item label="我是">
          <el-radio-group v-model="reg.role" class="role-pick">
            <el-radio-button value="buyer">买家 · 采购枸杞</el-radio-button>
            <el-radio-button value="seller">卖家 · 供货出售</el-radio-button>
          </el-radio-group>
        </el-form-item>
        <div class="role-tip">
          {{ reg.role === 'buyer'
            ? '买家可浏览货源、下单、申请售后、评价商品。'
            : '卖家注册后需提交资质并通过平台审核，才能发布商品。' }}
        </div>
        <el-form-item label="用户名" required>
          <el-input v-model="reg.username" placeholder="4~32 位字母、数字或下划线" />
        </el-form-item>
        <el-form-item label="密码" required>
          <el-input v-model="reg.password" type="password" show-password placeholder="至少 6 位" />
        </el-form-item>
        <el-form-item :label="reg.role === 'seller' ? '企业/合作社名称' : '昵称'" :required="reg.role === 'seller'">
          <el-input v-model="reg.org_name" v-if="reg.role === 'seller'" placeholder="如：中宁XX枸杞合作社" />
          <el-input v-model="reg.display_name" v-else placeholder="如：银川百味食品" />
        </el-form-item>
        <el-form-item label="手机号（选填，仅存掩码）">
          <el-input v-model="reg.contact_phone" placeholder="用于联系，不公开展示" />
        </el-form-item>
        <el-button type="primary" size="large" class="btn" :loading="regLoading" @click="onRegister">
          注册并登录
        </el-button>
      </el-form>

      <el-divider v-if="mode === 'login'">演示账号（点击填入）</el-divider>
      <div v-if="mode === 'login'" class="demo">
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
import { onMounted, reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { login, register } from '../api'
import { useAuthStore } from '../stores/auth'

const mode = ref('login')
const route0 = useRoute()
const form = reactive({ username: '', password: '' })
const reg = reactive({
  role: 'buyer', username: '', password: '', display_name: '', org_name: '', contact_phone: '',
})
const regLoading = ref(false)
const loading = ref(false)
const router = useRouter()
const route = useRoute()
const auth = useAuthStore()

onMounted(() => {
  if (String(route0.query.mode || '') === 'register') mode.value = 'register'
})

onMounted(() => {
  if (String(route0.query.mode || '') === 'register') mode.value = 'register'
})

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

async function onRegister() {
  if (!reg.username || reg.username.length < 4) return ElMessage.warning('用户名至少 4 位')
  if (!/^[a-zA-Z0-9_]+$/.test(reg.username)) return ElMessage.warning('用户名只能包含字母、数字和下划线')
  if (reg.password.length < 6) return ElMessage.warning('密码至少 6 位')
  if (reg.role === 'seller' && reg.org_name.trim().length < 2) return ElMessage.warning('请填写企业/合作社名称')

  regLoading.value = true
  try {
    const data = await register({
      username: reg.username.trim(),
      password: reg.password,
      role: reg.role,
      display_name: reg.role === 'seller' ? reg.org_name : reg.display_name,
      org_name: reg.role === 'seller' ? reg.org_name : '',
      contact_phone: reg.contact_phone,
    })
    auth.setAuth(data.access_token, data.user)
    ElMessage.closeAll()
    if (reg.role === 'seller') {
      ElMessage.success('注册成功，请先提交资质认证后再发布商品')
      router.push('/seller/qualification')
    } else {
      ElMessage.success('注册成功')
      router.push('/home')
    }
  } finally {
    regLoading.value = false
  }
}

async function onSubmit() {
  if (!form.username || !form.password) return ElMessage.warning('请输入用户名与密码')
  loading.value = true
  try {
    const data = await login(form.username, form.password)
    auth.setAuth(data.access_token, data.user || { username: form.username, role: data.role })
    ElMessage.closeAll() // 清掉登录前残留的旧提示（如过期会话的 403）
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
.mode { display: flex; margin-bottom: 18px; }
.mode :deep(.el-radio-button) { flex: 1; }
.mode :deep(.el-radio-button__inner) { width: 100%; }
.role-pick { display: flex; width: 100%; }
.role-pick :deep(.el-radio-button) { flex: 1; }
.role-pick :deep(.el-radio-button__inner) { width: 100%; }
.role-tip { font-size: 12px; color: var(--ink-3); line-height: 1.7; margin: -4px 0 14px;
  background: var(--brand-soft); border-radius: 6px; padding: 8px 10px; }
.demo { display: flex; flex-wrap: wrap; gap: 8px; justify-content: center; }
.demo-tag { cursor: pointer; }
.disclaimer { margin-top: 18px; font-size: 11.5px; color: var(--ink-4); line-height: 1.6; text-align: center; }
</style>
