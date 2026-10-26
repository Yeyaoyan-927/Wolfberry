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
      <!-- 商品 + 图片 -->
      <div class="card block">
        <h3>{{ d.title }}</h3>
        <div class="meta dim num">{{ d.product_no }} · {{ d.variety }} / {{ d.origin }} · {{ d.spec_per_50g }}粒/50g · ¥{{ d.unit_price }}/kg · 库存 {{ d.stock }}kg</div>
        <div class="desc">{{ d.description }}</div>
        <el-divider>实拍图（{{ d.images?.length || 0 }}）</el-divider>
        <div class="imgs">
          <div v-for="im in d.images" :key="im.id" class="img" :style="`background-image:url('${im.url}')`">
            <el-tag size="small" :type="im.l1_status === 1 ? 'success' : 'danger'">{{ im.l1_status === 1 ? 'L1过' : '拦截' }}</el-tag>
          </div>
        </div>
      </div>

      <!-- AI 评估 -->
      <div class="card block">
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

        <el-divider>卖家风险画像</el-divider>
        <div class="risk num" v-if="d.seller_risk">
          <span>30 天红标 <b :class="{ bad: d.seller_risk.risk_warn }">{{ d.seller_risk.red_flags_30d }}</b> 次</span>
          <span>累计驳回 {{ d.seller_risk.rejected_total }}</span>
          <span>历史提交 {{ d.seller_risk.products_total }}</span>
          <el-tag v-if="d.seller_risk.risk_warn" type="danger" size="small">账号预警</el-tag>
        </div>
      </div>
    </div>

    <!-- 审核记录 -->
    <div class="card block logs">
      <div class="sec-head"><b>审核记录（不可删除）</b></div>
      <el-timeline v-if="d.audit_logs?.length">
        <el-timeline-item v-for="lg in d.audit_logs" :key="lg.id" :timestamp="lg.acted_at?.replace('T', ' ')"
                          :type="{ approve: 'success', grade: 'primary', reject: 'danger' }[lg.action]">
          <b>{{ { approve: '通过', grade: '改级上架', reject: '驳回' }[lg.action] }}</b>
          · 自述 <GradeTag :grade="lg.grade_claim || '—'" /> / AI
          <GradeTag :grade="lg.ai_grade || '灰'" /> → 认定 <GradeTag :grade="lg.grade_platform_after || '—'" />
          <DiffFlag v-if="lg.diff_flag" :flag="lg.diff_flag" />
          <div class="dim">{{ lg.reason }}</div>
        </el-timeline-item>
      </el-timeline>
      <el-empty v-else :image-size="60" description="暂无审核记录" />
    </div>

    <!-- 驳回对话框 -->
    <el-dialog v-model="rejectDialog" title="驳回商品" width="460px">
      <el-form label-width="90px">
        <el-form-item label="驳回原因" required>
          <el-select v-model="reasonCode" placeholder="选择原因">
            <el-option v-for="(label, code) in rejectReasons" :key="code" :label="label" :value="code" />
          </el-select>
        </el-form-item>
        <el-form-item label="补充说明">
          <el-input v-model="note" type="textarea" :rows="2" maxlength="150" show-word-limit />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="rejectDialog = false">取消</el-button>
        <el-button type="danger" @click="onReject">确认驳回</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue'
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
})
</script>

<style scoped>
.top { display: flex; justify-content: space-between; align-items: center; margin-bottom: 14px; }
.top-ops { display: flex; gap: 10px; }
.grid { display: grid; grid-template-columns: minmax(0, 1fr) 460px; gap: 14px; align-items: start; }
.block { padding: 18px 20px; margin-bottom: 14px; }
.block h3 { margin: 0 0 6px; }
.meta { font-size: 12.5px; }
.desc { font-size: 13px; color: var(--ink-2); margin: 10px 0; line-height: 1.7; }
.imgs { display: grid; grid-template-columns: repeat(5, 1fr); gap: 10px; }
.img { height: 96px; border-radius: 8px; background: #f3ebe4 center/cover no-repeat; position: relative; }
.img .el-tag { position: absolute; left: 4px; top: 4px; }
.sec-head { display: flex; align-items: center; gap: 8px; margin-bottom: 12px; }
.berry { width: 16px; height: 16px; border-radius: 46% 54% 50% 50% / 58% 58% 42% 42%;
  background: radial-gradient(ellipse at 32% 28%, #ee7a5f 0%, #c22f27 52%, #8e1d18 100%); }
.grades { display: flex; align-items: center; gap: 8px; font-size: 13px; margin-bottom: 12px; flex-wrap: wrap; }
.a-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 8px; margin-bottom: 12px; }
.a-grid > div { background: var(--brand-soft); border-radius: 8px; padding: 8px 10px; text-align: center; }
.a-grid b { display: block; font-size: 16px; color: var(--brand); }
.a-grid span { font-size: 11px; color: var(--ink-3); }
.model-line { font-size: 11px; margin-top: 6px; }
.risk { display: flex; gap: 18px; font-size: 13px; align-items: center; }
.risk b.bad { color: var(--brand); }
.logs { max-width: 100%; }
</style>
