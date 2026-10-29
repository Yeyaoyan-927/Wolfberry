<template>
  <div class="page">
    <div class="filter card">
      <el-form inline>
        <el-form-item label="关键词">
          <el-input v-model="q.keyword" placeholder="标题 / 品种" clearable style="width: 180px" @keyup.enter="load" />
        </el-form-item>
        <el-form-item label="品种">
          <el-select v-model="q.variety" clearable placeholder="全部" style="width: 130px">
            <el-option v-for="v in varieties" :key="v" :label="v" :value="v" />
          </el-select>
        </el-form-item>
        <el-form-item label="产区">
          <el-select v-model="q.origin" clearable placeholder="全部" style="width: 120px">
            <el-option v-for="o in origins" :key="o" :label="o" :value="o" />
          </el-select>
        </el-form-item>
        <el-form-item label="认定等级">
          <el-select v-model="q.grade" clearable placeholder="全部" style="width: 120px">
            <el-option v-for="g in grades" :key="g" :label="g" :value="g" />
          </el-select>
        </el-form-item>
        <el-form-item label="价格">
          <el-input-number v-model="q.min_price" :min="0" :controls="false" placeholder="最低" style="width: 90px" />
          <span class="sep">—</span>
          <el-input-number v-model="q.max_price" :min="0" :controls="false" placeholder="最高" style="width: 90px" />
        </el-form-item>
        <el-form-item>
          <el-radio-group v-model="q.order_by" @change="load">
            <el-radio-button value="newest">最新</el-radio-button>
            <el-radio-button value="price_asc">价格↑</el-radio-button>
            <el-radio-button value="price_desc">价格↓</el-radio-button>
            <el-radio-button value="defect_asc">缺陷率↑</el-radio-button>
            <el-radio-button value="rating_desc">评分优先</el-radio-button>
            <el-radio-button value="rating_desc">评分优先</el-radio-button>
          </el-radio-group>
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="load">查询</el-button>
        </el-form-item>
      </el-form>
    </div>

    <el-row :gutter="16" v-loading="loading">
      <el-col v-for="p in items" :key="p.id" :span="6" :xs="12">
        <div class="pcard" @click="$router.push(`/products/${p.id}`)">
          <div class="pimg" :style="p.cover_url ? `background-image:url('${p.cover_url}')` : ''">
            <DiffFlag class="pflag" :flag="flagOf(p)" :gap="p.grade_diff" />
          </div>
          <div class="pbody">
            <div class="ptitle">{{ p.title }}</div>
            <div class="meta">
              <GradeTag :grade="p.grade_platform || p.grade_claim" />
              <span class="dim">{{ p.origin }} · {{ p.spec_per_50g }}粒/50g</span>
            </div>
            <div class="ai" v-if="p.defect_ratio !== null">
              AI：缺陷率 <b class="num">{{ (p.defect_ratio * 100).toFixed(2) }}%</b>
              <span v-if="p.grain_count"> · 粒数 {{ p.grain_count }}</span>
            </div>
            <div class="ai dim2" v-else>AI 评估中 / 未评估</div>
            <div class="rate" v-if="p.review_count">
              <el-rate :model-value="Math.round(p.rating_avg)" disabled size="small" />
              <span class="dim num">{{ p.rating_avg }}（{{ p.review_count }}）</span>
            </div>
            <div class="rate dim2" v-else><span class="dim">暂无评价</span></div>
            <div class="rate" v-if="p.review_count">
              <el-rate :model-value="Math.round(p.rating_avg)" disabled size="small" />
              <span class="dim num">{{ p.rating_avg }}（{{ p.review_count }}）</span>
            </div>
            <div class="rate dim2" v-else><span class="dim">暂无评价</span></div>
            <div class="pfoot">
              <span class="price num">¥{{ p.unit_price }}</span><span class="per">/kg</span>
              <span class="stock dim">库存 {{ p.stock }}kg</span>
            </div>
          </div>
        </div>
      </el-col>
    </el-row>
    <el-empty v-if="!loading && !items.length" description="没有符合条件的货源" />

    <div class="pager">
      <el-pagination background layout="prev, pager, next" :total="total" :page-size="q.size"
                     :current-page="q.page" @current-change="(p) => { q.page = p; load() }" />
    </div>
  </div>
</template>

<script setup>
import { onMounted, reactive, ref } from 'vue'
import { useRoute } from 'vue-router'
import { listProducts } from '../../api'
import GradeTag from '../../components/GradeTag.vue'
import DiffFlag from '../../components/DiffFlag.vue'

const grades = ['特优', '特级', '甲级', '乙级']
const varieties = ['宁杞5号', '宁杞7号', '大麻叶']
const origins = ['中宁', '诺木洪', '靖远']
const route = useRoute()
const items = ref([])
const total = ref(0)
const loading = ref(false)
const q = reactive({ page: 1, size: 12, keyword: '', variety: '', grade: '', origin: route.query.origin || '', min_price: undefined, max_price: undefined, order_by: 'newest' })

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
    const params = { ...q }
    for (const k of Object.keys(params)) if (params[k] === '' || params[k] == null) delete params[k]
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
.filter { padding: 16px 16px 0; margin-bottom: 16px; }
.filter :deep(.el-form-item) { margin-bottom: 12px; }
.sep { margin: 0 6px; color: var(--ink-4); }
.pcard { background: #fff; border: 1px solid var(--line); border-radius: 12px; overflow: hidden;
  cursor: pointer; margin-bottom: 16px; transition: box-shadow .2s, transform .2s; }
.pcard:hover { box-shadow: 0 8px 24px rgba(120,60,40,.12); transform: translateY(-2px); }
.pimg { height: 150px; background: #f3ebe4 center/cover no-repeat; position: relative; }
.pflag { position: absolute; left: 10px; top: 10px; }
.pbody { padding: 12px 14px 14px; }
.ptitle { font-size: 13.5px; font-weight: 600; line-height: 1.45; height: 39px;
  display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden; }
.meta { display: flex; gap: 8px; align-items: center; margin: 8px 0 4px; }
.dim { font-size: 12px; color: var(--ink-3); }
.dim2 { font-size: 12px; color: var(--ink-4); }
.ai { font-size: 12px; color: var(--ink-2); margin-bottom: 6px; }
.ai b { color: var(--brand); }
.pfoot { display: flex; align-items: baseline; gap: 3px; }
.rate { display: flex; align-items: center; gap: 6px; margin-bottom: 4px; min-height: 18px; }
.rate :deep(.el-rate) { height: 18px; }
.rate { display: flex; align-items: center; gap: 6px; margin-bottom: 4px; min-height: 18px; }
.rate :deep(.el-rate) { height: 18px; }
.price { color: var(--brand); font-size: 19px; font-weight: 700; }
.per { font-size: 12px; color: var(--ink-4); }
.stock { margin-left: auto; }
.pager { display: flex; justify-content: center; margin-top: 8px; }
</style>
