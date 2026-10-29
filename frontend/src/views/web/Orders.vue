<template>
  <div class="page">
    <div class="head">
      <h2>{{ isBuyer ? '我的订单' : '我收到的订单' }}</h2>
      <el-radio-group v-model="status" @change="load">
        <el-radio-button :value="undefined">全部</el-radio-button>
        <el-radio-button v-for="(label, st) in STATUS" :key="st" :value="Number(st)">{{ label }}</el-radio-button>
      </el-radio-group>
    </div>

    <el-alert v-if="isBuyer && pendingCount" type="warning" :closable="false" class="pending-tip"
              :title="`你有 ${pendingCount} 笔已完成订单还没评价，评价会帮助其他买家判断`">
      <template #default>
        <el-button size="small" type="primary" plain @click="openFirstPending">去评价</el-button>
      </template>
    </el-alert>

    <div class="card list" v-loading="loading">
      <div v-for="o in items" :key="o.id" class="orow">
        <div class="o-main">
          <div class="o-title">
            <span class="no num">{{ o.order_no }}</span>
            <el-tag size="small" :type="tagType(o.status)">{{ o.status_label }}</el-tag>
            <el-tag v-if="o.pay_status === 1" size="small" type="success" effect="plain">已登记支付</el-tag>
          </div>
          <div class="o-name">{{ o.product_title }}</div>
          <div class="o-meta dim num">
            {{ o.quantity }}kg × ¥{{ o.unit_price }} = <b class="text-brand">¥{{ o.total_amount }}</b>
            <template v-if="o.ship_company"> · {{ o.ship_company }} {{ o.ship_no }}</template>
            <template v-if="o.cancel_reason"> · 取消原因：{{ o.cancel_reason }}</template>
          </div>
          <!-- 状态时间线 -->
          <div class="tl" v-if="o.status !== 5">
            <div v-for="(node, i) in tlNodes(o)" :key="i" class="tl-node">
              <span class="tl-dot" :class="{ on: node.done, cur: node.cur }"></span>
              <span class="tl-line" v-if="i < 3" :class="{ on: node.done }"></span>
              <span class="tl-label" :class="{ dim2: !node.done }">{{ node.label }}</span>
            </div>
          </div>
          <div class="tl cancelled" v-else><el-tag size="small" type="info">订单已取消 · 冻结库存已归还</el-tag></div>
        </div>
        <div class="o-ops">
          <template v-if="isMySale(o)">
            <el-button size="small" type="primary" v-if="o.status === 1" @click="doConfirm(o)">确认订单</el-button>
            <el-button size="small" type="primary" v-if="o.status === 2" @click="openShip(o)">发货</el-button>
          </template>
          <template v-if="isMyBuy(o)">
            <el-button size="small" type="success" v-if="o.status === 3" @click="doReceive(o)">确认收货</el-button>
            <el-button size="small" plain v-if="o.status === 1 && o.pay_status === 0" @click="doPay(o)">登记支付</el-button>
            <el-button size="small" plain type="danger" v-if="[1, 2].includes(o.status)" @click="doCancel(o)">取消</el-button>
            <el-button size="small" plain type="warning" v-if="o.status === 4 && isBuyer" @click="openAfterSale(o)">申请售后</el-button>
            <el-button size="small" type="primary" plain v-if="o.status === 4 && isBuyer" @click="openReview(o)">评价</el-button>
          </template>
        </div>
      </div>
      <el-empty v-if="!loading && !items.length" description="暂无订单" />
    </div>

    <!-- 发货对话框 -->
    <ReviewDialog v-model="revDialog" :order="revOrder" @done="onReviewed" />

    <!-- 申请售后 -->
    <el-dialog v-model="asDialog" title="申请售后" width="520px">
      <el-alert type="info" :closable="false" class="as-tip"
                title="平台会调取该商品上架时的 AI 评估快照与你的举证图比对，作为裁定依据；请如实描述并上传能说明问题的照片。" />
      <el-form label-width="88px">
        <el-form-item label="问题类型" required>
          <el-radio-group v-model="asForm.type">
            <el-radio-button :value="1">质量问题</el-radio-button>
            <el-radio-button :value="2">数量不符</el-radio-button>
            <el-radio-button :value="3">与描述不符</el-radio-button>
            <el-radio-button :value="4">物流问题</el-radio-button>
            <el-radio-button :value="5">其他</el-radio-button>
          </el-radio-group>
        </el-form-item>
        <el-form-item label="申请说明" required>
          <el-input v-model="asForm.reason" type="textarea" :rows="3" maxlength="500" show-word-limit
                    placeholder="例如：底层约三分之一出现霉变，开箱视频与照片已上传" />
        </el-form-item>
        <el-form-item label="退款金额">
          <el-input-number v-model="asForm.refund_amount" :min="0" :precision="2" :step="10" />
          <span class="dim" style="margin-left:8px">元（整单退款可填订单金额 {{ asOrder?.total_amount }}）</span>
        </el-form-item>
        <el-form-item label="举证图片">
          <div class="as-upload">
            <div v-for="(u, i) in asForm.evidence" :key="i" class="as-img" :style="{ backgroundImage: `url(${u})` }" />
            <el-upload :show-file-list="false" accept="image/*" :http-request="uploadEvidence" class="as-add">
              <div class="as-add-box">＋</div>
            </el-upload>
          </div>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="asDialog = false">取消</el-button>
        <el-button type="primary" :loading="asSubmitting" @click="submitAfterSale">提交申请</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="shipDialog" title="发货（登记物流信息）" width="420px">
      <el-form label-width="80px">
        <el-form-item label="物流公司">
          <el-input v-model="shipForm.company" placeholder="如：顺丰速运" />
        </el-form-item>
        <el-form-item label="运单号">
          <el-input v-model="shipForm.no" placeholder="运单号" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="shipDialog = false">取消</el-button>
        <el-button type="primary" @click="submitShip">确认发货</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  applyAfterSale, cancelOrder, confirmOrder, listOrders, receiveOrder,
  registerPay, shipOrder, uploadImage,
} from '../../api'
import { useAuthStore } from '../../stores/auth'
import { pendingReviews } from '../../api'
import ReviewDialog from './ReviewDialog.vue'

const STATUS = { 1: '待确认', 2: '待发货', 3: '已发货', 4: '已完成', 5: '已取消' }
const auth = useAuthStore()
const router = useRouter()
const isBuyer = computed(() => auth.role === 'buyer')
const revDialog = ref(false)
const revOrder = ref(null)
const pendingCount = ref(0)
const pendingList = ref([])
const asDialog = ref(false)
const asOrder = ref(null)
const asSubmitting = ref(false)
const asForm = ref({ type: 1, reason: '', refund_amount: 0, evidence: [] })
const items = ref([])
const loading = ref(false)
const status = ref(undefined)
const shipDialog = ref(false)
const shipForm = ref({ id: null, company: '', no: '' })

const isMyBuy = (o) => auth.role === 'buyer' && o.buyer_id === auth.user?.id
const isMySale = (o) => ['seller', 'admin'].includes(auth.role) && o.seller_id === auth.user?.id

const tagType = (st) => ({ 1: 'warning', 2: 'primary', 3: 'primary', 4: 'success', 5: 'info' }[st])

// 时间线节点：下单 → 确认 → 发货 → 收货
function tlNodes(o) {
  const nodes = [
    { label: '下单', done: true, cur: o.status === 1 },
    { label: '确认', done: o.status >= 2, cur: o.status === 2 },
    { label: '发货', done: o.status >= 3, cur: o.status === 3 },
    { label: '收货', done: o.status >= 4, cur: o.status === 4 },
  ]
  return nodes
}

async function load() {
  loading.value = true
  try {
    const data = await listOrders({ status: status.value })
    items.value = data.items
  } finally {
    loading.value = false
  }
}

async function doConfirm(o) {
  await confirmOrder(o.id)
  ElMessage.success('已确认，请尽快发货')
  load()
}

function openShip(o) {
  shipForm.value = { id: o.id, company: '', no: '' }
  shipDialog.value = true
}

async function submitShip() {
  const f = shipForm.value
  if (!f.company || !f.no) return ElMessage.warning('请填写物流公司与运单号')
  await shipOrder(f.id, { ship_company: f.company, ship_no: f.no })
  ElMessage.success('已发货')
  shipDialog.value = false
  load()
}

async function doReceive(o) {
  await ElMessageBox.confirm(`确认已收到货？订单 ${o.order_no} 将变为已完成`, '确认收货')
  await receiveOrder(o.id)
  ElMessage.success('交易完成')
  load()
}

async function doCancel(o) {
  const { value } = await ElMessageBox.prompt('请输入取消原因', '取消订单', { inputValue: '拍错了' })
  await cancelOrder(o.id, value || '')
  ElMessage.success('已取消，冻结库存已归还')
  load()
}

async function doPay(o) {
  await ElMessageBox.confirm('线下支付完成后，在此登记支付状态（平台不接支付通道）', '登记支付')
  await registerPay(o.id, '')
  ElMessage.success('已登记')
  load()
}

function openAfterSale(o) {
  asOrder.value = o
  asForm.value = { type: 1, reason: '', refund_amount: Number(o.total_amount) || 0, evidence: [] }
  asDialog.value = true
}

async function uploadEvidence({ file }) {
  const r = await uploadImage(file)
  asForm.value.evidence.push(r.url)
}

async function submitAfterSale() {
  if (asForm.value.reason.trim().length < 5) return ElMessage.warning('请填写申请说明（至少 5 字）')
  asSubmitting.value = true
  try {
    const t = await applyAfterSale(asOrder.value.id, asForm.value)
    ElMessage.success(`已提交售后工单 ${t.ticket_no}，等待卖家响应`)
    asDialog.value = false
    router.push('/after-sales')
  } finally {
    asSubmitting.value = false
  }
}

async function loadPending() {
  if (!isBuyer.value) return
  try {
    pendingList.value = await pendingReviews()
    pendingCount.value = (pendingList.value || []).filter((p) => !p.has_open_after_sale).length
  } catch {
    pendingCount.value = 0
  }
}

function openReview(o) {
  revOrder.value = {
    order_id: o.id, order_no: o.order_no, product_title: o.product_title,
    product_id: o.product_id, total_amount: o.total_amount,
  }
  revDialog.value = true
}

function openFirstPending() {
  const p = pendingList.value.find((x) => !x.has_open_after_sale)
  if (p) {
    revOrder.value = p
    revDialog.value = true
  }
}

function onReviewed() {
  load()
  loadPending()
}

onMounted(() => { load(); loadPending() })
</script>

<style scoped>
.head { display: flex; justify-content: space-between; align-items: center; margin-bottom: 14px; }
.head h2 { margin: 0; font-size: 18px; }
.list { padding: 6px 20px; }
.orow { display: flex; align-items: center; gap: 16px; padding: 16px 0; border-bottom: 1px solid var(--line); }
.orow:last-child { border-bottom: none; }
.o-main { flex: 1; min-width: 0; }
.o-title { display: flex; gap: 10px; align-items: center; }
.no { font-size: 12px; color: var(--ink-3); }
.o-name { font-size: 14px; font-weight: 600; margin: 6px 0 4px; }
.o-meta { font-size: 12.5px; }
.pending-tip { margin-bottom: 12px; }
.pending-tip :deep(.el-alert__content) { display: flex; align-items: center; gap: 12px; }
.tl { display: flex; align-items: center; gap: 0; margin-top: 10px; }
.tl-node { display: flex; align-items: center; }
.tl-dot { width: 9px; height: 9px; border-radius: 50%; background: #ddd3c9; flex: none; }
.tl-dot.on { background: var(--brand); }
.tl-dot.cur { box-shadow: 0 0 0 3px var(--brand-soft); }
.tl-line { width: 44px; height: 2px; background: #ddd3c9; margin: 0 6px; }
.tl-line.on { background: var(--brand); }
.tl-label { font-size: 11px; margin-left: 4px; color: var(--brand); }
.tl-label.dim2 { color: var(--ink-4); }
.tl.cancelled { margin-top: 8px; }
.o-ops { display: flex; gap: 8px; flex: none; }
</style>
