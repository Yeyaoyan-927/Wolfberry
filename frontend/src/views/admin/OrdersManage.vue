<template>
  <div>
    <div class="bar">
      <el-radio-group v-model="status" @change="load">
        <el-radio-button :value="undefined">全部</el-radio-button>
        <el-radio-button v-for="(label, st) in STATUS" :key="st" :value="Number(st)">{{ label }}</el-radio-button>
      </el-radio-group>
      <span class="dim num">共 {{ total }} 笔</span>
    </div>

    <div class="card table-card">
      <el-table :data="items" v-loading="loading" :header-cell-style="{ background: '#faf6f3' }">
        <el-table-column label="订单号" width="170">
          <template #default="{ row }"><span class="num dim">{{ row.order_no }}</span></template>
        </el-table-column>
        <el-table-column label="商品" min-width="220">
          <template #default="{ row }"><div class="p-name">{{ row.product_title }}</div></template>
        </el-table-column>
        <el-table-column label="买家 / 卖家" width="120">
          <template #default="{ row }"><span class="num dim">#{{ row.buyer_id }} / #{{ row.seller_id }}</span></template>
        </el-table-column>
        <el-table-column label="数量×单价" width="130" align="right">
          <template #default="{ row }"><span class="num">{{ row.quantity }}kg × ¥{{ row.unit_price }}</span></template>
        </el-table-column>
        <el-table-column label="金额" width="100" align="right">
          <template #default="{ row }"><b class="num price">¥{{ row.total_amount }}</b></template>
        </el-table-column>
        <el-table-column label="状态" width="96" align="center">
          <template #default="{ row }">
            <span class="st" :class="`st-${row.status}`">{{ row.status_label }}</span>
          </template>
        </el-table-column>
        <el-table-column label="支付" width="86" align="center">
          <template #default="{ row }">
            <span class="st" :class="row.pay_status === 1 ? 'st-4' : 'st-0'">
              {{ row.pay_status === 1 ? '已登记' : '未支付' }}
            </span>
          </template>
        </el-table-column>
        <el-table-column label="时间" width="130">
          <template #default="{ row }"><span class="num dim">{{ (row.ordered_at || '').replace('T', ' ').slice(0, 16) }}</span></template>
        </el-table-column>
        <el-table-column label="操作" width="150" fixed="right">
          <template #default="{ row }">
            <el-button v-if="row.status === 1" size="small" type="primary" link @click="doConfirm(row)">代为确认</el-button>
            <el-button v-if="row.status === 2" size="small" type="primary" link @click="openShip(row)">代为发货</el-button>
            <el-button v-if="[1, 2].includes(row.status)" size="small" type="danger" link @click="doCancel(row)">取消</el-button>
            <span v-if="![1, 2].includes(row.status)" class="dim">—</span>
          </template>
        </el-table-column>
      </el-table>
      <div class="pager">
        <el-pagination background layout="prev, pager, next" :total="total" :page-size="size"
                       :current-page="page" @current-change="(p) => { page = p; load() }" />
      </div>
    </div>

    <el-dialog v-model="shipDialog" title="代为发货（登记物流）" width="420px">
      <el-form label-width="80px">
        <el-form-item label="物流公司"><el-input v-model="shipForm.company" placeholder="如：顺丰速运" /></el-form-item>
        <el-form-item label="运单号"><el-input v-model="shipForm.no" /></el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="shipDialog = false">取消</el-button>
        <el-button type="primary" @click="submitShip">确认发货</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { cancelOrder, confirmOrder, listOrders, shipOrder } from '../../api'

const STATUS = { 1: '待确认', 2: '待发货', 3: '已发货', 4: '已完成', 5: '已取消' }
const items = ref([])
const total = ref(0)
const loading = ref(false)
const status = ref(undefined)
const page = ref(1)
const size = 15
const shipDialog = ref(false)
const shipForm = ref({ id: null, company: '', no: '' })

async function load() {
  loading.value = true
  try {
    const data = await listOrders({ status: status.value, page: page.value, size })
    items.value = data.items
    total.value = data.total
  } finally {
    loading.value = false
  }
}

async function doConfirm(row) {
  await ElMessageBox.confirm(`代卖家确认订单 ${row.order_no}？`, '代为确认')
  await confirmOrder(row.id)
  ElMessage.success('已确认，等待卖家发货')
  load()
}

function openShip(row) {
  shipForm.value = { id: row.id, company: '', no: '' }
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

async function doCancel(row) {
  const { value } = await ElMessageBox.prompt('取消原因（将归还冻结库存）', '取消订单', { inputValue: '运营取消' })
  await cancelOrder(row.id, value || '运营取消')
  ElMessage.success('已取消')
  load()
}

onMounted(load)
</script>

<style scoped>
.bar { display: flex; align-items: center; gap: 14px; margin-bottom: 14px; }
.dim { font-size: 12px; color: var(--ink-3); }
.table-card { padding: 14px 16px; }
.p-name { font-size: 13px; font-weight: 600; line-height: 1.4; }
.price { color: var(--brand); }
.pager { display: flex; justify-content: center; margin-top: 12px; }
.st { display: inline-block; font-size: 12px; line-height: 18px; padding: 1px 8px; border-radius: 4px;
  border: 1px solid transparent; white-space: nowrap; font-weight: 600; }
.st-1 { color: #b07205; background: #fdf3dd; border-color: #efd9a7; }
.st-2, .st-3 { color: #1f5fa8; background: #e8f1fb; border-color: #c4dcf4; }
.st-4 { color: #1d8a4e; background: #e5f6ec; border-color: #bce5cc; }
.st-5, .st-0 { color: #8a7462; background: #f1ece7; border-color: #ddd3c9; }
</style>
