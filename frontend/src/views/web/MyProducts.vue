<template>
  <div class="page">
    <div class="head">
      <h2>我的商品</h2>
      <el-button type="primary" @click="$router.push('/publish')">
        <el-icon style="margin-right:4px"><Plus /></el-icon>发布新货源
      </el-button>
    </div>

    <el-alert v-if="loadError" type="error" :closable="false" :title="`加载失败：${loadError}`" style="margin-bottom:12px" />
    <div class="card list" v-loading="loading">
      <div v-for="p in items" :key="p.id" class="row">
        <div class="p-img" :style="p.cover_url ? { backgroundImage: `url(${p.cover_url})` } : {}"></div>
        <div class="p-main">
          <div class="p-title" @click="$router.push(`/products/${p.id}`)">{{ p.title }}</div>
          <div class="meta dim num">
            {{ p.product_no }} · {{ p.variety }} / {{ p.origin }} · {{ p.spec_per_50g }}粒/50g
            · ¥{{ p.unit_price }}/kg · 库存 {{ p.stock }}kg
          </div>
          <div class="tags">
            <span class="st" :class="`s-${p.status}`">{{ STATUS[p.status] }}</span>
            <GradeTag :grade="p.grade_claim" />
            <span class="dim">自述 → 认定</span>
            <GradeTag :grade="p.grade_platform || '—'" />
            <span v-if="p.defect_ratio !== null" class="dim num">AI 缺陷率 {{ (p.defect_ratio * 100).toFixed(2) }}%</span>
            <span v-else class="dim">AI 评估中</span>
          </div>
        </div>
        <div class="ops">
          <el-button v-if="p.status === 3" size="small" plain @click="toggle(p, false)">下架</el-button>
          <el-button v-if="p.status === 5" size="small" type="primary" plain @click="toggle(p, true)">重新提交审核</el-button>
          <el-button v-if="p.status === 4" size="small" plain @click="showReason(p)">查看驳回原因</el-button>
          <el-button v-if="[1, 3, 5].includes(p.status)" size="small" link @click="$router.push(`/products/${p.id}`)">查看</el-button>
        </div>
      </div>
      <el-empty v-if="!loading && !items.length" description="还没有发布商品的记录">
        <el-button type="primary" @click="$router.push('/publish')">去发布</el-button>
      </el-empty>
      <div class="pager" v-if="total > size">
        <el-pagination background layout="prev, pager, next" :total="total" :page-size="size"
                       :current-page="page" @current-change="(p) => { page = p; load() }" />
      </div>
    </div>
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { http, myProducts } from '../../api'
import GradeTag from '../../components/GradeTag.vue'

const STATUS = { 1: '待审核', 3: '在售', 4: '已驳回', 5: '已下架' }
const items = ref([])
const loadError = ref('')
const total = ref(0)
const loading = ref(false)
const page = ref(1)
const size = 10

async function load() {
  loading.value = true
  try {
    const data = await myProducts({ page: page.value, size })
    items.value = data.items
    total.value = data.total
  } catch (e) {
    loadError.value = e?.message || String(e)
  } finally {
    loading.value = false
  }
}

async function toggle(p, onShelf) {
  await ElMessageBox.confirm(
    onShelf ? `重新提交「${p.title.slice(0, 16)}…」审核？` : `下架商品「${p.title.slice(0, 16)}…」？下架后买家不可见。`,
    onShelf ? '重新提交' : '下架确认',
  )
  await http.patch(`/products/${p.id}/shelf`, null, { params: { on_shelf: onShelf } })
  ElMessage.success(onShelf ? '已提交审核' : '已下架')
  load()
}

async function showReason(p) {
  const d = await http.get(`/products/${p.id}`)
  ElMessageBox.alert(d.reject_reason || '未找到驳回原因，请联系平台客服', '驳回原因')
}

onMounted(load)
</script>

<style scoped>
.head { display: flex; justify-content: space-between; align-items: center; margin-bottom: 14px; }
.head h2 { margin: 0; font-size: 18px; }
.list { padding: 6px 20px 14px; }
.row { display: flex; gap: 14px; align-items: center; padding: 14px 0; border-bottom: 1px solid var(--line); }
.row:last-child { border-bottom: none; }
.p-img { width: 72px; height: 72px; border-radius: 8px; background: #f3ebe4 center/cover no-repeat; flex: none; }
.p-main { flex: 1; min-width: 0; }
.p-title { font-size: 14px; font-weight: 600; cursor: pointer; }
.p-title:hover { color: var(--brand); }
.meta { font-size: 12px; margin: 4px 0 6px; }
.tags { display: flex; gap: 8px; align-items: center; flex-wrap: wrap; font-size: 12px; }
.dim { font-size: 12px; color: var(--ink-3); }
.st { display: inline-block; font-size: 12px; line-height: 18px; padding: 1px 8px; border-radius: 4px;
  border: 1px solid transparent; font-weight: 600; }
.s-1 { color: #b07205; background: #fdf3dd; border-color: #efd9a7; }
.s-3 { color: #1d8a4e; background: #e5f6ec; border-color: #bce5cc; }
.s-4 { color: var(--brand); background: var(--brand-soft); border-color: var(--brand-line); }
.s-5 { color: #8a7462; background: #f1ece7; border-color: #ddd3c9; }
.ops { display: flex; gap: 8px; flex: none; }
.pager { display: flex; justify-content: center; margin-top: 12px; }
</style>
