<template>
  <div class="lr">
    <!-- 左树：状态 + 待办优先级 -->
    <div class="tree card">
      <div class="t-head">工单状态</div>
      <div class="t-node" :class="{ on: status === undefined }" @click="pick(undefined)">
        全部<span class="cnt num">{{ stats.total || 0 }}</span>
      </div>
      <div v-for="s in STATES" :key="s.v" class="t-node" :class="{ on: status === s.v }" @click="pick(s.v)">
        {{ s.label }}<span class="cnt num">{{ stats.by_status?.[s.v] || 0 }}</span>
      </div>
      <el-divider style="margin:10px 0" />
      <div class="t-head">待处理</div>
      <div class="todo">
        <div class="todo-row"><span>待卖家响应</span><b class="num">{{ stats.pending || 0 }}</b></div>
        <div class="todo-row"><span>平台介入中</span><b class="num warn">{{ stats.escalated || 0 }}</b></div>
        <div class="todo-row"><span>已解决</span><b class="num ok">{{ stats.resolved || 0 }}</b></div>
      </div>
      <div class="tip">介入中的工单需平台裁定：调取上架评估快照 + 双方举证，给出支持买家 / 支持卖家 / 部分退款结论。</div>
    </div>

    <!-- 右表 -->
    <div class="card table-card">
      <div class="bar">
        <span class="dim num">共 {{ total }} 条工单</span>
        <span class="flex1"></span>
        <el-button size="small" plain @click="load">刷新</el-button>
      </div>

      <el-alert v-if="loadError" type="error" :closable="false" :title="`加载失败：${loadError}`" class="mb" />

      <el-table :data="items" v-loading="loading" :header-cell-style="{ background: '#faf6f3' }"
                @row-click="openDetail" row-class-name="clickable">
        <el-table-column label="工单" width="150">
          <template #default="{ row }">
            <div class="num t-no">{{ row.ticket_no }}</div>
            <div class="dim num">{{ (row.created_at || '').slice(5, 16) }}</div>
          </template>
        </el-table-column>
        <el-table-column label="商品" min-width="180">
          <template #default="{ row }">
            <div class="t-title">{{ row.product_title }}</div>
            <div class="dim num">{{ row.order_no }}</div>
          </template>
        </el-table-column>
        <el-table-column label="类型" width="96" align="center">
          <template #default="{ row }"><span class="tag-type">{{ row.type_label }}</span></template>
        </el-table-column>
        <el-table-column label="金额" width="90" align="right">
          <template #default="{ row }">
            <span class="num amount">{{ row.refund_amount ? `¥${row.refund_amount}` : '—' }}</span>
          </template>
        </el-table-column>
        <el-table-column label="状态" width="104" align="center">
          <template #default="{ row }">
            <span class="st" :class="`st-${row.status}`">{{ row.status_label }}</span>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="110" align="center">
          <template #default="{ row }">
            <el-button v-if="[1, 3, 4].includes(row.status)" size="small" type="primary" link
                       @click.stop="openResolve(row)">裁定</el-button>
            <span v-else class="dim">已结案</span>
          </template>
        </el-table-column>
      </el-table>
      <el-empty v-if="!loading && !items.length" description="暂无工单" />
    </div>

    <!-- 详情 -->
    <el-drawer v-model="drawer" :title="`工单 ${cur?.ticket_no || ''}`" size="46%">
      <template v-if="cur">
        <div class="d-head">
          <span class="st" :class="`st-${cur.status}`">{{ cur.status_label }}</span>
          <span class="tag-type">{{ cur.type_label }}</span>
          <span v-if="cur.refund_amount" class="amount num">¥{{ cur.refund_amount }}</span>
        </div>
        <el-descriptions :column="1" border size="small">
          <el-descriptions-item label="商品">{{ cur.product_title }}</el-descriptions-item>
          <el-descriptions-item label="订单">{{ cur.order_no }}</el-descriptions-item>
          <el-descriptions-item label="买家 ID">{{ cur.buyer_id }}</el-descriptions-item>
          <el-descriptions-item label="卖家 ID">{{ cur.seller_id }}</el-descriptions-item>
          <el-descriptions-item label="申请说明">{{ cur.reason }}</el-descriptions-item>
          <el-descriptions-item v-if="cur.seller_reply" label="卖家回复">{{ cur.seller_reply }}</el-descriptions-item>
          <el-descriptions-item v-if="cur.resolution" label="处理结论">{{ cur.resolution }}</el-descriptions-item>
        </el-descriptions>

        <div v-if="cur.evidence?.length" class="ev">
          <div class="sec-t">买家举证</div>
          <div class="ev-imgs">
            <el-image v-for="(u, i) in cur.evidence" :key="i" :src="u" :preview-src-list="cur.evidence"
                      fit="cover" class="ev-img" />
          </div>
        </div>

        <div class="sec-t">处理轨迹</div>
        <el-timeline>
          <el-timeline-item v-for="lg in cur.logs" :key="lg.id"
                            :timestamp="(lg.created_at || '').slice(0, 16)"
                            :type="{ apply: 'primary', agree: 'success', reject: 'danger', escalate: 'warning', resolve: 'success' }[lg.action]">
            <b>{{ { apply: '提交申请', agree: '卖家同意', reject: '卖家拒绝', escalate: '申请平台介入', resolve: '平台裁决' }[lg.action] || lg.action }}</b>
            <span class="dim"> · {{ { buyer: '买家', seller: '卖家', admin: '平台' }[lg.actor_role] || lg.actor_role }}</span>
            <div v-if="lg.note" class="dim">{{ lg.note }}</div>
          </el-timeline-item>
        </el-timeline>

        <div class="acts">
          <el-button link type="primary" @click="$router.push(`/admin/audit?id=${cur.product_id}`)">
            调取该商品的上架评估快照 →
          </el-button>
        </div>
      </template>
    </el-drawer>

    <!-- 裁决 -->
    <el-dialog v-model="resolveDialog" :title="`平台裁定 · ${target?.ticket_no || ''}`" width="520px">
      <el-alert type="info" :closable="false" class="mb"
                title="裁定依据：上架时的 AI 评估快照 + 买家举证 + 卖家回复。裁定结果不可撤销。" />
      <el-form label-width="92px">
        <el-form-item label="裁定结果" required>
          <el-radio-group v-model="form.outcome">
            <el-radio value="refund_buyer">支持买家全额退款</el-radio>
            <el-radio value="partial">部分退款</el-radio>
            <el-radio value="support_seller">支持卖家</el-radio>
            <el-radio value="closed">证据不足关闭</el-radio>
          </el-radio-group>
        </el-form-item>
        <el-form-item label="退款金额">
          <el-input-number v-model="form.refund_amount" :min="0" :precision="2" :step="10" />
          <span class="dim" style="margin-left:8px">元（支持买家时建议等于订单金额）</span>
        </el-form-item>
        <el-form-item label="裁定说明" required>
          <el-input v-model="form.note" type="textarea" :rows="3" maxlength="300" show-word-limit
                    placeholder="写明依据，例如：上架评估霉变率 0%，买家举证明显霉变，支持退款" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="resolveDialog = false">取消</el-button>
        <el-button type="primary" :loading="resolving" @click="submitResolve">确认裁定</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { onMounted, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import { afterSaleDetail, afterSaleStats, listAfterSales, resolveAfterSale } from '../../api'

const route = useRoute()
const items = ref([])
const total = ref(0)
const status = ref(undefined)
const loading = ref(false)
const loadError = ref('')
const stats = ref({})
const drawer = ref(false)
const cur = ref(null)

const resolveDialog = ref(false)
const target = ref(null)
const resolving = ref(false)
const form = ref({ outcome: 'refund_buyer', refund_amount: 0, note: '' })

const STATES = [
  { v: 1, label: '待卖家响应' },
  { v: 2, label: '卖家已同意' },
  { v: 3, label: '卖家已拒绝' },
  { v: 4, label: '平台介入中' },
  { v: 5, label: '已解决' },
  { v: 6, label: '已关闭' },
]

function pick(v) {
  status.value = v
  load()
}

async function load() {
  loading.value = true
  loadError.value = ''
  try {
    const [data, st] = await Promise.all([
      listAfterSales({ status: status.value, size: 50 }),
      afterSaleStats(),
    ])
    items.value = data.items || []
    total.value = data.total || 0
    stats.value = st || {}
  } catch (e) {
    loadError.value = e?.message || String(e)
  } finally {
    loading.value = false
  }
}

async function openDetail(row) {
  try {
    cur.value = await afterSaleDetail(row.id)
    drawer.value = true
  } catch (e) {
    ElMessage.error(`加载工单详情失败：${e?.message || e}`)
  }
}

function openResolve(row) {
  target.value = row
  form.value = {
    outcome: 'refund_buyer',
    refund_amount: Number(row.refund_amount) || 0,
    note: '',
  }
  resolveDialog.value = true
}

async function submitResolve() {
  if (form.value.note.trim().length < 5) {
    return ElMessage.warning('请填写裁定说明（至少 5 字），便于事后复盘')
  }
  resolving.value = true
  try {
    await resolveAfterSale(target.value.id, form.value)
    ElMessage.success('已裁定')
    resolveDialog.value = false
    load()
  } finally {
    resolving.value = false
  }
}

onMounted(load)

// 深链：/admin/after-sales?ticket=12 直接打开详情（watch immediate 比 onMounted 更早且能响应路由变化）
watch(
  () => route.query.ticket,
  (v) => {
    const tid = Number(v || 0)
    if (tid) openDetail({ id: tid })
  },
  { immediate: true },
)
</script>

<style scoped>
.lr { display: grid; grid-template-columns: 220px minmax(0, 1fr); gap: 14px; align-items: start; }
.tree { padding: 14px; position: sticky; top: 12px; }
.t-head { font-weight: 700; margin-bottom: 8px; font-size: 13px; }
.t-node { display: flex; justify-content: space-between; align-items: center; font-size: 13px;
  padding: 6px 10px; border-radius: 6px; cursor: pointer; }
.t-node:hover { background: var(--brand-soft); }
.t-node.on { background: var(--brand); color: #fff; font-weight: 600; }
.t-node.on .cnt { color: #fff; }
.cnt { font-size: 11px; color: var(--ink-4); }
.todo { font-size: 12.5px; }
.todo-row { display: flex; justify-content: space-between; padding: 3px 2px; color: var(--ink-2); }
.tip { font-size: 11px; color: var(--ink-4); line-height: 1.6; margin-top: 10px; }
.table-card { padding: 14px 16px; }
.bar { display: flex; align-items: center; gap: 10px; margin-bottom: 12px; }
.flex1 { flex: 1; }
.dim { font-size: 12.5px; color: var(--ink-3); }
.mb { margin-bottom: 12px; }
.t-no { font-size: 12.5px; font-weight: 600; }
.t-title { font-size: 13px; font-weight: 600; line-height: 1.4; }
.tag-type { font-size: 11.5px; color: var(--ink-3); background: #f3ece7; border-radius: 4px; padding: 1px 6px; }
.amount { color: var(--brand); font-weight: 700; }
:deep(.clickable) { cursor: pointer; }
.st { display: inline-block; font-size: 12px; line-height: 18px; padding: 1px 8px;
  border-radius: 4px; border: 1px solid transparent; white-space: nowrap; font-weight: 600; }
.st-1 { color: #b07205; background: #fdf3dd; border-color: #efd9a7; }
.st-2, .st-5 { color: #1d8a4e; background: #e5f6ec; border-color: #bce5cc; }
.st-3 { color: var(--brand); background: var(--brand-soft); border-color: var(--brand-line); }
.st-4 { color: #1f5fa8; background: #e8f1fb; border-color: #c4dcf4; }
.st-6 { color: #8a7462; background: #f1ece7; border-color: #ddd3c9; }
.d-head { display: flex; gap: 10px; align-items: center; margin-bottom: 12px; }
.sec-t { font-weight: 700; font-size: 13px; margin: 14px 0 10px; }
.ev-imgs { display: flex; gap: 8px; flex-wrap: wrap; }
.ev-img { width: 88px; height: 88px; border-radius: 8px; border: 1px solid var(--line); }
.acts { margin-top: 12px; }
</style>
