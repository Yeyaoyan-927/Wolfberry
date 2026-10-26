<template>
  <div class="page">
    <div class="head">
      <h2>我的订单</h2>
      <el-radio-group v-model="status" @change="load">
        <el-radio-button :value="undefined">全部</el-radio-button>
        <el-radio-button v-for="(label, st) in STATUS" :key="st" :value="Number(st)">{{ label }}</el-radio-button>
      </el-radio-group>
    </div>

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
          </template>
        </div>
      </div>
      <el-empty v-if="!loading && !items.length" description="暂无订单" />
    </div>

    <!-- 发货对话框 -->
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
import { onMounted, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { cancelOrder, confirmOrder, listOrders, receiveOrder, registerPay, shipOrder } from '../../api'
import { useAuthStore } from '../../stores/auth'

const STATUS = { 1: '待确认', 2: '待发货', 3: '已发货', 4: '已完成', 5: '已取消' }
const auth = useAuthStore()
const items = ref([])
const loading = ref(false)
const status = ref(undefined)
const shipDialog = ref(false)
const shipForm = ref({ id: null, company: '', no: '' })

const isMyBuy = (o) => auth.role === 'buyer' && o.buyer_id === auth.user?.id
const isMySale = (o) => ['seller', 'admin'].includes(auth.role) && o.seller_id === auth.user?.id

const tagType = (st) => ({ 1: 'warning', 2: 'primary', 3: 'primary', 4: 'success', 5: 'info' }[st])

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

onMounted(load)
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
.o-ops { display: flex; gap: 8px; flex: none; }
</style>
