<template>
  <div class="page">
    <section class="hero card">
      <div class="hero-l">
        <h1>枸杞货源 · <span class="text-brand">AI 外观评估</span> · 平台审核背书</h1>
        <p>卖家上传实拍图 → AI 评估缺陷率与等级 → 审核员定级上架 → 买家按客观数据比价下单</p>
        <div class="ops">
          <el-button type="primary" round size="large" @click="$router.push('/products')">逛货源市场</el-button>
          <el-button round size="large" @click="$router.push('/chat')">问 AI · 标准与行情</el-button>
        </div>
      </div>
      <div class="hero-r num">
        <div class="stat"><b>{{ stats.onSale }}</b><span>在售货源</span></div>
        <div class="stat"><b>{{ stats.assessed }}</b><span>AI 评估商品</span></div>
        <div class="stat"><b>{{ stats.audited }}</b><span>平台认定等级</span></div>
      </div>
    </section>

    <section class="sect">
      <div class="sect-head"><h2>最新上架</h2><router-link to="/products" class="more">查看全部 →</router-link></div>
      <el-row :gutter="16">
        <el-col v-for="p in latest" :key="p.id" :span="6" :xs="12">
          <div class="pcard" @click="$router.push(`/products/${p.id}`)">
            <div class="pimg" :style="p.cover_url ? { backgroundImage: `url(${p.cover_url})` } : {}"></div>
            <div class="pbody">
              <div class="ptitle">{{ p.title }}</div>
              <div class="pgrades">
                <GradeTag :grade="p.grade_platform || p.grade_claim" />
                <span class="dim">{{ p.origin }} · {{ p.variety }}</span>
              </div>
              <div class="pfoot">
                <span class="price num">¥{{ p.unit_price }}</span>
                <span class="per">/kg</span>
                <DiffFlag v-if="p.ai_grade || !p.assessing" :flag="flagOf(p)" :gap="p.grade_diff" />
              </div>
            </div>
          </div>
        </el-col>
      </el-row>
      <el-empty v-if="!latest.length" description="暂无上架货源" />
    </section>

    <section class="sect">
      <div class="sect-head">
        <h2>行情速览</h2>
        <router-link to="/market" class="more">行情中心 →</router-link>
      </div>
      <div class="market card">
        <div class="m-left">
          <div class="m-label">{{ mkt.variety }} · {{ mkt.grade }} 近 30 天均价</div>
          <div class="m-price num">¥{{ mkt.summary?.avg ?? '—' }}<span class="u">/kg</span></div>
          <div class="m-sub num" :class="trendCls">
            较前期 {{ mkt.summary?.trend_pct == null ? '—' : (mkt.summary.trend_pct > 0 ? '↑ ' : mkt.summary.trend_pct < 0 ? '↓ ' : '') + Math.abs(mkt.summary.trend_pct) + '%' }}
            · 区间 ¥{{ mkt.summary?.low ?? '—' }} ~ ¥{{ mkt.summary?.high ?? '—' }}
          </div>
        </div>
        <svg v-if="mkt.points?.length" viewBox="0 0 620 110" class="m-chart" preserveAspectRatio="none">
          <path :d="mktArea" fill="#c22f27" opacity=".08" />
          <path :d="mktLine" fill="none" stroke="#C22F27" stroke-width="2" />
        </svg>
      </div>
    </section>

    <section class="sect" v-if="origins.length">
      <div class="sect-head"><h2>按产区找</h2></div>
      <el-row :gutter="16">
        <el-col v-for="o in origins" :key="o.origin" :span="8">
          <div class="ocard card" @click="$router.push({ path: '/products', query: { origin: o.origin } })">
            <div class="o-name">{{ o.origin }}</div>
            <div class="o-meta num">在售 {{ o.count }} 件 · 均价 <b>¥{{ o.avg_price }}</b> /kg 起</div>
            <div class="o-tags">{{ o.varieties.join(' · ') }}</div>
          </div>
        </el-col>
      </el-row>
    </section>

    <section class="sect">
      <div class="sect-head"><h2>平台如何保证「所见即所得」</h2></div>
      <el-row :gutter="16">
        <el-col v-for="w in whys" :key="w.t" :span="8">
          <div class="why card">
            <div class="w-no num">{{ w.no }}</div>
            <div class="w-t">{{ w.t }}</div>
            <div class="w-d">{{ w.d }}</div>
          </div>
        </el-col>
      </el-row>
    </section>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { listProducts, marketOrigins, marketSummary } from '../../api'
import GradeTag from '../../components/GradeTag.vue'
import DiffFlag from '../../components/DiffFlag.vue'

const latest = ref([])
const mkt = ref({})
const origins = ref([])

// 迷你行情折线
const mktLine = computed(() => {
  const pts = mkt.value.points || []
  if (!pts.length) return ''
  const min = Math.min(...pts.map((p) => p.low))
  const max = Math.max(...pts.map((p) => p.high))
  const y = (v) => 100 - ((v - min) / (max - min || 1)) * 88 - 6
  const x = (i) => (i / (pts.length - 1 || 1)) * 620
  return pts.map((p, i) => `${i ? 'L' : 'M'}${x(i).toFixed(1)},${y(p.avg).toFixed(1)}`).join(' ')
})
const mktArea = computed(() => (mktLine.value ? `${mktLine.value} L620,110 L0,110 Z` : ''))
const trendCls = computed(() => {
  const t = mkt.value.summary?.trend_pct
  return t == null ? '' : t > 0 ? 'up' : t < 0 ? 'down' : ''
})
const stats = computed(() => ({
  onSale: latest.value.length,
  assessed: latest.value.filter((p) => p.ai_grade || p.defect_ratio !== null).length,
  audited: latest.value.filter((p) => p.grade_platform).length,
}))

const whys = [
  { no: '01', t: 'AI 外观评估卡', d: '每件货源附缺陷率、粒数、置信度等客观数值，不只听卖家描述。' },
  { no: '02', t: '等级差异标记', d: '卖家自述等级与 AI 建议不一致时，平台自动标黄/标红并重点审核。' },
  { no: '03', t: '评估快照留痕', d: '上架时的评估明细永久保留，售后纠纷可回溯举证。' },
]

function flagOf(p) {
  const conf = p.ai_confidence ?? null
  if (!p.ai_grade || (conf !== null && conf < 0.45)) return '灰'
  if ((p.grade_diff ?? 0) >= 2) return '红'
  if (p.grade_diff === 1) return '黄'
  if (p.grade_diff < 0) return '蓝'
  return '绿'
}

onMounted(async () => {
  try {
    const [data, market, originList] = await Promise.all([
      listProducts({ size: 8, order_by: 'newest' }),
      marketSummary({ variety: '宁杞5号', grade: '特级', days: 30 }).catch(() => ({})),
      marketOrigins().catch(() => []),
    ])
    latest.value = data.items
    mkt.value = market
    origins.value = originList || []
  } catch { /* 已统一提示 */ }
})
</script>

<style scoped>
.hero { display: flex; justify-content: space-between; gap: 24px; padding: 40px 36px;
  background:
    radial-gradient(circle at 96% -20%, rgba(194,47,39,.08), transparent 50%), #fff; }
.hero h1 { margin: 0 0 10px; font-size: 26px; }
.hero p { margin: 0 0 22px; color: var(--ink-3); font-size: 14px; }
.hero-r { display: flex; gap: 28px; align-items: center; }
.stat { text-align: center; }
.stat b { display: block; font-size: 28px; color: var(--brand); }
.stat span { font-size: 12px; color: var(--ink-3); }
.sect { margin-top: 28px; }
.sect-head { display: flex; justify-content: space-between; align-items: baseline; margin-bottom: 14px; }
.sect-head h2 { margin: 0; font-size: 18px; padding-left: 13px; position: relative; }
.sect-head h2::before { content: ""; position: absolute; left: 0; top: .42em; width: 8px; height: 8px;
  border-radius: 50% 50% 46% 46% / 58% 58% 42% 42%;
  background: radial-gradient(ellipse at 32% 26%, #ee7a5f 0%, #c22f27 48%, #8e1d18 100%); }
.more { font-size: 13px; color: var(--ink-3); }
.pcard { background: #fff; border: 1px solid var(--line); border-radius: 12px; overflow: hidden;
  cursor: pointer; transition: box-shadow .2s, transform .2s; margin-bottom: 16px; }
.pcard:hover { box-shadow: 0 8px 24px rgba(120,60,40,.12); transform: translateY(-2px); }
.pimg { height: 150px; background: #f3ebe4 center/cover no-repeat; }
.pbody { padding: 12px 14px 14px; }
.ptitle { font-size: 13.5px; font-weight: 600; line-height: 1.45; height: 39px;
  display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden; }
.pgrades { display: flex; gap: 8px; align-items: center; margin: 8px 0 6px; }
.dim { font-size: 12px; color: var(--ink-3); }
.pfoot { display: flex; align-items: baseline; gap: 3px; }
.price { color: var(--brand); font-size: 19px; font-weight: 700; }
.per { font-size: 12px; color: var(--ink-4); }
.pfoot .dtag { margin-left: auto; }
.why { padding: 18px 20px; }
.w-no { font-size: 12px; color: var(--brand); font-weight: 700; letter-spacing: 1px; }
.w-t { font-weight: 700; margin: 6px 0; }
.w-d { font-size: 13px; color: var(--ink-3); line-height: 1.7; }
.market { display: flex; align-items: center; gap: 24px; padding: 18px 24px; }
.m-left { flex: none; min-width: 300px; }
.m-label { font-size: 12.5px; color: var(--ink-3); }
.m-price { font-size: 34px; font-weight: 800; color: var(--brand); line-height: 1.2; margin: 4px 0; }
.m-price .u { font-size: 13px; color: var(--ink-4); font-weight: 400; margin-left: 4px; }
.m-sub { font-size: 12.5px; color: var(--ink-3); }
.up { color: #c22f27; font-weight: 600; }
.down { color: #1d8a4e; font-weight: 600; }
.m-chart { flex: 1; height: 110px; }
.ocard { padding: 16px 18px; cursor: pointer; transition: all .15s; }
.ocard:hover { border-color: var(--brand-line); box-shadow: 0 6px 18px rgba(120,60,40,.08); }
.o-name { font-size: 17px; font-weight: 700; }
.o-meta { font-size: 12.5px; color: var(--ink-3); margin: 6px 0 4px; }
.o-meta b { color: var(--brand); }
.o-tags { font-size: 11.5px; color: var(--ink-4); }
</style>
