<template>
  <div>
    <div class="bar">
      <el-radio-group v-model="action" @change="load">
        <el-radio-button :value="undefined">全部动作</el-radio-button>
        <el-radio-button value="approve">通过</el-radio-button>
        <el-radio-button value="grade">改级上架</el-radio-button>
        <el-radio-button value="reject">驳回</el-radio-button>
      </el-radio-group>
      <span class="dim num">共 {{ total }} 条（不可删除，只增）</span>
    </div>

    <div class="card table-card">
      <el-table :data="items" v-loading="loading" :header-cell-style="{ background: '#faf6f3' }">
        <el-table-column label="时间" width="140">
          <template #default="{ row }"><span class="num dim">{{ (row.acted_at || '').replace('T', ' ').slice(0, 16) }}</span></template>
        </el-table-column>
        <el-table-column label="商品" min-width="200">
          <template #default="{ row }">
            <router-link :to="`/admin/audit?id=${row.product_id}`" class="p-link">{{ row.product_title }}</router-link>
          </template>
        </el-table-column>
        <el-table-column prop="auditor" label="审核员" width="100" />
        <el-table-column label="动作" width="96" align="center">
          <template #default="{ row }">
            <span class="st" :class="`act-${row.action}`">{{ { approve: '通过', grade: '改级', reject: '驳回' }[row.action] }}</span>
          </template>
        </el-table-column>
        <el-table-column label="自述 → AI → 认定" width="180">
          <template #default="{ row }">
            <span class="num">{{ row.grade_claim || '—' }} → {{ row.ai_grade || '灰' }} → </span>
            <b class="num">{{ row.grade_platform_after || '—' }}</b>
          </template>
        </el-table-column>
        <el-table-column label="差异" width="70" align="center">
          <template #default="{ row }">
            <DiffFlag v-if="row.diff_flag" :flag="row.diff_flag" />
          </template>
        </el-table-column>
        <el-table-column prop="reason" label="理由" min-width="220" show-overflow-tooltip />
      </el-table>
      <div class="pager">
        <el-pagination background layout="prev, pager, next" :total="total" :page-size="size"
                       :current-page="page" @current-change="(p) => { page = p; load() }" />
      </div>
    </div>
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { adminAuditLogs } from '../../api'
import DiffFlag from '../../components/DiffFlag.vue'

const items = ref([])
const total = ref(0)
const loading = ref(false)
const action = ref(undefined)
const page = ref(1)
const size = 20

async function load() {
  loading.value = true
  try {
    const data = await adminAuditLogs({ action: action.value, page: page.value, size })
    items.value = data.items
    total.value = data.total
  } finally {
    loading.value = false
  }
}

onMounted(load)
</script>

<style scoped>
.bar { display: flex; align-items: center; gap: 14px; margin-bottom: 14px; }
.dim { font-size: 12px; color: var(--ink-3); }
.table-card { padding: 14px 16px; }
.p-link { color: var(--brand); font-weight: 600; font-size: 13px; }
.pager { display: flex; justify-content: center; margin-top: 12px; }
.st { display: inline-block; font-size: 12px; line-height: 18px; padding: 1px 8px; border-radius: 4px;
  border: 1px solid transparent; white-space: nowrap; font-weight: 600; }
.act-approve { color: #1d8a4e; background: #e5f6ec; border-color: #bce5cc; }
.act-grade { color: #1f5fa8; background: #e8f1fb; border-color: #c4dcf4; }
.act-reject { color: var(--brand); background: var(--brand-soft); border-color: var(--brand-line); }
</style>
