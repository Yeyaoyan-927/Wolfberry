<template>
  <div>
    <div class="bar">
      <el-radio-group v-model="role" @change="load">
        <el-radio-button :value="undefined">全部</el-radio-button>
        <el-radio-button value="buyer">买家</el-radio-button>
        <el-radio-button value="seller">卖家</el-radio-button>
        <el-radio-button value="admin">管理员</el-radio-button>
      </el-radio-group>
      <el-input v-model="keyword" placeholder="用户名 / 显示名" clearable style="width: 200px" @keyup.enter="load" />
      <el-button type="primary" plain @click="load">查询</el-button>
      <span class="dim num">共 {{ total }} 人</span>
    </div>

    <div class="card table-card">
      <el-table :data="items" v-loading="loading" :header-cell-style="{ background: '#faf6f3' }">
        <el-table-column prop="id" label="ID" width="60" align="center" />
        <el-table-column label="用户" min-width="180">
          <template #default="{ row }">
            <div class="u-name">{{ row.display_name || row.username }}</div>
            <div class="dim num">@{{ row.username }}</div>
          </template>
        </el-table-column>
        <el-table-column label="角色" width="90" align="center">
          <template #default="{ row }">
            <span class="st" :class="`role-${row.role}`">{{ { admin: '管理员', seller: '卖家', buyer: '买家' }[row.role] }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="org_name" label="组织 / 店铺" min-width="120">
          <template #default="{ row }">{{ row.org_name || '—' }}</template>
        </el-table-column>
        <el-table-column label="经营统计（卖家）" min-width="180">
          <template #default="{ row }">
            <span v-if="row.seller_stats" class="num dim">
              发布 {{ row.seller_stats.published }} · 驳回 {{ row.seller_stats.rejected }} ·
              <b :class="{ bad: row.seller_stats.red_30d >= 3 }">30 天红标 {{ row.seller_stats.red_30d }}</b>
            </span>
            <span v-else class="dim">—</span>
          </template>
        </el-table-column>
        <el-table-column label="状态" width="86" align="center">
          <template #default="{ row }">
            <span class="st" :class="row.is_active ? 'st-on' : 'st-off'">{{ row.is_active ? '启用' : '已停用' }}</span>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="100" fixed="right">
          <template #default="{ row }">
            <el-button v-if="row.is_active" size="small" type="danger" link :disabled="row.role === 'admin'"
                       @click="toggle(row, false)">停用</el-button>
            <el-button v-else size="small" type="success" link @click="toggle(row, true)">启用</el-button>
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
import { onMounted, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { adminUsers, setUserStatus } from '../../api'

const items = ref([])
const total = ref(0)
const loading = ref(false)
const role = ref(undefined)
const keyword = ref('')
const page = ref(1)
const size = 20

async function load() {
  loading.value = true
  try {
    const data = await adminUsers({ role: role.value, keyword: keyword.value || undefined, page: page.value, size })
    items.value = data.items
    total.value = data.total
  } finally {
    loading.value = false
  }
}

async function toggle(row, active) {
  await ElMessageBox.confirm(
    `${active ? '启用' : '停用'}用户「${row.display_name || row.username}」？${active ? '' : '停用后无法登录。'}`,
    '确认操作',
  )
  await setUserStatus(row.id, active)
  ElMessage.success(active ? '已启用' : '已停用')
  load()
}

onMounted(load)
</script>

<style scoped>
.bar { display: flex; align-items: center; gap: 14px; margin-bottom: 14px; }
.dim { font-size: 12px; color: var(--ink-3); }
.u-name { font-size: 13px; font-weight: 600; }
.bad { color: var(--brand); }
.table-card { padding: 14px 16px; }
.pager { display: flex; justify-content: center; margin-top: 12px; }
.st { display: inline-block; font-size: 12px; line-height: 18px; padding: 1px 8px; border-radius: 4px;
  border: 1px solid transparent; white-space: nowrap; font-weight: 600; }
.role-admin { color: var(--brand); background: var(--brand-soft); border-color: var(--brand-line); }
.role-seller { color: #b07205; background: #fdf3dd; border-color: #efd9a7; }
.role-buyer { color: #1d8a4e; background: #e5f6ec; border-color: #bce5cc; }
.st-on { color: #1d8a4e; background: #e5f6ec; border-color: #bce5cc; }
.st-off { color: #8a7462; background: #f1ece7; border-color: #ddd3c9; }
</style>
