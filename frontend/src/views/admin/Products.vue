<template>
  <div class="lr">
    <!-- 左树 -->
    <div class="tree card">
      <div class="t-head">筛选</div>
      <div class="t-group" v-for="g in tree" :key="g.name">
        <div class="t-lv1">{{ g.name }}</div>
        <div v-for="n in g.children" :key="n.key" class="t-node" :class="{ on: isActive(g.key, n.key) }"
             @click="pick(g.key, n.key)">
          {{ n.label }}
          <span class="cnt num">{{ n.count }}</span>
        </div>
      </div>
    </div>

    <!-- 右表 -->
    <div class="card table-card">
      <div class="bar">
        <el-input v-model="keyword" placeholder="搜索标题" clearable style="width: 220px" @keyup.enter="load" />
        <el-button type="primary" plain @click="load">查询</el-button>
        <span class="dim num">共 {{ total }} 条</span>
      </div>
      <el-table :data="items" v-loading="loading" size="default" :header-cell-style="{ background: '#faf6f3' }">
        <el-table-column label="商品" min-width="260">
          <template #default="{ row }">
            <div class="p-cell">
              <div class="p-img" :style="row.cover_url ? `background-image:url('${row.cover_url}')` : ''"></div>
              <div>
                <div class="p-name">{{ row.title }}</div>
                <div class="dim num">{{ row.product_no }} · {{ row.variety }} / {{ row.origin }}</div>
              </div>
            </div>
          </template>
        </el-table-column>
        <el-table-column label="自述 → 认定" width="130" align="center">
          <template #default="{ row }">
            <div class="pair"><GradeTag :grade="row.grade_claim" /><span class="arr">→</span><GradeTag :grade="row.grade_platform || '—'" /></div>
          </template>
        </el-table-column>
        <el-table-column label="AI" width="70" align="center">
          <template #default="{ row }"><GradeTag :grade="row.ai_grade || '灰'" /></template>
        </el-table-column>
        <el-table-column label="差异" width="96" align="center">
          <template #default="{ row }"><DiffFlag :flag="flagOf(row)" :gap="row.grade_diff" /></template>
        </el-table-column>
        <el-table-column label="报价" width="86" align="right">
          <template #default="{ row }"><span class="num price">¥{{ row.unit_price }}</span></template>
        </el-table-column>
        <el-table-column label="缺陷率" width="84" align="right">
          <template #default="{ row }"><span class="num">{{ pct(row.defect_ratio) }}</span></template>
        </el-table-column>
        <el-table-column label="状态" width="80" align="center">
          <template #default="{ row }">
            <el-tag size="small" :type="{ 1: 'warning', 3: 'success', 4: 'danger', 5: 'info' }[row.status]">
              {{ { 1: '待审核', 3: '在售', 4: '已驳回', 5: '已下架' }[row.status] }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="96" fixed="right">
          <template #default="{ row }">
            <el-button v-if="row.status === 1" size="small" type="primary" link
                       @click="$router.push(`/admin/audit/${row.id}`)">审核</el-button>
            <el-button v-else size="small" link @click="$router.push(`/admin/audit/${row.id}`)">详情</el-button>
          </template>
        </el-table-column>
      </el-table>
      <div class="pager">
        <el-pagination background layout="prev, pager, next" :total="total" :page-size="size"
                       :current-page="page" @current-change="(p) => { page = p; load() }" />
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { listProducts } from '../../api'
import GradeTag from '../../components/GradeTag.vue'
import DiffFlag from '../../components/DiffFlag.vue'

const items = ref([])
const total = ref(0)
const loading = ref(false)
const page = ref(1)
const size = 15
const keyword = ref('')
const pick_ = ref({ group: 'status', key: 'ALL' })

const STATUS_DEFS = [
  { key: 'ALL', label: '全部' },
  { key: '1', label: '待审核' },
  { key: '3', label: '在售' },
  { key: '4', label: '已驳回' },
  { key: '5', label: '已下架' },
]
const GRADE_DEFS = ['特优', '特级', '甲级', '乙级'].map((g) => ({ key: g, label: g }))
const ORIGIN_DEFS = ['中宁', '诺木洪', '靖远'].map((o) => ({ key: o, label: o }))

const tree = computed(() => [
  { name: '状态', key: 'status', children: STATUS_DEFS },
  { name: '认定等级', key: 'grade', children: GRADE_DEFS },
  { name: '产区', key: 'origin', children: ORIGIN_DEFS },
])

function isActive(group, key) {
  return pick_.value.group === group && pick_.value.key === key
}

function pick(group, key) {
  pick_.value = { group, key }
  page.value = 1
  load()
}

const pct = (v) => (v == null ? '—' : (v * 100).toFixed(1) + '%')

function flagOf(p) {
  const conf = p.ai_confidence ?? null
  if (!p.ai_grade || (conf !== null && conf < 0.45)) return '灰'
  if ((p.grade_diff ?? 0) >= 2) return '红'
  if (p.grade_diff === 1) return '黄'
  if (p.grade_diff < 0) return '蓝'
  return '绿'
}

async function load() {
  loading.value = true
  try {
    const params = { page: page.value, size, keyword: keyword.value || undefined, only_on_shelf: false }
    const { group, key } = pick_.value
    if (group === 'status' && key !== 'ALL') params.status = Number(key)
    if (group === 'grade') params.grade = key
    if (group === 'origin') params.origin = key
    const data = await listProducts(params)
    items.value = data.items
    total.value = data.total
  } finally {
    loading.value = false
  }
}

onMounted(load)
</script>

<style scoped>
.lr { display: grid; grid-template-columns: 230px minmax(0, 1fr); gap: 14px; align-items: start; }
.tree { padding: 14px; position: sticky; top: 12px; }
.t-head { font-weight: 700; margin-bottom: 10px; }
.t-group { margin-bottom: 12px; }
.t-lv1 { font-size: 12px; color: var(--ink-3); margin: 8px 0 4px; }
.t-node { display: flex; justify-content: space-between; align-items: center; font-size: 13px;
  padding: 6px 10px; border-radius: 6px; cursor: pointer; }
.t-node:hover { background: var(--brand-soft); }
.t-node.on { background: var(--brand); color: #fff; font-weight: 600; }
.t-node.on .cnt { color: #fff; }
.cnt { font-size: 11px; color: var(--ink-4); }
.table-card { padding: 14px 16px; }
.bar { display: flex; gap: 10px; align-items: center; margin-bottom: 12px; }
.dim { font-size: 12px; color: var(--ink-3); }
.p-cell { display: flex; gap: 10px; align-items: center; }
.p-img { width: 46px; height: 46px; border-radius: 6px; background: #f3ebe4 center/cover no-repeat; flex: none; }
.p-name { font-size: 13px; font-weight: 600; line-height: 1.4; max-width: 240px; }
.pair { display: flex; align-items: center; gap: 4px; white-space: nowrap; }
.arr { color: var(--ink-4); font-size: 11px; }
.price { color: var(--brand); font-weight: 600; }
.pager { display: flex; justify-content: center; margin-top: 12px; }
</style>
