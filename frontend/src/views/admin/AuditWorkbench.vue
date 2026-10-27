<template>
  <div class="wb" v-loading="loading">
    <!-- 顶部队列条 -->
    <div class="queue-bar card">
      <div class="qitem">待审核 <b>{{ qs.pending }}</b></div>
      <div class="qitem">今日已审 <b>{{ qs.audited_today }}</b></div>
      <div class="qitem" :class="{ danger: qs.overtime > 0 }">超时 <b>{{ qs.overtime }}</b></div>
      <div class="q-progress">
        <span class="dim">队列进度</span>
        <div class="pbar"><div class="pfill" :style="{ width: progressPct + '%' }"></div></div>
        <span class="dim num">{{ idx + 1 }} / {{ queue.length || 1 }}</span>
      </div>
      <div class="q-nav">
        <el-button size="small" :disabled="idx <= 0" @click="goto(idx - 1)">上一条</el-button>
        <el-button size="small" :disabled="idx >= queue.length - 1" @click="goto(idx + 1)">下一条 →</el-button>
      </div>
    </div>

    <div class="shell" v-if="d.id">
      <!-- ============ 左：商品与卖家 ============ -->
      <div class="col card">
        <div class="sec">
          <div class="between"><span class="dim num">{{ d.product_no }}</span>
            <span class="dim">{{ (d.created_at || '').slice(5, 16).replace('T', ' ') }}</span></div>
          <div class="w-title">{{ d.title }}</div>
        </div>

        <div class="sec">
          <div class="sec-t">自述与报价</div>
          <div class="claim-card">
            <div><div class="dim">卖家自述等级</div>
              <div style="margin-top:5px"><GradeTag :grade="d.grade_claim" /></div></div>
            <div class="claim-price">
              <div class="dim">报价</div>
              <div class="num price">¥{{ d.unit_price }}<span class="u">/kg</span></div>
            </div>
          </div>
          <div class="kv">
            <div class="kv-row"><span class="k">品种 / 规格</span><span class="v">{{ d.variety }} · {{ d.spec_per_50g }} 粒/50g</span></div>
            <div class="kv-row"><span class="k">产区</span><span class="v">{{ d.origin }}</span></div>
            <div class="kv-row"><span class="k">库存 / 起订</span><span class="v num">{{ d.stock }} kg / {{ d.min_order_qty }} kg</span></div>
            <div class="kv-row"><span class="k">图片数量</span><span class="v num">{{ d.images?.length || 0 }} 张</span></div>
            <div class="kv-row"><span class="k">AI 建议等级</span><span class="v"><GradeTag :grade="d.ai_grade || '灰'" /></span></div>
          </div>
        </div>

        <div class="sec">
          <div class="sec-t">卖家信息与风险</div>
          <div class="kv">
            <div class="kv-row"><span class="k">卖家 ID</span><span class="v num">#{{ d.seller_id }}</span></div>
            <div class="kv-row"><span class="k">30 天红标</span>
              <span class="v"><b :class="{ bad: d.seller_risk?.risk_warn }" class="num">{{ d.seller_risk?.red_flags_30d ?? 0 }}</b> 次
                <el-tag v-if="d.seller_risk?.risk_warn" type="danger" size="small" style="margin-left:4px">预警</el-tag></span></div>
            <div class="kv-row"><span class="k">累计驳回</span><span class="v num">{{ d.seller_risk?.rejected_total ?? 0 }} 次</span></div>
            <div class="kv-row"><span class="k">历史提交</span><span class="v num">{{ d.seller_risk?.products_total ?? 0 }} 件</span></div>
          </div>
        </div>

        <div class="sec" v-if="d.market">
          <div class="sec-t">同类行情参考</div>
          <div class="kv">
            <div class="kv-row"><span class="k">近 30 天成交均价</span><span class="v num">¥{{ d.market.avg_30d }}（{{ d.market.samples }} 样）</span></div>
            <div class="kv-row"><span class="k">本单报价偏离</span>
              <span class="v num" :class="{ 'dev-bad': Math.abs(d.market.deviation_pct) > 10 }">{{ d.market.deviation_pct > 0 ? '+' : '' }}{{ d.market.deviation_pct }}%</span></div>
            <div class="kv-row"><span class="k">价格区间</span><span class="v num">¥{{ d.market.low }} ~ ¥{{ d.market.high }}</span></div>
          </div>
        </div>

        <div class="sec">
          <div class="sec-t">卖家描述</div>
          <div class="desc">{{ d.description || '—' }}</div>
        </div>
      </div>

      <!-- ============ 中：图片 ============ -->
      <div class="col col-mid">
        <div class="mid-head card">
          <el-segmented v-model="tab" :options="[
            { label: `实拍图 ${d.images?.length || 0}`, value: 'raw' },
            { label: 'AI 标注图', value: 'mask' },
            { label: '门禁结果', value: 'gate' }]" />
          <span class="dim">← → 切换图片 · 点击放大</span>
        </div>

        <div class="mid-body">
          <!-- 实拍 / 标注：图片网格 -->
          <template v-if="tab !== 'gate'">
            <div class="img-grid">
              <div v-for="(im, i) in d.images" :key="im.id" class="aimg card"
                   :class="{ sel: curImg === i }" @click="curImg = i">
                <el-image :src="im.url" fit="cover" class="aimg-img"
                          :preview-src-list="[im.url]" preview-teleported hide-on-click-modal
                          @click.stop />
                <span class="idx">{{ i + 1 }} {{ im.file_name?.slice(0, 10) }}</span>
                <span class="ov num" v-if="im.width">{{ im.width }}×{{ im.height }}</span>
                <!-- AI 标注叠加 -->
                <template v-if="tab === 'mask'">
                  <span v-for="(b, bi) in boxesOf(im.id)" :key="bi" class="dbox"
                        :class="'dbox-' + b.label"
                        :style="boxStyle(b, im)" :title="boxTitle(b)"></span>
                  <span class="mask-note" v-if="!boxesOf(im.id).length">无检测框</span>
                </template>
              </div>
            </div>
            <div class="legend card" v-if="tab === 'mask'">
              <span class="lg"><i class="dot dot-moldy"></i>霉变</span>
              <span class="lg"><i class="dot dot-bad"></i>坏果</span>
              <span class="lg"><i class="dot dot-oily"></i>油果</span>
              <span class="lg"><i class="dot dot-normal"></i>正常</span>
              <span class="dim legend-note">框为 AI 定位（伪评估为启发式定位，非像素级分割）</span>
            </div>
          </template>

          <!-- 门禁结果 -->
          <template v-else>
            <div class="card gate">
              <div v-for="im in d.images" :key="im.id" class="gate-row">
                <span class="num gate-idx">图 {{ im.id }}</span>
                <el-tag size="small" :type="im.l1_status === 1 ? 'success' : 'danger'">
                  L1 {{ im.l1_status === 1 ? '通过' : '拦截' }}
                </el-tag>
                <span class="dim num">{{ im.width }}×{{ im.height }}</span>
                <span class="dim gate-detail">{{ gateText(im) }}</span>
              </div>
              <div v-for="a in d.assessments || []" :key="'l2' + a.image_id" class="gate-row">
                <span class="num gate-idx">图 {{ a.image_id }}</span>
                <el-tag size="small" :type="a.valid ? 'success' : 'warning'">L2 {{ a.valid ? '有效' : '剔除' }}</el-tag>
                <span class="dim num">粒 {{ a.grain_count }} · 置信 {{ a.image_confidence }}</span>
                <span class="dim gate-detail" v-if="!a.valid">{{ a.exclude_reason }}</span>
              </div>
            </div>
          </template>

          <!-- 识别汇总 -->
          <div class="card summary">
            <div class="between"><b>识别汇总</b><span class="dim">多张有效图合并计算</span></div>
            <div class="metrics num">
              <div class="m"><div class="mk">总粒数</div><div class="mv">{{ d.grain_count ?? '—' }}<span class="u">粒</span></div></div>
              <div class="m"><div class="mk">综合缺陷率</div><div class="mv" :class="{ bad: (d.defect_ratio ?? 0) > 0.05 }">{{ pct(d.defect_ratio) }}</div></div>
              <div class="m"><div class="mk">霉变率</div><div class="mv" :class="{ bad: (d.moldy_ratio ?? 0) > 0.015 }">{{ pct(d.moldy_ratio) }}</div></div>
              <div class="m"><div class="mk">图级置信</div><div class="mv">{{ d.ai_confidence ?? '—' }}</div></div>
            </div>
            <div class="dim s-note">粒数为多张有效图合并计数总和，缺陷率按合并计数计算（非各图比率的平均值）。</div>
          </div>
        </div>
      </div>

      <!-- ============ 右：评估与操作 ============ -->
      <div class="col card col-right">
        <div class="sec">
          <div class="between"><b>AI 外观评估</b><el-tag size="small" effect="plain">仅外观</el-tag></div>
          <div class="metrics num" style="margin-top:10px">
            <div class="m"><div class="mk">建议等级</div><div class="mv">{{ d.ai_grade || '灰' }}</div></div>
            <div class="m"><div class="mk">置信度</div><div class="mv">{{ d.ai_confidence ?? '—' }}</div></div>
            <div class="m"><div class="mk">相对自述</div><div class="mv">{{ gapText }}</div></div>
          </div>

          <div class="diff-box" :class="'diff-' + (d.diff_flag || '灰')">
            <span class="flag-tag">{{ flagText }}</span>
            <div class="diff-text">{{ diffAdvice }}</div>
          </div>

          <div v-if="d.rules?.length" class="rules">
            <div class="dim rules-t">命中规则</div>
            <div class="between rule-row" v-for="r in d.rules" :key="r.code">
              <span>{{ r.code }} {{ r.desc }}</span>
              <span class="num">{{ r.value }}</span>
              <el-tag size="small" :type="r.hit ? 'danger' : 'success'">{{ r.hit ? '命中' : '通过' }}</el-tag>
            </div>
          </div>

          <div class="dim model-line" v-if="d.assessments?.length">
            {{ d.assessments[0].model_version }} · {{ d.assessments[0].threshold_version }}
            <template v-if="d.assessing"> · 评估中</template>
          </div>
        </div>

        <div class="sec" v-if="d.status === 1">
          <div class="sec-t">审核操作</div>
          <div class="ops">
            <button class="op-btn" @click="approveAs">通过（按自述{{ d.grade_claim }}）<span class="kbd">A</span></button>
            <button class="op-btn" @click="approveAs(true)">改级通过（按 AI 建议）<span class="kbd">E</span></button>
            <button class="op-btn danger focus" @click="rejectDialog = true">驳回 <span class="kbd">R</span></button>
            <button class="op-btn small" disabled title="后续版本提供">要求补充材料</button>
            <button class="op-btn small" disabled title="后续版本提供">标记违规并下架</button>
          </div>
        </div>

        <div class="sec" v-if="d.status === 1">
          <div class="sec-t">审核备注</div>
          <el-input v-model="note" type="textarea" :rows="3" maxlength="150" show-word-limit
                    placeholder="备注会同步给卖家（驳回时建议填写）" />
          <div class="chips">
            <span class="chip" v-for="c in chips" :key="c" @click="note = note ? note + '；' + c : c">{{ c }}</span>
          </div>
        </div>

        <div class="sec kbd-sec">
          <span class="kbd">A</span><span class="dim">通过</span>
          <span class="kbd">E</span><span class="dim">改级</span>
          <span class="kbd">R</span><span class="dim">驳回</span>
          <span class="kbd">→</span><span class="dim">下一条</span>
        </div>

        <div class="sec" v-if="d.audit_logs?.length">
          <div class="sec-t">历史审核记录</div>
          <div v-for="lg in d.audit_logs" :key="lg.id" class="hlog">
            <b :class="{ ok: lg.action !== 'reject', bad: lg.action === 'reject' }">
              {{ { approve: '通过', grade: '改级上架', reject: '驳回' }[lg.action] }}</b>
            <span class="dim"> → {{ lg.grade_platform_after || '—' }} · {{ (lg.acted_at || '').slice(5, 16).replace('T', ' ') }}</span>
            <div class="dim hlog-r">{{ lg.reason }}</div>
          </div>
        </div>
      </div>
    </div>

    <el-empty v-else-if="!loading" description="队列为空，全部审完 🎉" />

    <!-- 驳回弹层 -->
    <el-dialog v-model="rejectDialog" title="驳回商品" width="520px">
      <div class="modal-sub dim">{{ d.title }} · {{ d.product_no }}</div>
      <div class="sec-t" style="margin-top:12px">驳回原因 *</div>
      <div class="reason-tags">
        <span v-for="(label, code) in rejectReasons" :key="code" class="r-tag"
              :class="{ on: reasonCode === code }" @click="reasonCode = code">{{ label }}</span>
      </div>
      <div class="sec-t">补充说明 *（至少 10 字，卖家可见）</div>
      <el-input v-model="note" type="textarea" :rows="3" maxlength="150" show-word-limit />
      <template #footer>
        <el-button @click="rejectDialog = false">取消</el-button>
        <el-button type="danger" @click="onReject">确认驳回</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { auditApprove, auditDetail, auditQueue, auditReassess, auditReject, queueStats } from '../../api'
import { useAuthStore } from '../../stores/auth'
import GradeTag from '../../components/GradeTag.vue'

const auth = useAuthStore()
const route = useRoute()
const router = useRouter()

const queue = ref([])          // 待审商品 id 列表
const idx = ref(0)
const qs = ref({ pending: 0, audited_today: 0, overtime: 0 })
const d = ref({})
const loading = ref(true)
const tab = ref('raw')
const curImg = ref(0)
const note = ref('')
const grade = ref('')
const rejectDialog = ref(false)
const reasonCode = ref('')
const rejectReasons = ref({})
const chips = ['缺陷率与自述不符', '请补充细节图', '图片光照不足']

const pct = (v) => (v == null ? '—' : (v * 100).toFixed(2) + '%')
const progressPct = computed(() => (queue.value.length ? ((idx.value + 1) / queue.value.length) * 100 : 0))

const gapText = computed(() => {
  if (d.value.grade_gap == null) return '—'
  if (d.value.grade_gap === 0) return '一致'
  return d.value.grade_gap > 0 ? `高报 ${d.value.grade_gap} 级` : `低报 ${-d.value.grade_gap} 级`
})
const flagText = computed(() => ({
  红: `自述高报 ${d.value.grade_gap ?? 2} 级`, 黄: '自述高报 1 级',
  绿: '自述与 AI 一致', 蓝: '自述低于 AI 建议', 灰: 'AI 不参与判定',
}[d.value.diff_flag] || '—'))
const diffAdvice = computed(() => {
  const f = d.value.diff_flag
  const dr = (d.value.defect_ratio ?? 0)
  if (f === '红') return `卖家自述 ${d.value.grade_claim}，AI 建议 ${d.value.ai_grade}。综合缺陷率 ${pct(d.value.defect_ratio)}，建议驳回或改级通过。`
  if (f === '黄') return `自述高报 1 级，综合缺陷率 ${pct(d.value.defect_ratio)}，建议改级为 ${d.value.ai_grade} 或重点核对图片。`
  if (f === '灰') return `AI 置信不足（${d.value.ai_confidence ?? '—'} < 0.45），不参与判定，请人工核对图片定级。`
  if (f === '蓝') return 'AI 建议高于自述，可考虑按 AI 建议改级，减少卖家损失。'
  return `自述与 AI 建议一致，综合缺陷率 ${pct(dr)}，各项指标达标。`
})

function boxesOf(imageId) {
  const a = (d.value.assessments || []).find((x) => x.image_id === imageId)
  return a?.raw?.boxes || []
}
function boxStyle(b, im) {
  // 伪评估框以检测圆心+半径换算为百分比定位
  const left = (b.x / (im.width || 1)) * 100
  const top = (b.y / (im.height || 1)) * 100
  const size = (b.r * 2 / (im.width || 1)) * 100
  return { left: left - size / 2 + '%', top: top - size / 2 + '%', width: size + '%', height: size + '%' }
}
function boxTitle(b) {
  return { moldy: '疑似霉变', bad: '疑似坏果', oily: '疑似油果', normal: '正常果' }[b.label] || '果实'
}
function gateText(im) {
  const det = im.l1_detail || {}
  return det.reason || (det.width ? `短边 ${det.short_side}px · ${(det.size / 1024).toFixed(0)}KB` : '')
}

async function loadQueue() {
  const q = await auditQueue({ size: 100 })
  queue.value = q.items.map((i) => i.id)
  rejectReasons.value = q.reject_reasons || {}
}

async function loadDetail(id) {
  loading.value = true
  try {
    d.value = await auditDetail(id)
    grade.value = d.value.ai_grade || ''
    curImg.value = 0
    tab.value = 'raw'
  } finally {
    loading.value = false
  }
}

async function goto(i) {
  idx.value = i
  router.replace({ query: { id: queue.value[i] } })
  await loadDetail(queue.value[i])
}

async function refreshAfterAction() {
  await loadQueue()
  qs.value = await queueStats()
  // 审核完当前商品后自动跳下一个
  if (queue.value.length) {
    idx.value = Math.min(idx.value, queue.value.length - 1)
    await loadDetail(queue.value[idx.value])
  } else {
    d.value = {}
  }
}

async function approveAs(byAi) {
  const target = byAi ? (grade.value || d.value.ai_grade) : d.value.grade_claim
  if (!target) return ElMessage.warning('无可依据的等级，请先人工定级')
  await auditApprove(d.value.id, target)
  ElMessage.success(`已通过上架，认定等级 ${target}`)
  refreshAfterAction()
}

async function onReject() {
  if (!reasonCode.value) return ElMessage.warning('请选择驳回原因')
  if (note.value.trim().length < 10) return ElMessage.warning('补充说明至少 10 字，卖家需要知道驳回原因')
  await auditReject(d.value.id, reasonCode.value, note.value)
  ElMessage.success('已驳回，原因已留痕')
  rejectDialog.value = false
  note.value = ''
  refreshAfterAction()
}

async function onKey(e) {
  const tag = e.target?.tagName
  if (['INPUT', 'TEXTAREA', 'SELECT'].includes(tag)) return
  if (!d.value.id || d.value.status !== 1) return
  if (e.key === 'a' || e.key === 'A') approveAs(false)
  else if (e.key === 'e' || e.key === 'E') approveAs(true)
  else if (e.key === 'r' || e.key === 'R') rejectDialog.value = true
  else if (e.key === 'ArrowRight' && idx.value < queue.value.length - 1) goto(idx.value + 1)
  else if (e.key === 'ArrowLeft' && idx.value > 0) goto(idx.value - 1)
}

onMounted(async () => {
  window.addEventListener('keydown', onKey)
  try {
    await loadQueue()
    const stats = await queueStats()
    qs.value = stats
    const wantId = Number(route.query.id) || queue.value[0]
    idx.value = Math.max(0, queue.value.indexOf(wantId))
    if (wantId) await loadDetail(wantId)
  } finally {
    loading.value = false
  }
})
onUnmounted(() => window.removeEventListener('keydown', onKey))
</script>

<style scoped>
.queue-bar { display: flex; align-items: center; gap: 22px; padding: 12px 20px; margin-bottom: 14px; }
.qitem { font-size: 12.5px; color: var(--ink-3); display: flex; align-items: baseline; gap: 5px; }
.qitem b { font-size: 17px; font-weight: 700; color: var(--ink-1); font-variant-numeric: tabular-nums; }
.qitem.danger, .qitem.danger b { color: var(--brand); }
.q-progress { margin-left: auto; display: flex; align-items: center; gap: 10px; }
.pbar { width: 130px; height: 4px; border-radius: 999px; background: var(--line); overflow: hidden; }
.pfill { height: 100%; background: var(--brand); transition: width .3s; }
.shell { display: grid; grid-template-columns: 320px minmax(0, 1fr) 380px; gap: 14px; align-items: start; }
.col { overflow: hidden; }
.col-mid { background: transparent; border: none; box-shadow: none; }
.sec { padding: 14px 16px; border-bottom: 1px solid var(--line); }
.sec:last-child { border-bottom: none; }
.sec-t { font-size: 11px; font-weight: 600; color: var(--ink-3); letter-spacing: .06em; margin-bottom: 10px; }
.between { display: flex; align-items: center; justify-content: space-between; }
.dim { color: var(--ink-3); }
.w-title { font-size: 15px; font-weight: 700; line-height: 1.45; margin-top: 6px; }
.claim-card { display: flex; align-items: center; justify-content: space-between; gap: 12px;
  padding: 12px 14px; border-radius: 8px; background: var(--brand-soft); border: 1px solid var(--brand-line); }
.claim-price { text-align: right; }
.price { font-size: 19px; font-weight: 800; color: var(--brand); }
.price .u { font-size: 11px; color: var(--ink-4); font-weight: 400; }
.kv-row { display: flex; justify-content: space-between; gap: 12px; font-size: 12.5px; padding: 4px 0; }
.kv-row .k { color: var(--ink-3); flex-shrink: 0; }
.kv-row .v { text-align: right; }
.kv-row .v.bad { color: var(--brand); }
.dev-bad { color: var(--brand); font-weight: 700; }
.desc { font-size: 12.5px; color: var(--ink-2); line-height: 1.75; white-space: pre-wrap; }
.mid-head { display: flex; align-items: center; justify-content: space-between; padding: 10px 16px; margin-bottom: 12px; }
.mid-body { padding: 0 2px 12px; }
.img-grid { display: grid; grid-template-columns: repeat(2, 1fr); gap: 12px; }
.aimg { position: relative; aspect-ratio: 4/3; overflow: hidden; cursor: pointer; padding: 0; }
.aimg.sel { outline: 2px solid var(--brand); }
.aimg-img { width: 100%; height: 100%; }
.aimg :deep(.el-image__inner) { transition: transform .2s; }
.aimg:hover :deep(.el-image__inner) { transform: scale(1.03); }
.aimg .idx { position: absolute; left: 8px; top: 8px; font-size: 11px; background: rgba(0,0,0,.55);
  color: #fff; border-radius: 4px; padding: 2px 7px; z-index: 3; }
.aimg .ov { position: absolute; right: 8px; bottom: 8px; font-size: 10.5px; background: rgba(0,0,0,.55);
  color: #fff; border-radius: 4px; padding: 2px 6px; z-index: 3; }
.dbox { position: absolute; border: 2px dashed; border-radius: 4px; z-index: 2; pointer-events: auto; }
.dbox-moldy { border-color: #e0453a; }
.dbox-bad { border-color: #c9771f; }
.dbox-oily { border-color: #6b5bd6; }
.dbox-normal { border-color: #2ba05f; }
.mask-note { position: absolute; left: 8px; bottom: 8px; font-size: 10.5px; color: var(--ink-4);
  background: rgba(255,255,255,.85); border-radius: 4px; padding: 2px 6px; z-index: 3; }
.legend { display: flex; gap: 14px; align-items: center; padding: 8px 14px; margin-top: 12px; font-size: 12px; }
.lg { display: flex; align-items: center; gap: 5px; }
.dot { width: 9px; height: 9px; border-radius: 3px; border: 2px dashed; display: inline-block; }
.dot-moldy { border-color: #e0453a; }
.dot-bad { border-color: #c9771f; }
.dot-oily { border-color: #6b5bd6; }
.dot-normal { border-color: #2ba05f; }
.legend-note { margin-left: auto; font-size: 10.5px; }
.gate { padding: 6px 16px; }
.gate-row { display: flex; align-items: center; gap: 12px; padding: 8px 0; border-bottom: 1px dashed var(--line); font-size: 12.5px; }
.gate-row:last-child { border-bottom: none; }
.gate-idx { width: 46px; color: var(--ink-2); }
.gate-detail { flex: 1; text-align: right; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.summary { padding: 14px 16px; margin-top: 14px; }
.metrics { display: grid; grid-template-columns: repeat(4, 1fr); gap: 8px; }
.m { background: var(--brand-soft); border-radius: 8px; padding: 8px 10px; text-align: center; }
.mk { font-size: 11px; color: var(--ink-3); }
.mv { font-size: 16px; font-weight: 700; color: var(--ink-1); }
.mv.bad { color: var(--brand); }
.mv .u { font-size: 10px; color: var(--ink-4); font-weight: 400; }
.s-note { font-size: 10.5px; margin-top: 8px; line-height: 1.7; }
.col-right { position: sticky; top: 12px; }
.diff-box { border-radius: 8px; padding: 12px 14px; margin-top: 12px; border: 1px solid var(--line); }
.diff-红 { background: #fdecec; border-color: #f3c1c1; }
.diff-黄 { background: #fdf3dd; border-color: #efd9a7; }
.diff-绿 { background: #e5f6ec; border-color: #bce5cc; }
.diff-蓝 { background: #e8f1fb; border-color: #c4dcf4; }
.diff-灰 { background: #f1ece7; border-color: #ddd3c9; }
.flag-tag { display: inline-block; font-size: 12.5px; font-weight: 700; margin-bottom: 6px;
  color: var(--brand); }
.diff-绿 .flag-tag { color: #1d8a4e; }
.diff-蓝 .flag-tag { color: #1f5fa8; }
.diff-灰 .flag-tag { color: var(--ink-3); }
.diff-text { font-size: 12.5px; line-height: 1.7; color: var(--ink-2); }
.rules { margin-top: 12px; }
.rules-t { font-size: 11px; margin-bottom: 6px; }
.rule-row { font-size: 12px; padding: 4px 0; gap: 8px; }
.model-line { font-size: 10.5px; margin-top: 10px; }
.ops { display: flex; flex-direction: column; gap: 8px; }
.op-btn { display: flex; align-items: center; justify-content: space-between; height: 42px;
  padding: 0 14px; border-radius: 8px; border: 1px solid var(--line); background: #fff;
  font-size: 13.5px; color: var(--ink-1); cursor: pointer; transition: all .15s; }
.op-btn:hover { border-color: var(--brand-line); background: var(--brand-soft); }
.op-btn.danger { color: var(--brand); border-color: var(--brand-line); background: var(--brand-soft); font-weight: 600; }
.op-btn.small { height: 34px; font-size: 12.5px; color: var(--ink-3); }
.op-btn:disabled { opacity: .5; cursor: not-allowed; }
.kbd { display: inline-block; min-width: 20px; text-align: center; font-size: 11px; font-weight: 700;
  border: 1px solid var(--line); border-bottom-width: 2px; border-radius: 4px; padding: 1px 5px;
  color: var(--ink-3); background: var(--bg); }
.chips { display: flex; gap: 8px; flex-wrap: wrap; margin-top: 8px; }
.chip { font-size: 12px; border: 1px solid var(--line); border-radius: 999px; padding: 4px 10px;
  cursor: pointer; color: var(--ink-2); }
.chip:hover { border-color: var(--brand); color: var(--brand); }
.kbd-sec { display: flex; gap: 8px; align-items: center; background: var(--bg); }
.hlog { font-size: 12.5px; padding: 6px 0; border-bottom: 1px dashed var(--line); }
.hlog:last-child { border-bottom: none; }
.hlog .ok { color: #1d8a4e; }
.hlog .bad { color: var(--brand); }
.hlog-r { font-size: 11.5px; margin-top: 2px; }
.modal-sub { font-size: 12px; margin-bottom: 4px; }
.reason-tags { display: flex; flex-wrap: wrap; gap: 8px; margin-bottom: 14px; }
.r-tag { font-size: 12.5px; padding: 5px 12px; border: 1px solid var(--line); border-radius: 999px;
  cursor: pointer; color: var(--ink-2); transition: all .15s; }
.r-tag:hover { border-color: var(--brand); color: var(--brand); }
.r-tag.on { background: var(--brand); border-color: var(--brand); color: #fff; }
@media (max-width: 1200px) { .shell { grid-template-columns: 1fr; } .col-right { position: static; } }
</style>
