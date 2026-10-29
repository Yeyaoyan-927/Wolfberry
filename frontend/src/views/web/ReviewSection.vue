<template>
  <div class="card rev">
    <div class="r-head">
      <b>买家评价</b>
      <span class="dim num" v-if="summary.review_count">共 {{ summary.review_count }} 条</span>
    </div>

    <template v-if="summary.review_count">
      <div class="overview">
        <div class="score">
          <div class="big num">{{ summary.rating_avg }}</div>
          <el-rate :model-value="Math.round(summary.rating_avg)" disabled size="small" />
          <div class="dim">{{ summary.review_count }} 位买家评价</div>
        </div>
        <div class="bars">
          <div v-for="star in [5, 4, 3, 2, 1]" :key="star" class="bar-row" @click="pickStar(star)">
            <span class="lab">{{ star }}星</span>
            <div class="bar"><i :style="{ width: pct(star) }"></i></div>
            <span class="cnt num">{{ summary.dist?.[star] || 0 }}</span>
          </div>
        </div>
        <div class="extras">
          <div class="ex"><b class="num">{{ summary.good_rate }}%</b><span>好评率（4~5 星）</span></div>
          <div class="ex"><b class="num">{{ summary.with_images }}</b><span>带图评价</span></div>
        </div>
      </div>

      <div class="filters">
        <span class="f" :class="{ on: !star }" @click="pickStar(null)">全部</span>
        <span v-for="s in [5, 4, 3, 2, 1]" :key="s" class="f" :class="{ on: star === s }"
              @click="pickStar(s)">{{ s }} 星（{{ summary.dist?.[s] || 0 }}）</span>
      </div>

      <div v-for="r in items" :key="r.id" class="item">
        <div class="i-head">
          <span class="avatar">{{ (r.buyer_name || '')[0] }}</span>
          <span class="name">{{ r.buyer_name }}</span>
          <el-rate :model-value="r.rating" disabled size="small" />
          <span class="flex1"></span>
          <span class="dim num">{{ (r.created_at || '').slice(0, 10) }}</span>
        </div>
        <div v-if="r.tags?.length" class="i-tags">
          <span v-for="t in r.tags" :key="t" class="tg">{{ t }}</span>
        </div>
        <div class="i-text">{{ r.content || '此买家未填写文字评价' }}</div>
        <div v-if="r.images?.length" class="i-imgs">
          <el-image v-for="(u, i) in r.images" :key="i" :src="u" :preview-src-list="r.images"
                    fit="cover" class="i-img" />
        </div>
        <div v-if="r.reply" class="i-reply">
          <b>卖家回复：</b>{{ r.reply }}
        </div>
      </div>

      <div v-if="total > items.length" class="more">
        <el-button size="small" :loading="loading" @click="loadMore">加载更多</el-button>
      </div>
    </template>
    <el-empty v-else :image-size="70" description="还没有买家评价，收货后可评价" />
  </div>
</template>

<script setup>
import { onMounted, ref, watch } from 'vue'
import { productReviews } from '../../api'

const props = defineProps({ productId: { type: [Number, String], required: true } })

const items = ref([])
const total = ref(0)
const summary = ref({ rating_avg: 0, review_count: 0, dist: {}, good_rate: 0, with_images: 0 })
const star = ref(null)
const page = ref(1)
const loading = ref(false)

function pct(s) {
  const n = summary.value.review_count || 0
  if (!n) return '0%'
  return `${Math.round(((summary.value.dist?.[s] || 0) / n) * 100)}%`
}

function pickStar(s) {
  star.value = s
  page.value = 1
  items.value = []
  load()
}

async function load(append = false) {
  loading.value = true
  try {
    const d = await productReviews(props.productId, { rating: star.value || undefined, page: page.value, size: 5 })
    summary.value = d.summary || summary.value
    total.value = d.total || 0
    items.value = append ? [...items.value, ...(d.items || [])] : (d.items || [])
  } catch {
    items.value = []
  } finally {
    loading.value = false
  }
}

function loadMore() {
  page.value += 1
  load(true)
}

onMounted(load)
watch(() => props.productId, () => { page.value = 1; items.value = []; load() })
</script>

<style scoped>
.rev { padding: 18px 20px; margin-top: 14px; }
.r-head { display: flex; align-items: baseline; gap: 10px; margin-bottom: 14px; }
.r-head b { font-size: 15px; }
.dim { font-size: 12.5px; color: var(--ink-3); }
.overview { display: grid; grid-template-columns: 160px minmax(0, 1fr) 150px; gap: 20px;
  align-items: center; padding-bottom: 14px; border-bottom: 1px solid var(--line); }
.score { text-align: center; }
.score .big { font-size: 38px; font-weight: 800; color: var(--brand); line-height: 1.1; }
.bars { display: flex; flex-direction: column; gap: 5px; }
.bar-row { display: grid; grid-template-columns: 34px minmax(0, 1fr) 30px; gap: 8px;
  align-items: center; cursor: pointer; }
.bar-row:hover .lab { color: var(--brand); }
.lab { font-size: 12px; color: var(--ink-3); }
.bar { height: 7px; background: #f1ece7; border-radius: 4px; overflow: hidden; }
.bar i { display: block; height: 100%; background: var(--brand); border-radius: 4px; }
.cnt { font-size: 11.5px; color: var(--ink-4); text-align: right; }
.extras { display: flex; flex-direction: column; gap: 10px; }
.ex { text-align: center; background: var(--brand-soft); border-radius: 8px; padding: 8px; }
.ex b { display: block; font-size: 17px; color: var(--brand); }
.ex span { font-size: 11px; color: var(--ink-3); }
.filters { display: flex; flex-wrap: wrap; gap: 8px; margin: 14px 0; }
.f { font-size: 12.5px; padding: 3px 10px; border-radius: 14px; border: 1px solid var(--line);
  cursor: pointer; color: var(--ink-2); }
.f:hover { border-color: var(--brand); color: var(--brand); }
.f.on { background: var(--brand); border-color: var(--brand); color: #fff; }
.item { padding: 12px 0; border-bottom: 1px dashed var(--line); }
.i-head { display: flex; align-items: center; gap: 8px; margin-bottom: 6px; }
.avatar { width: 26px; height: 26px; border-radius: 50%; background: var(--brand-soft); color: var(--brand);
  display: grid; place-items: center; font-size: 12px; font-weight: 700; }
.name { font-size: 12.5px; color: var(--ink-2); }
.flex1 { flex: 1; }
.i-tags { display: flex; gap: 6px; flex-wrap: wrap; margin-bottom: 6px; }
.tg { font-size: 11.5px; padding: 1px 8px; border-radius: 10px; background: #f3ece7; color: var(--ink-2); }
.i-text { font-size: 13px; line-height: 1.75; color: var(--ink-1); white-space: pre-wrap; }
.i-imgs { display: flex; gap: 8px; margin-top: 8px; flex-wrap: wrap; }
.i-img { width: 76px; height: 76px; border-radius: 6px; border: 1px solid var(--line); }
.i-reply { margin-top: 8px; font-size: 12.5px; color: var(--ink-2); background: #faf6f3;
  border-radius: 6px; padding: 8px 10px; line-height: 1.7; }
.more { text-align: center; padding-top: 12px; }
@media (max-width: 900px) {
  .overview { grid-template-columns: 1fr; }
}
</style>
