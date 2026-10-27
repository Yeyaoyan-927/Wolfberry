<template>
  <div v-loading="loading">
    <!-- KPI -->
    <el-row :gutter="14">
      <el-col v-for="k in kpis" :key="k.label" :span="6">
        <div class="kpi card">
          <div class="k-label">{{ k.label }}</div>
          <div class="k-value num" :class="k.color">{{ k.value }}</div>
          <div class="k-sub dim">{{ k.sub }}</div>
        </div>
      </el-col>
    </el-row>

    <el-row :gutter="14" class="row2">
      <!-- 近 7 天上架趋势（纯 CSS 柱状图，零依赖） -->
      <el-col :span="14">
        <div class="card block">
          <div class="b-head">近 7 天上架趋势</div>
          <div class="bars">
            <div v-for="d in trend" :key="d.date" class="bar-item">
              <div class="bar-wrap">
                <div class="bar" :style="{ height: barH(d.count) + 'px' }"></div>
              </div>
              <div class="bar-v num">{{ d.count || '' }}</div>
              <div class="bar-d dim">{{ d.date.slice(5) }}</div>
            </div>
          </div>
        </div>
      </el-col>
      <!-- 快捷入口 + 知识库状态 -->
      <el-col :span="10">
        <div class="card block">
          <div class="b-head">平台概况</div>
          <div class="facts num">
            <div class="fact"><span>买家 / 卖家</span><b>{{ s.users?.buyers ?? 0 }} / {{ s.users?.sellers ?? 0 }}</b></div>
            <div class="fact"><span>今日 AI 评估</span><b>{{ s.assessment?.today ?? 0 }} 次</b></div>
            <div class="fact"><span>知识库文档 / 切片</span><b>{{ s.kb?.docs ?? 0 }} / {{ s.kb?.chunks ?? 0 }}</b></div>
            <div class="fact"><span>订单状态分布</span>
              <b class="mini">
                <el-tag v-for="(c, st) in s.orders?.by_status || {}" :key="st" v-show="c"
                        size="small" effect="plain" class="m-tag num">
                  {{ { 1: '待确认', 2: '待发货', 3: '已发货', 4: '已完成', 5: '已取消' }[st] }} {{ c }}
                </el-tag>
              </b>
            </div>
          </div>
          <div class="ops">
            <el-button type="primary" plain size="small" @click="$router.push('/admin/audit')">
              去审核（{{ s.products?.pending ?? 0 }} 条待审）
            </el-button>
            <el-button plain size="small" @click="$router.push('/admin/kb')">管理知识库</el-button>
          </div>
        </div>
      </el-col>
    </el-row>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { adminStats } from '../../api'

const s = ref({})
const loading = ref(true)

const kpis = computed(() => [
  { label: '在售货源', value: s.value.products?.on_shelf ?? 0, sub: `共 ${s.value.products?.total ?? 0} 个商品`, color: 'c-brand' },
  { label: '待审核', value: s.value.products?.pending ?? 0, sub: '审核队列待处理', color: 'c-warn' },
  { label: '成交总额', value: `¥${s.value.orders?.gmv ?? 0}`, sub: `订单 ${s.value.orders?.total ?? 0} 笔`, color: 'c-brand' },
  { label: '已驳回', value: s.value.products?.rejected ?? 0, sub: '历史驳回商品', color: 'c-dim' },
])

const trend = computed(() => s.value.publish_trend || [])
const maxCount = computed(() => Math.max(1, ...trend.value.map((d) => d.count)))
const barH = (c) => Math.round((c / maxCount.value) * 120) + 4

onMounted(async () => {
  try {
    s.value = await adminStats()
  } finally {
    loading.value = false
  }
})
</script>

<style scoped>
.kpi { padding: 18px 20px; }
.k-label { font-size: 12.5px; color: var(--ink-3); }
.k-value { font-size: 26px; font-weight: 800; margin: 6px 0 4px; }
.c-brand { color: var(--brand); }
.c-warn { color: #b07205; }
.c-dim { color: var(--ink-2); }
.k-sub { font-size: 11.5px; }
.row2 { margin-top: 14px; }
.block { padding: 16px 20px; }
.b-head { font-weight: 700; margin-bottom: 14px; }
.bars { display: flex; gap: 18px; align-items: flex-end; height: 170px; padding: 0 6px; }
.bar-item { flex: 1; text-align: center; }
.bar-wrap { height: 130px; display: flex; align-items: flex-end; justify-content: center; }
.bar { width: 34px; border-radius: 5px 5px 0 0;
  background: linear-gradient(180deg, var(--brand), #e8a49a); min-height: 4px; }
.bar-v { font-size: 12px; color: var(--brand); font-weight: 600; margin-top: 4px; min-height: 16px; }
.bar-d { font-size: 11px; }
.facts { display: flex; flex-direction: column; gap: 10px; }
.fact { display: flex; justify-content: space-between; align-items: center; font-size: 13px;
  border-bottom: 1px dashed var(--line); padding-bottom: 8px; }
.fact span { color: var(--ink-3); }
.fact .mini { display: flex; gap: 6px; flex-wrap: wrap; justify-content: flex-end; }
.m-tag { font-weight: 400; }
.ops { margin-top: 14px; display: flex; gap: 10px; }
</style>
