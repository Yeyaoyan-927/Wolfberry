<template>
  <div class="page">
    <div class="head">
      <h2>售后服务</h2>
      <span class="dim">已发货或已完成的订单可发起售后；举证图与上架评估快照共同作为判定依据</span>
    </div>

    <div class="card">
      <el-radio-group v-model="status" @change="load">
        <el-radio-button :value="undefined">全部</el-radio-button>
        <el-radio-button v-for="s in STATUS" :key="s.v" :value="s.v">{{ s.label }}</el-radio-button>
      </el-radio-group>
    </div>

    <div v-loading="loading">
      <div v-for="t in items" :key="t.id" class="card tk" @click="openDetail(t)">
        <div class="tk-head">
          <span class="tk-no num">{{ t.ticket_no }}</span>
          <span class="st" :class="`st-${t.status}`">{{ t.status_label }}</span>
          <span class="tag-type">{{ t.type_label }}</span>
          <span class="flex1"></span>
          <span class="dim num">{{ (t.created_at || '').slice(0, 16) }}</span>
        </div>
        <div class="tk-title">{{ t.product_title }}</div>
        <div class="tk-reason">{{ t.reason }}</div>
        <div class="tk-foot">
          <span class="dim num">订单 {{ t.order_no }}</span>
          <span v-if="t.refund_amount" class="amount num">申请退款 ¥{{ t.refund_amount }}</span>
          <span class="flex1"></span>
          <el-button size="small" link type="primary">查看处理进度 →</el-button>
        </div>
      </div>
      <el-empty v-if="!loading && !items.length" description="暂无售后工单" />
    </div>

    <!-- 详情 -->
    <el-drawer v-model="drawer" :title="`工单 ${cur?.ticket_no || ''}`" size="46%">
      <template v-if="cur">
        <div class="d-head">
          <span class="st" :class="`st-${cur.status}`">{{ cur.status_label }}</span>
          <span class="tag-type">{{ cur.type_label }}</span>
          <span v-if="cur.refund_amount" class="amount num">¥{{ cur.refund_amount }}</span>
        </div>
        <el-descriptions :column="1" border size="small" class="d-info">
          <el-descriptions-item label="商品">{{ cur.product_title }}</el-descriptions-item>
          <el-descriptions-item label="订单号">{{ cur.order_no }}</el-descriptions-item>
          <el-descriptions-item label="申请说明">{{ cur.reason }}</el-descriptions-item>
          <el-descriptions-item v-if="cur.seller_reply" label="卖家回复">{{ cur.seller_reply }}</el-descriptions-item>
          <el-descriptions-item v-if="cur.resolution" label="处理结论">{{ cur.resolution }}</el-descriptions-item>
        </el-descriptions>

        <div v-if="cur.evidence?.length" class="ev">
          <div class="sec-t">举证图片</div>
          <div class="ev-imgs">
            <el-image v-for="(u, i) in cur.evidence" :key="i" :src="u" :preview-src-list="cur.evidence"
                      fit="cover" class="ev-img" />
          </div>
        </div>

        <div class="sec-t">处理进度</div>
        <el-timeline>
          <el-timeline-item v-for="lg in cur.logs" :key="lg.id"
                            :timestamp="(lg.created_at || '').slice(0, 16)"
                            :type="{ apply: 'primary', agree: 'success', reject: 'danger', escalate: 'warning', resolve: 'success' }[lg.action]">
            <b>{{ { apply: '提交申请', agree: '卖家同意', reject: '卖家拒绝', escalate: '申请平台介入', resolve: '平台裁决' }[lg.action] || lg.action }}</b>
            <span class="dim"> · {{ { buyer: '买家', seller: '卖家', admin: '平台' }[lg.actor_role] || lg.actor_role }}</span>
            <div v-if="lg.note" class="dim">{{ lg.note }}</div>
          </el-timeline-item>
        </el-timeline>

        <!-- 卖家可响应 -->
        <div v-if="isSeller && cur.status === 1" class="acts">
          <el-input v-model="replyNote" type="textarea" :rows="2" placeholder="回复说明（卖家可见）" />
          <div class="act-btns">
            <el-button type="success" :loading="acting" @click="respond(true)">同意并退款</el-button>
            <el-button type="danger" plain :loading="acting" @click="respond(false)">拒绝</el-button>
          </div>
        </div>
        <!-- 买家可申请介入 -->
        <div v-if="isBuyer && [1, 3].includes(cur.status)" class="acts">
          <el-alert type="info" :closable="false"
                    title="对卖家处理结果有异议？可申请平台介入，平台将调取上架时的 AI 评估快照与双方举证进行裁定。" />
          <el-button type="warning" plain :loading="acting" @click="escalate">申请平台介入</el-button>
        </div>
      </template>
    </el-drawer>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { afterSaleDetail, escalateAfterSale, listAfterSales, respondAfterSale } from '../../api'
import { useAuthStore } from '../../stores/auth'

const auth = useAuthStore()
const items = ref([])
const status = ref(undefined)
const loading = ref(false)
const drawer = ref(false)
const cur = ref(null)
const replyNote = ref('')
const acting = ref(false)

const STATUS = [
  { v: 1, label: '待卖家响应' },
  { v: 2, label: '卖家已同意' },
  { v: 3, label: '卖家已拒绝' },
  { v: 4, label: '平台介入中' },
  { v: 5, label: '已解决' },
]
const isSeller = computed(() => auth.role === 'seller')
const isBuyer = computed(() => auth.role === 'buyer')

async function load() {
  loading.value = true
  try {
    const data = await listAfterSales({ status: status.value, size: 50 })
    items.value = data.items || []
  } finally {
    loading.value = false
  }
}

async function openDetail(t) {
  cur.value = await afterSaleDetail(t.id)
  replyNote.value = ''
  drawer.value = true
}

async function respond(agree) {
  acting.value = true
  try {
    cur.value = await respondAfterSale(cur.value.id, { agree, note: replyNote.value })
    ElMessage.success(agree ? '已同意并结案' : '已拒绝，买家可申请平台介入')
    load()
  } finally {
    acting.value = false
  }
}

async function escalate() {
  acting.value = true
  try {
    cur.value = await escalateAfterSale(cur.value.id, '买家申请平台介入')
    ElMessage.success('已提交平台介入，请等待裁定')
    load()
  } finally {
    acting.value = false
  }
}

onMounted(load)
</script>

<style scoped>
.head { display: flex; align-items: baseline; gap: 14px; margin-bottom: 14px; }
.head h2 { margin: 0; font-size: 18px; }
.dim { font-size: 12.5px; color: var(--ink-3); }
.card { padding: 14px 16px; margin-bottom: 12px; }
.tk { cursor: pointer; transition: box-shadow .18s; }
.tk:hover { box-shadow: 0 6px 18px rgba(120, 60, 40, .1); }
.tk-head { display: flex; align-items: center; gap: 8px; margin-bottom: 8px; }
.tk-no { font-size: 12px; color: var(--ink-3); }
.tk-title { font-size: 14px; font-weight: 600; margin-bottom: 4px; }
.tk-reason { font-size: 12.5px; color: var(--ink-2); line-height: 1.6;
  display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden; }
.tk-foot { display: flex; align-items: center; gap: 12px; margin-top: 8px; }
.flex1 { flex: 1; }
.amount { color: var(--brand); font-weight: 700; font-size: 13px; }
.tag-type { font-size: 11.5px; color: var(--ink-3); background: #f3ece7;
  border-radius: 4px; padding: 1px 6px; }
.st { display: inline-block; font-size: 12px; line-height: 18px; padding: 1px 8px;
  border-radius: 4px; border: 1px solid transparent; white-space: nowrap; font-weight: 600; }
.st-1 { color: #b07205; background: #fdf3dd; border-color: #efd9a7; }
.st-2, .st-5 { color: #1d8a4e; background: #e5f6ec; border-color: #bce5cc; }
.st-3 { color: var(--brand); background: var(--brand-soft); border-color: var(--brand-line); }
.st-4 { color: #1f5fa8; background: #e8f1fb; border-color: #c4dcf4; }
.st-6 { color: #8a7462; background: #f1ece7; border-color: #ddd3c9; }
.d-head { display: flex; gap: 10px; align-items: center; margin-bottom: 12px; }
.d-info { margin-bottom: 14px; }
.sec-t { font-weight: 700; font-size: 13px; margin: 14px 0 10px; }
.ev-imgs { display: flex; gap: 8px; flex-wrap: wrap; }
.ev-img { width: 88px; height: 88px; border-radius: 8px; border: 1px solid var(--line); }
.acts { margin-top: 16px; display: flex; flex-direction: column; gap: 10px; }
.act-btns { display: flex; gap: 8px; }
</style>
