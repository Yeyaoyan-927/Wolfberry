<template>
  <div class="lr">
    <div class="tree card">
      <div class="t-head">认证状态</div>
      <div class="t-node" :class="{ on: status === undefined }" @click="pick(undefined)">
        全部<span class="cnt num">{{ totalAll }}</span>
      </div>
      <div v-for="s in STATES" :key="s.v" class="t-node" :class="{ on: status === s.v }" @click="pick(s.v)">
        {{ s.label }}<span class="cnt num">{{ stats.by_status?.[s.v] || 0 }}</span>
      </div>
      <el-divider style="margin:10px 0" />
      <div class="todo">
        <div class="todo-row"><span>待审核</span><b class="num warn">{{ stats.pending || 0 }}</b></div>
        <div class="todo-row"><span>已认证</span><b class="num ok">{{ stats.verified || 0 }}</b></div>
        <div class="todo-row"><span>已驳回</span><b class="num">{{ stats.rejected || 0 }}</b></div>
      </div>
      <div class="tip">通过后卖家才能发布商品。驳回必须写原因，卖家据此补充材料重新提交。</div>
    </div>

    <div class="card table-card">
      <div class="bar">
        <span class="dim num">共 {{ total }} 条申请</span>
        <span class="flex1"></span>
        <el-button size="small" plain @click="load">刷新</el-button>
      </div>
      <el-alert v-if="loadError" type="error" :closable="false" :title="`加载失败：${loadError}`" class="mb" />

      <el-table :data="items" v-loading="loading" :header-cell-style="{ background: '#faf6f3' }"
                row-class-name="clickable" @row-click="open">
        <el-table-column label="企业/合作社" min-width="180">
          <template #default="{ row }">
            <div class="c-name">{{ row.company_name }}</div>
            <div class="dim num">{{ row.username }} · {{ row.credit_code || '无信用代码' }}</div>
          </template>
        </el-table-column>
        <el-table-column label="产区" width="90" align="center">
          <template #default="{ row }"><span class="dim">{{ row.origin || '—' }}</span></template>
        </el-table-column>
        <el-table-column label="经营" width="110" align="center">
          <template #default="{ row }">
            <span class="num">{{ row.products_on_shelf }} / {{ row.products_total }}</span>
            <div class="dim" style="font-size:11px">在售 / 全部</div>
          </template>
        </el-table-column>
        <el-table-column label="提交时间" width="120" align="center">
          <template #default="{ row }"><span class="dim num">{{ (row.created_at || '').slice(5, 16) }}</span></template>
        </el-table-column>
        <el-table-column label="状态" width="96" align="center">
          <template #default="{ row }">
            <span class="st" :class="`sq-${row.status}`">{{ row.status_label }}</span>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="100" align="center">
          <template #default="{ row }">
            <el-button v-if="row.status === 1" size="small" type="primary" link @click.stop="open(row)">审核</el-button>
            <span v-else class="dim">—</span>
          </template>
        </el-table-column>
      </el-table>
      <el-empty v-if="!loading && !items.length" description="暂无资质申请" />
    </div>

    <!-- 审核抽屉 -->
    <el-drawer v-model="drawer" :title="`资质审核 · ${cur?.company_name || ''}`" size="46%">
      <template v-if="cur">
        <div class="d-head">
          <span class="st" :class="`sq-${cur.status}`">{{ cur.status_label }}</span>
          <span class="dim num">{{ cur.username }}</span>
        </div>
        <el-descriptions :column="2" border size="small">
          <el-descriptions-item label="企业名称" :span="2">{{ cur.company_name }}</el-descriptions-item>
          <el-descriptions-item label="信用代码">{{ cur.credit_code || '—' }}</el-descriptions-item>
          <el-descriptions-item label="法定代表人">{{ cur.legal_person || '—' }}</el-descriptions-item>
          <el-descriptions-item label="主要产区">{{ cur.origin || '—' }}</el-descriptions-item>
          <el-descriptions-item label="联系电话">{{ cur.contact_phone || '—' }}</el-descriptions-item>
          <el-descriptions-item label="在售/全部" :span="2">
            {{ cur.products_on_shelf }} / {{ cur.products_total }} 件
          </el-descriptions-item>
          <el-descriptions-item label="资质说明" :span="2">{{ cur.intro || '—' }}</el-descriptions-item>
          <el-descriptions-item v-if="cur.reject_reason" label="上次驳回原因" :span="2">
            {{ cur.reject_reason }}
          </el-descriptions-item>
        </el-descriptions>

        <div class="sec-t">证件材料</div>
        <div v-if="cur.licenses?.length" class="lic">
          <el-image v-for="(u, i) in cur.licenses" :key="i" :src="u" :preview-src-list="cur.licenses"
                    fit="cover" class="lic-img" />
        </div>
        <el-empty v-else :image-size="60" description="卖家未上传证件" />

        <div v-if="cur.status === 1" class="acts">
          <el-input v-model="reason" type="textarea" :rows="2" maxlength="300" show-word-limit
                    placeholder="驳回时必须填写原因（至少 4 字），卖家据此补充材料" />
          <div class="btns">
            <el-button type="primary" :loading="acting" @click="audit(true)">通过认证</el-button>
            <el-button type="danger" plain :loading="acting" @click="audit(false)">驳回</el-button>
          </div>
        </div>
      </template>
    </el-drawer>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { adminQualifications, auditQualification, qualificationStats } from '../../api'

const items = ref([])
const total = ref(0)
const status = ref(undefined)
const loading = ref(false)
const loadError = ref('')
const stats = ref({})
const drawer = ref(false)
const cur = ref(null)
const reason = ref('')
const acting = ref(false)

const STATES = [
  { v: 1, label: '待审核' },
  { v: 2, label: '已认证' },
  { v: 3, label: '已驳回' },
]
const totalAll = computed(() => Object.values(stats.value.by_status || {}).reduce((a, b) => a + b, 0))

function pick(v) {
  status.value = v
  load()
}

async function load() {
  loading.value = true
  loadError.value = ''
  try {
    const [data, st] = await Promise.all([
      adminQualifications({ status: status.value, size: 50 }),
      qualificationStats(),
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

async function open(row) {
  cur.value = row
  reason.value = ''
  drawer.value = true
}

async function audit(approve) {
  if (!approve && reason.value.trim().length < 4) {
    return ElMessage.warning('驳回请填写原因（至少 4 字）')
  }
  acting.value = true
  try {
    cur.value = await auditQualification(cur.value.id, { approve, reason: reason.value })
    ElMessage.success(approve ? '已通过认证，卖家可发布商品' : '已驳回，结果将展示给卖家')
    load()
  } finally {
    acting.value = false
  }
}

onMounted(load)
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
.c-name { font-size: 13px; font-weight: 600; }
:deep(.clickable) { cursor: pointer; }
.st { display: inline-block; font-size: 12px; line-height: 18px; padding: 1px 8px;
  border-radius: 4px; border: 1px solid transparent; white-space: nowrap; font-weight: 600; }
.sq-0 { color: #8a7462; background: #f1ece7; border-color: #ddd3c9; }
.sq-1 { color: #b07205; background: #fdf3dd; border-color: #efd9a7; }
.sq-2 { color: #1d8a4e; background: #e5f6ec; border-color: #bce5cc; }
.sq-3 { color: var(--brand); background: var(--brand-soft); border-color: var(--brand-line); }
.d-head { display: flex; gap: 10px; align-items: center; margin-bottom: 12px; }
.sec-t { font-weight: 700; font-size: 13px; margin: 14px 0 10px; }
.lic { display: flex; gap: 8px; flex-wrap: wrap; }
.lic-img { width: 96px; height: 96px; border-radius: 8px; border: 1px solid var(--line); }
.acts { margin-top: 16px; display: flex; flex-direction: column; gap: 10px; }
.btns { display: flex; gap: 8px; }
</style>
