<template>
  <div class="page" v-loading="loading">
    <el-breadcrumb class="crumb">
      <el-breadcrumb-item to="/">首页</el-breadcrumb-item>
      <el-breadcrumb-item to="/products">货源市场</el-breadcrumb-item>
      <el-breadcrumb-item>{{ p.title || '商品详情' }}</el-breadcrumb-item>
    </el-breadcrumb>

    <div class="detail" v-if="p.id">
      <!-- 左：图片 -->
      <div class="gallery card">
        <div class="gmain" :style="mainImg ? `background-image:url('${mainImg}')` : ''"></div>
        <div class="thumbs">
          <div v-for="(im, i) in p.images" :key="im.id" class="thumb"
               :class="{ on: i === cur }" :style="`background-image:url('${im.url}')`" @mouseenter="cur = i"></div>
        </div>
      </div>

      <!-- 中：信息 -->
      <div class="info card">
        <h1>{{ p.title }}</h1>
        <div class="claim">
          <GradeTag :grade="p.grade_platform || p.grade_claim" />
          <span class="dim">卖家自述</span>
          <GradeTag :grade="p.grade_claim" />
          <template v-if="p.grade_platform">
            <span class="dim">→ 平台认定</span>
            <GradeTag :grade="p.grade_platform" />
          </template>
          <DiffFlag :flag="flag" :gap="p.grade_diff" />
        </div>

        <div class="price-row">
          <span class="price num">¥{{ p.unit_price }}</span><span class="per">/kg</span>
          <span class="stock dim">库存 {{ p.stock }}kg · 起订 {{ p.min_order_qty }}kg</span>
        </div>

        <el-descriptions :column="2" border size="small" class="specs">
          <el-descriptions-item label="品种">{{ p.variety }}</el-descriptions-item>
          <el-descriptions-item label="产区">{{ p.origin }}</el-descriptions-item>
          <el-descriptions-item label="规格">{{ p.spec_per_50g }} 粒 / 50g</el-descriptions-item>
          <el-descriptions-item label="状态">{{ statusLabel }}</el-descriptions-item>
        </el-descriptions>

        <div class="buy">
          <el-input-number v-model="qty" :min="Number(p.min_order_qty)" :max="Number(p.stock)" :step="10" />
          <span class="dim">kg</span>
          <el-button type="primary" size="large" :disabled="p.status !== 3" @click="onBuy">
            立即下单 · 合计 ¥{{ (qty * Number(p.unit_price)).toFixed(2) }}
          </el-button>
        </div>

        <el-divider />
        <div class="desc">
          <h3>商品描述</h3>
          <p>{{ p.description || '—' }}</p>
        </div>
      </div>

      <!-- 右：AI 评估卡 -->
      <div class="assess card">
        <div class="a-head">
          <span class="berry"></span>
          <b>平台 AI 外观评估</b>
        </div>
        <template v-if="p.defect_ratio !== null">
          <div class="a-grade">
            建议等级 <GradeTag :grade="p.ai_grade || '灰（不参与判定）'" />
          </div>
          <div class="a-grid num">
            <div><b>{{ (p.defect_ratio * 100).toFixed(2) }}%</b><span>综合缺陷率</span></div>
            <div><b>{{ ((p.moldy_ratio ?? 0) * 100).toFixed(2) }}%</b><span>霉变率</span></div>
            <div><b>{{ p.grain_count ?? '—' }}</b><span>识别粒数</span></div>
            <div><b>{{ p.ai_confidence ?? '—' }}</b><span>加权置信度</span></div>
          </div>
          <el-alert type="info" :closable="false" show-icon
                    title="评估为平台审核依据，快照已留痕" description="仅外观筛查，不检测硫/水分/多糖等内在品质；疑似问题请人工复核或送第三方检测。" />
        </template>
        <el-empty v-else :image-size="70" description="AI 评估中 / 未评估，可正常下单，评估完成后展示" />
      </div>
    </div>

    <!-- 下单对话框 -->
    <el-dialog v-model="buyDialog" title="确认订单" width="440px">
      <el-descriptions :column="1" border>
        <el-descriptions-item label="商品">{{ p.title }}</el-descriptions-item>
        <el-descriptions-item label="单价">¥{{ p.unit_price }} /kg</el-descriptions-item>
        <el-descriptions-item label="数量">{{ qty }} kg</el-descriptions-item>
        <el-descriptions-item label="合计">
          <b class="text-brand num">¥{{ (qty * Number(p.unit_price)).toFixed(2) }}</b>
        </el-descriptions-item>
      </el-descriptions>
      <div class="pay-note">支付方式：线下支付（平台仅登记状态与凭证）</div>
      <template #footer>
        <el-button @click="buyDialog = false">取消</el-button>
        <el-button type="primary" :loading="buying" @click="submitBuy">提交订单</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { createOrder, getProduct } from '../../api'
import { useAuthStore } from '../../stores/auth'
import GradeTag from '../../components/GradeTag.vue'
import DiffFlag from '../../components/DiffFlag.vue'

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()
const p = ref({})
const cur = ref(0)
const qty = ref(50)
const loading = ref(true)
const buyDialog = ref(false)
const buying = ref(false)

const mainImg = computed(() => p.value.images?.[cur.value]?.url || p.value.cover_url || '')
const statusLabel = computed(() => ({ 1: '待审核', 3: '在售', 4: '已驳回', 5: '已下架' }[p.value.status] || '—'))
const flag = computed(() => {
  const conf = p.value.ai_confidence ?? null
  if (!p.value.ai_grade || (conf !== null && conf < 0.45)) return '灰'
  if ((p.value.grade_diff ?? 0) >= 2) return '红'
  if (p.value.grade_diff === 1) return '黄'
  if (p.value.grade_diff < 0) return '蓝'
  return '绿'
})

function onBuy() {
  if (!auth.isLogin) return router.push({ name: 'login', query: { redirect: route.fullPath } })
  if (auth.role !== 'buyer') return ElMessage.warning('仅买家账号可下单（当前：' + auth.role + '）')
  buyDialog.value = true
}

async function submitBuy() {
  buying.value = true
  try {
    const order = await createOrder(p.value.id, qty.value)
    ElMessage.success(`下单成功，订单号 ${order.order_no}，等待卖家确认`)
    buyDialog.value = false
    router.push('/orders')
  } finally {
    buying.value = false
  }
}

onMounted(async () => {
  try {
    p.value = await getProduct(route.params.id)
    qty.value = Number(p.value.min_order_qty)
  } finally {
    loading.value = false
  }
})
</script>

<style scoped>
.crumb { margin: 16px 0; }
.detail { display: grid; grid-template-columns: 400px minmax(0, 1fr) 300px; gap: 16px; align-items: start; }
.gallery { padding: 14px; }
.gmain { height: 320px; border-radius: 8px; background: #f3ebe4 center/cover no-repeat; }
.thumbs { display: flex; gap: 8px; margin-top: 10px; }
.thumb { width: 64px; height: 64px; border-radius: 6px; background: #f3ebe4 center/cover no-repeat;
  border: 2px solid transparent; cursor: pointer; }
.thumb.on { border-color: var(--brand); }
.info { padding: 22px 24px; }
.info h1 { margin: 0 0 12px; font-size: 20px; line-height: 1.5; }
.claim { display: flex; align-items: center; gap: 8px; margin-bottom: 16px; flex-wrap: wrap; }
.dim { font-size: 12px; color: var(--ink-3); }
.price-row { display: flex; align-items: baseline; gap: 6px; background: var(--brand-soft);
  border-radius: 8px; padding: 12px 16px; margin-bottom: 16px; }
.price { color: var(--brand); font-size: 28px; font-weight: 800; }
.per { color: var(--ink-3); }
.stock { margin-left: auto; }
.specs { margin-bottom: 16px; }
.buy { display: flex; gap: 10px; align-items: center; }
.desc h3 { font-size: 14px; margin: 0 0 8px; }
.desc p { color: var(--ink-2); font-size: 13.5px; line-height: 1.8; margin: 0; white-space: pre-wrap; }
.assess { padding: 18px; position: sticky; top: 76px; }
.a-head { display: flex; align-items: center; gap: 8px; margin-bottom: 14px; }
.berry { width: 18px; height: 18px; border-radius: 46% 54% 50% 50% / 58% 58% 42% 42%;
  background: radial-gradient(ellipse at 32% 28%, #ee7a5f 0%, #c22f27 52%, #8e1d18 100%); }
.a-grade { margin-bottom: 12px; font-size: 13px; display: flex; gap: 8px; align-items: center; }
.a-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; margin-bottom: 14px; }
.a-grid > div { background: var(--brand-soft); border-radius: 8px; padding: 10px 12px; }
.a-grid b { display: block; font-size: 18px; color: var(--brand); }
.a-grid span { font-size: 11.5px; color: var(--ink-3); }
.pay-note { margin-top: 10px; font-size: 12px; color: var(--ink-3); }
@media (max-width: 1100px) { .detail { grid-template-columns: 1fr; } }
</style>
