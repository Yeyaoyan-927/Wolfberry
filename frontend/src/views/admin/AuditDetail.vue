<template>
  <div v-loading="loading">
    <div class="top">
      <el-page-header @back="$router.push('/admin/audit')" :title="'返回队列'" />
      <div class="top-ops" v-if="d.status === 1">
        <el-button type="danger" plain @click="rejectDialog = true">驳回</el-button>
        <el-select v-model="grade" style="width: 130px" placeholder="认定等级">
          <el-option v-for="g in ['特优','特级','甲级','乙级','等外']" :key="g" :label="g" :value="g" />
        </el-select>
        <el-button type="primary" @click="onApprove">通过上架</el-button>
      </div>
      <el-tag v-else :type="{ 3: 'success', 4: 'danger' }[d.status]" size="large">
        {{ { 3: '已上架', 4: '已驳回', 5: '已下架' }[d.status] || `状态${d.status}` }}
      </el-tag>
    </div>

    <div class="grid">
      <!-- 左：商品信息 -->
      <div class="card block">
        <h3>{{ d.title }}</h3>
        <div class="meta dim num">{{ d.product_no }} · {{ d.variety }} / {{ d.origin }} · {{ d.spec_per_50g }}粒/50g · ¥{{ d.unit_price }}/kg · 库存 {{ d.stock }}kg</div>
        <div class="desc">{{ d.description }}</div>
        <el-divider>卖家风险画像</el-divider>
        <div class="risk num" v-if="d.seller_risk">
          <div class="risk-row"><span>30 天红标</span><b :class="{ bad: d.seller_risk.risk_warn }">{{ d.seller_risk.red_flags_30d }} 次</b></div>
          <div class="risk-row"><span>累计驳回</span><b>{{ d.seller_risk.rejected_total }}</b></div>
          <div class="risk-row"><span>历史提交</span><b>{{ d.seller_risk.products_total }}</b></div>
          <el-tag v-if="d.seller_risk.risk_warn" type="danger" size="small">账号预警</el-tag>
        </div>
        <el-divider>审核记录（不可删除）</el-divider>
        <el-timeline v-if="d.audit_logs?.length" class="mini-logs">
          <el-timeline-item v-for="lg in d.audit_logs" :key="lg.id"
                            :timestamp="(lg.acted_at || '').replace('T', ' ').slice(0, 16)"
                            :type="{ approve: 'success', grade: 'primary', reject: 'danger' }[lg.action]">
            <b>{{ { approve: '通过', grade: '改级上架', reject: '驳回' }[lg.action] }}</b>
            → 认定 <GradeTag :grade="lg.grade_platform_after || '—'" />
            <div class="dim">{{ lg.reason }}</div>
          </el-timeline-item>
        </el-timeline>
        <el-empty v-else :image-size="50" description="暂无审核记录" />
      </div>

      <!-- 中：图片墙 -->
      <div class="card block">
        <div class="sec-head"><b>实拍图（{{ d.images?.length || 0 }}）</b></div>
        <div class="imgs">
          <el-image v-for="im in d.images" :key="im.id" class="img" fit="cover"
                    :src="im.url" :preview-src-list="d.images.map((x) => x.url)"
                    :initial-index="d.images.indexOf(im)" preview-teleported hide-on-click-modal>
            <template #error><div class="img-err">加载失败</div></template>
          </el-image>
        </div>
        <div class="l1-note dim">L1 门禁：格式 / 大小 / 短边 ≥800px，不通过的上传时已拦截</div>
      </div>

      <!-- 右：AI 评估 + 操作 -->
      <div class="card block assess-col">
        <div class="sec-head"><span class="berry"></span><b>AI 评估</b>
          <DiffFlag v-if="d.diff_flag" :flag="d.diff_flag" />
          <el-button v-if="d.status === 1" size="small" plain style="margin-left:auto" @click="reassess">重新评估</el-button>
        </div>
        <template v-if="d.assessing">
          <el-alert type="warning" :closable="false" title="评估进行中，可先人工审核，产出后自动补写" />
        </template>
        <template v-else>
          <div class="grades">
            自述 <GradeTag :grade="d.grade_claim" />
            → AI 建议 <GradeTag :grade="d.ai_grade || '灰'" />
            <span class="dim">差异 {{ d.grade_gap ?? '—' }} 级</span>
          </div>
          <div class="a-grid num">
            <div><b>{{ pct(d.defect_ratio) }}</b><span>综合缺陷率</span></div>
            <div><b>{{ pct(d.moldy_ratio) }}</b><span>霉变率</span></div>
            <div><b>{{ d.grain_count ?? '—' }}</b><span>粒数</span></div>
            <div><b>{{ d.ai_confidence ?? '—' }}</b><span>置信</span></div>
          </div>
          <el-table :data="d.assessments || []" size="small" border>
            <el-table-column prop="image_id" label="图" width="46" />
            <el-table-column prop="grain_count" label="粒数" width="60" />
            <el-table-column prop="moldy" label="霉" width="52" />
            <el-table-column prop="bad" label="坏" width="52" />
            <el-table-column prop="oily" label="油" width="52" />
            <el-table-column prop="impurity" label="杂" width="52" />
            <el-table-column prop="image_confidence" label="置信" width="62" />
            <el-table-column label="状态">
              <template #default="{ row }">
                <span v-if="row.valid">有效</span>
                <el-tooltip v-else :content="row.exclude_reason"><el-tag size="small" type="info">剔除</el-tag></el-tooltip>
              </template>
            </el-table-column>
          </el-table>
          <div class="dim model-line" v-if="d.assessments?.length">
            model: {{ d.assessments[0].model_version }} · thresholds: {{ d.assessments[0].threshold_version }}
          </div>
        </template>

        <!-- 操作区（快捷键 A 通过 / R 驳回） -->
        <template v-if="d.status === 1">
          <el-divider>审核操作</el-divider>
          <div class="act">
            <div class="act-row">
              <span class="dim">认定等级</span>
              <el-select v-model="grade" style="width: 130px" placeholder="认定等级" ref="gradeSelect">
                <el-option v-for="g in ['特优','特级','甲级','乙级','等外']" :key="g" :label="g" :value="g" />
              </el-select>
              <span class="kbd-hint dim">AI 有建议时默认带入</span>
            </div>
            <div class="act-btns">
              <el-button type="danger" plain @click="rejectDialog = true">驳回（R）</el-button>
              <el-button type="primary" @click="onApprove">通过上架（A）</el-button>
            </div>
            <div class="kbd-hint dim">快捷键：A 通过 · R 驳回 · E 改级 · → 返回队列</div>
          </div>
        </template>
        <el-tag v-else :type="{ 3: 'success', 4: 'danger', 5: 'info' }[d.status]" size="large" class="done-tag">
          {{ { 3: '已上架', 4: '已驳回', 5: '已下架' }[d.status] || `状态${d.status}` }}
        </el-tag>
      </div>
    </div>

    <!-- 驳回对话框：原因标签点选 -->
    <el-dialog v-model="rejectDialog" title="驳回商品" width="500px">
      <div class="reason-tags">
        <span v-for="(label, code) in rejectReasons" :key="code" class="r-tag"
              :class="{ on: reasonCode === code }" @click="reasonCode = code">{{ label }}</span>
      </div>
      <el-input v-model="note" type="textarea" :rows="2" maxlength="150" show-word-limit
                placeholder="补充说明（可选）" class="note-input" />
      <template #footer>
        <el-button @click="rejectDialog = false">取消</el-button>
        <el-button type="danger" @click="onReject">确认驳回</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { onMounted, onUnmounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { auditApprove, auditDetail, auditReject, auditReassess } from '../../api'
import GradeTag from '../../components/GradeTag.vue'
import DiffFlag from '../../components/DiffFlag.vue'

const route = useRoute()
const router = useRouter()
const d = ref({})
const loading = ref(true)
const grade = ref('')
const rejectDialog = ref(false)
const reasonCode = ref('')
const note = ref('')
const rejectReasons = ref({})

const pct = (v) => (v == null ? '—' : (v * 100).toFixed(2) + '%')

async function load() {
  loading.value = true
  try {
    d.value = await auditDetail(route.params.id)
    grade.value = d.value.ai_grade || ''
  } finally {
    loading.value = false
  }
}

async function onApprove() {
  if (!grade.value) return ElMessage.warning('AI 无建议等级时必须指定认定等级')
  await auditApprove(d.value.id, grade.value)
  ElMessage.success(`已通过上架，认定等级 ${grade.value}`)
  load()
}

async function onReject() {
  if (!reasonCode.value) return ElMessage.warning('请选择驳回原因')
  await auditReject(d.value.id, reasonCode.value, note.value)
  ElMessage.success('已驳回，原因已留痕')
  rejectDialog.value = false
  load()
}

async function reassess() {
  await auditReassess(d.value.id)
  ElMessage.success('已重新评估')
  load()
}

onMounted(async () => {
  const q = await auditQueue({ size: 1 })
  rejectReasons.value = q.reject_reasons || {}
  await load()
  // 快捷键：A 通过 / R 驳回 / E 聚焦改级 / → 返回队列
  window.addEventListener('keydown', onKey)
})

onUnmounted(() => window.removeEventListener('keydown', onKey))

function onKey(e) {
  const tag = e.target?.tagName
  if (['INPUT', 'TEXTAREA', 'SELECT'].includes(tag)) return
  if (d.value.status !== 1) return
  if (e.key === 'a' || e.key === 'A') onApprove()
  else if (e.key === 'r' || e.key === 'R') rejectDialog.value = true
  else if (e.key === 'e' || e.key === 'E') document.activeElement?.blur()
  else if (e.key === 'ArrowRight') router.push('/admin/audit')
}
</script>

<style scoped>
.top { display: flex; justify-content: space-between; align-items: center; margin-bottom: 14px; }
.top-ops { display: flex; gap: 10px; }
.grid { display: grid; grid-template-columns: minmax(0, 1fr) minmax(0, 1.1fr) 400px; gap: 14px; align-items: start; }
.block { padding: 18px 20px; margin-bottom: 14px; }
.block h3 { margin: 0 0 6px; }
.meta { font-size: 12.5px; }
.desc { font-size: 13px; color: var(--ink-2); margin: 10px 0; line-height: 1.7; }
.imgs { display: grid; grid-template-columns: repeat(2, 1fr); gap: 10px; }
.img { height: 150px; border-radius: 8px; background: #f3ebe4; cursor: zoom-in; }
.img-err { height: 100%; display: flex; align-items: center; justify-content: center; color: var(--ink-4); font-size: 12px; }
.l1-note { font-size: 11px; margin-top: 10px; }
.sec-head { display: flex; align-items: center; gap: 8px; margin-bottom: 12px; }
.berry { width: 16px; height: 16px; border-radius: 46% 54% 50% 50% / 58% 58% 42% 42%;
  background: radial-gradient(ellipse at 32% 28%, #ee7a5f 0%, #c22f27 52%, #8e1d18 100%); }
.grades { display: flex; align-items: center; gap: 8px; font-size: 13px; margin-bottom: 12px; flex-wrap: wrap; }
.a-grid { display: grid; grid-template-columns: repeat(2, 1fr); gap: 8px; margin-bottom: 12px; }
.a-grid > div { background: var(--brand-soft); border-radius: 8px; padding: 8px 10px; text-align: center; }
.a-grid b { display: block; font-size: 16px; color: var(--brand); }
.a-grid span { font-size: 11px; color: var(--ink-3); }
.model-line { font-size: 11px; margin-top: 6px; }
.assess-col { position: sticky; top: 12px; }
.risk { display: flex; flex-direction: column; gap: 8px; font-size: 13px; }
.risk-row { display: flex; justify-content: space-between; border-bottom: 1px dashed var(--line); padding-bottom: 6px; }
.risk-row span { color: var(--ink-3); }
.risk-row b.bad { color: var(--brand); }
.mini-logs :deep(.el-timeline-item__content) { font-size: 12.5px; }
.act { display: flex; flex-direction: column; gap: 10px; }
.act-row { display: flex; align-items: center; gap: 10px; }
.act-btns { display: flex; gap: 10px; }
.kbd-hint { font-size: 11px; }
.done-tag { margin-top: 12px; }
.reason-tags { display: flex; flex-wrap: wrap; gap: 8px; margin-bottom: 14px; }
.r-tag { font-size: 12.5px; padding: 5px 12px; border: 1px solid var(--line); border-radius: 999px;
  cursor: pointer; color: var(--ink-2); transition: all .15s; }
.r-tag:hover { border-color: var(--brand); color: var(--brand); }
.r-tag.on { background: var(--brand); border-color: var(--brand); color: #fff; }
.note-input { margin-bottom: 4px; }
</style>
