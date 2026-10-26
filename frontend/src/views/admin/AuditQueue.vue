<template>
  <div>
    <div class="bar">
      <el-radio-group v-model="flag" @change="load">
        <el-radio-button :value="undefined">全部</el-radio-button>
        <el-radio-button v-for="f in ['红','黄','灰','蓝','绿']" :key="f" :value="f">{{ f }}标</el-radio-button>
      </el-radio-group>
      <span class="dim">红标（自述高报 ≥2 级）优先处理；共 {{ total }} 条待审</span>
    </div>

    <div class="card list" v-loading="loading">
      <div v-for="it in items" :key="it.id" class="qrow" @click="$router.push(`/admin/audit/${it.id}`)">
        <div class="qimg" :style="it.cover ? `background-image:url('${it.cover}')` : ''"></div>
        <div class="q-main">
          <div class="q-title">{{ it.title }}</div>
          <div class="q-meta dim num">
            {{ it.product_no }} · {{ it.variety }} / {{ it.origin }}
            <template v-if="it.defect_ratio !== null"> · 缺陷率 {{ (it.defect_ratio * 100).toFixed(2) }}%</template>
            <template v-else> · 评估中</template>
          </div>
          <div class="q-grades">
            自述 <GradeTag :grade="it.grade_claim" />
            <span class="dim">AI 建议</span>
            <GradeTag :grade="it.ai_grade || '—'" />
            <DiffFlag :flag="it.diff_flag" />
          </div>
        </div>
        <el-button size="small" :type="it.diff_flag === '红' ? 'danger' : 'primary'" plain>去审核</el-button>
      </div>
      <el-empty v-if="!loading && !items.length" description="队列为空，全部审完 🎉" />
    </div>
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { auditQueue } from '../../api'
import GradeTag from '../../components/GradeTag.vue'
import DiffFlag from '../../components/DiffFlag.vue'

const items = ref([])
const total = ref(0)
const loading = ref(false)
const flag = ref(undefined)

async function load() {
  loading.value = true
  try {
    const data = await auditQueue({ flag: flag.value })
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
.dim { font-size: 12.5px; color: var(--ink-3); }
.list { padding: 4px 18px; }
.qrow { display: flex; align-items: center; gap: 14px; padding: 14px 0; border-bottom: 1px solid var(--line); cursor: pointer; }
.qrow:last-child { border-bottom: none; }
.qrow:hover { background: #fffaf8; }
.qimg { width: 64px; height: 64px; border-radius: 8px; background: #f3ebe4 center/cover no-repeat; flex: none; }
.q-main { flex: 1; min-width: 0; }
.q-title { font-weight: 600; font-size: 14px; }
.q-meta { font-size: 12px; margin: 4px 0 6px; }
.q-grades { display: flex; align-items: center; gap: 8px; font-size: 12.5px; }
</style>
