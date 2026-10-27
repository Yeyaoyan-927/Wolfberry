<template>
  <div class="page">
    <div class="head">
      <h2>行情中心</h2>
      <span class="dim">基于平台成交与挂牌数据聚合 · 仅供参考</span>
    </div>

    <div class="filter card">
      <el-select v-model="variety" style="width: 140px" @change="load">
        <el-option v-for="v in opts.varieties" :key="v" :label="v" :value="v" />
      </el-select>
      <el-radio-group v-model="grade" @change="load">
        <el-radio-button v-for="g in opts.grades" :key="g" :value="g">{{ g }}</el-radio-button>
      </el-radio-group>
      <el-radio-group v-model="days" @change="load">
        <el-radio-button :value="30">近 30 天</el-radio-button>
        <el-radio-button :value="90">近 90 天</el-radio-button>
      </el-radio-group>
    </div>

    <el-row :gutter="14" v-loading="loading">
      <el-col :span="17">
        <div class="card block">
          <div class="between">
            <b>{{ variety }} · {{ grade }} 成交均价走势</b>
            <span class="dim num">{{ points.length }} 个交易日</span>
          </div>
          <!-- 纯 SVG 折线图（零依赖） -->
          <div class="chart-wrap">
            <svg v-if="points.length" :viewBox="`0 0 ${W} ${H}`" class="chart" preserveAspectRatio="none">
              <defs>
                <linearGradient id="g" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stop-color="#C22F27" stop-opacity=".22" />
                  <stop offset="100%" stop-color="#C22F27" stop-opacity="0" />
                </linearGradient>
              </defs>
              <!-- 网格 -->
              <line v-for="i in 4" :key="'grid' + i" :x1="0" :x2="W"
                    :y1="(H / 4) * i" :y2="(H / 4) * i" stroke="#eee6df" stroke-width="1" />
              <!-- 面积 -->
              <path :d="areaPath" fill="url(#g)" />
              <!-- 折线 -->
              <path :d="linePath" fill="none" stroke="#C22F27" stroke-width="2.2" stroke-linejoin="round" />
              <!-- 数据点 -->
              <circle v-for="(p, i) in points" :key="'pt' + i" :cx="x(i)" :cy="y(p.avg)" r="3" fill="#C22F27">
                <title>{{ p.date }} ¥{{ p.avg }}（{{ p.count }} 样）</title>
              </circle>
            </svg>
            <el-empty v-else description="该维度暂无成交数据" :image-size="70" />
          </div>
          <div class="axis">
            <span v-for="(p, i) in points" :key="'ax' + i" class="ax-item">{{ p.date.slice(5) }}</span>
          </div>
        </div>
      </el-col>
      <el-col :span="7">
        <div class="card block">
          <div class="b-head">近期概览</div>
          <template v-if="summary">
            <div class="big-num num">¥{{ summary.avg }}<span class="u">/kg 均价</span></div>
            <div class="kv">
              <div class="kv-row"><span class="k">价格区间</span><span class="v num">¥{{ summary.low }} ~ ¥{{ summary.high }}</span></div>
              <div class="kv-row"><span class="k">样本量</span><span class="v num">{{ summary.samples }}</span></div>
              <div class="kv-row"><span class="k">近期趋势</span>
                <span class="v num" :class="summary.trend_pct > 0 ? 'up' : summary.trend_pct < 0 ? 'down' : ''">
                  {{ summary.trend_pct == null ? '—' : (summary.trend_pct > 0 ? '↑ ' : summary.trend_pct < 0 ? '↓ ' : '') + Math.abs(summary.trend_pct) + '%' }}
                </span></div>
            </div>
            <div class="dim tip">涨跌按最近 3 个交易日均值 vs 前序均值计算；数据来自平台成交记录。</div>
          </template>
          <el-empty v-else :image-size="60" description="暂无数据" />
        </div>
      </el-col>
    </el-row>

    <div class="card block" style="margin-top:14px">
      <div class="b-head">逐日明细</div>
      <el-table :data="points" size="small" max-height="320" :header-cell-style="{ background: '#faf6f3' }">
        <el-table-column prop="date" label="日期" width="120" />
        <el-table-column prop="avg" label="均价" width="100" align="right">
          <template #default="{ row }"><span class="num">¥{{ row.avg }}</span></template>
        </el-table-column>
        <el-table-column prop="low" label="最低" width="90" align="right" />
        <el-table-column prop="high" label="最高" width="90" align="right" />
        <el-table-column prop="count" label="样本" width="80" align="right" />
        <el-table-column label="较前日" align="right">
          <template #default="{ row, $index }">
            <span v-if="$index > 0" class="num" :class="delta(row, $index) > 0 ? 'up' : delta(row, $index) < 0 ? 'down' : ''">
              {{ delta(row, $index) > 0 ? '+' : '' }}{{ delta(row, $index) }}%
            </span>
            <span v-else class="dim">—</span>
          </template>
        </el-table-column>
      </el-table>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { marketSummary } from '../../api'

const W = 760
const H = 260
const opts = ref({ varieties: [], grades: [], origins: [] })
const variety = ref('宁杞5号')
const grade = ref('特级')
const days = ref(30)
const points = ref([])
const summary = ref(null)
const loading = ref(false)

const minV = computed(() => Math.min(...points.value.map((p) => p.low), Infinity))
const maxV = computed(() => Math.max(...points.value.map((p) => p.high), -Infinity))
const pad = computed(() => Math.max(0.5, (maxV.value - minV.value) * 0.12))

function x(i) { return points.value.length <= 1 ? W / 2 : (i / (points.value.length - 1)) * W }
function y(v) {
  const lo = minV.value - pad.value
  const hi = maxV.value + pad.value
  return H - ((v - lo) / (hi - lo || 1)) * H
}
const linePath = computed(() => points.value.map((p, i) => `${i ? 'L' : 'M'}${x(i)},${y(p.avg)}`).join(' '))
const areaPath = computed(() =>
  points.value.length ? `${linePath.value} L${x(points.value.length - 1)},${H} L0,${H} Z` : '')

function delta(row, i) {
  const prev = points.value[i - 1]
  if (!prev?.avg) return 0
  return Number((((row.avg - prev.avg) / prev.avg) * 100).toFixed(1))
}

async function load() {
  loading.value = true
  try {
    const d = await marketSummary({ variety: variety.value, grade: grade.value, days: days.value })
    points.value = d.points
    summary.value = d.summary
    opts.value = d.options
    if (!variety.value) variety.value = '宁杞5号'
    if (!grade.value) grade.value = '特级'
  } finally {
    loading.value = false
  }
}

onMounted(load)
</script>

<style scoped>
.head { display: flex; align-items: baseline; gap: 14px; margin-bottom: 14px; }
.head h2 { margin: 0; font-size: 18px; }
.dim { font-size: 12.5px; color: var(--ink-3); }
.filter { display: flex; gap: 14px; align-items: center; padding: 12px 16px; margin-bottom: 14px; flex-wrap: wrap; }
.block { padding: 16px 20px; }
.between { display: flex; justify-content: space-between; align-items: baseline; margin-bottom: 12px; }
.chart-wrap { height: 260px; }
.chart { width: 100%; height: 100%; }
.axis { display: flex; justify-content: space-between; margin-top: 6px; overflow: hidden; }
.ax-item { font-size: 10.5px; color: var(--ink-4); }
.b-head { font-weight: 700; margin-bottom: 12px; }
.big-num { font-size: 30px; font-weight: 800; color: var(--brand); }
.big-num .u { font-size: 12px; color: var(--ink-4); font-weight: 400; margin-left: 4px; }
.kv-row { display: flex; justify-content: space-between; font-size: 13px; padding: 6px 0;
  border-bottom: 1px dashed var(--line); }
.kv-row .k { color: var(--ink-3); }
.up { color: #c22f27; font-weight: 600; }
.down { color: #1d8a4e; font-weight: 600; }
.tip { font-size: 11px; line-height: 1.7; margin-top: 10px; }
</style>
