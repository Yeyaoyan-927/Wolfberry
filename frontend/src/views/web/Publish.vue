<template>
  <div class="page">
    <div class="head">
      <h2>发布货源</h2>
      <span class="dim">上传实拍图 → AI 自动外观评估（异步）→ 平台审核后上架</span>
    </div>

    <el-steps :active="created ? 2 : 0" align-center class="steps">
      <el-step title="基本信息" description="品种 / 产区 / 等级自述" />
      <el-step title="交易信息" description="价格 / 库存 / 起订量" />
      <el-step title="实拍图与评估" description="上传 → AI 评估 → 提交审核" />
    </el-steps>

    <div class="grid">
      <!-- 表单 -->
      <div class="card form-card">
        <el-form label-width="90px">
          <el-form-item label="标题" required>
            <el-input v-model="form.title" maxlength="200" show-word-limit
                      placeholder="如：中宁宁杞5号 特级 280粒/50g 2026 新货" />
          </el-form-item>
          <el-form-item label="品种" required>
            <el-select v-model="form.variety" style="width: 200px">
              <el-option v-for="v in ['宁杞5号','宁杞7号','大麻叶']" :key="v" :label="v" :value="v" />
            </el-select>
          </el-form-item>
          <el-form-item label="产区" required>
            <el-input v-model="form.origin" style="width: 200px" placeholder="如：中宁" />
          </el-form-item>
          <el-form-item label="等级自述" required>
            <el-radio-group v-model="form.grade_claim">
              <el-radio-button v-for="g in ['特优','特级','甲级','乙级']" :key="g" :value="g">{{ g }}</el-radio-button>
            </el-radio-group>
            <div class="hint">自述等级将与 AI 建议比对，高报 1 级标黄、≥2 级标红，请如实填写</div>
          </el-form-item>
          <el-form-item label="粒数规格" required>
            <el-input-number v-model="form.spec_per_50g" :min="100" :max="1000" :step="10" />
            <span class="hint2">粒 / 50g</span>
          </el-form-item>
          <el-form-item label="单价" required>
            <el-input-number v-model="form.unit_price" :min="1" :precision="2" />
            <span class="hint2">元 / kg</span>
          </el-form-item>
          <el-form-item label="库存" required>
            <el-input-number v-model="form.stock" :min="1" />
            <span class="hint2">kg</span>
          </el-form-item>
          <el-form-item label="起订量" required>
            <el-input-number v-model="form.min_order_qty" :min="1" />
            <span class="hint2">kg</span>
          </el-form-item>
          <el-form-item label="描述">
            <el-input v-model="form.description" type="textarea" :rows="3" maxlength="2000" show-word-limit />
          </el-form-item>
          <el-form-item>
            <el-button type="primary" :loading="submitting" @click="submit">创建商品</el-button>
          </el-form-item>
        </el-form>
      </div>

      <!-- 图片上传与评估结果 -->
      <div class="card up-card">
        <!-- 实时预览：买家将看到 -->
        <div class="preview">
          <div class="pv-head dim">买家将看到</div>
          <div class="pv-card">
            <div class="pv-img" :style="images[0] ? { backgroundImage: `url(${images[0].url})` } : {}">
              <span v-if="!images.length" class="pv-ph">实拍图</span>
            </div>
            <div class="pv-body">
              <div class="pv-title">{{ form.title || '（商品标题）' }}</div>
              <div class="pv-meta">
                <span class="gtag" :class="`grade-${form.grade_claim}`">{{ form.grade_claim }}</span>
                <span class="dim">{{ form.origin || '产区' }} · {{ form.variety }}</span>
              </div>
              <div class="pv-price num">¥{{ form.unit_price || '—' }} <i>/kg</i></div>
            </div>
          </div>
          <el-alert v-if="form.grade_claim === '特优' || form.grade_claim === '特级'" type="warning"
                    :closable="false" show-icon class="pv-warn"
                    :title="`自述「${form.grade_claim}」将接受 AI 比对：高报 1 级标黄、≥2 级标红`" />
        </div>

        <el-divider />

        <template v-if="!created">
          <el-empty description="完成左侧信息创建商品后，在此上传实拍图（3~8 张，短边≥800px）" :image-size="70" />
        </template>
        <template v-else>
          <div class="up-head">
            <el-tag>商品 #{{ created.id }} 已创建（待审核）</el-tag>
          </div>
          <el-upload drag multiple accept=".jpg,.jpeg,.png,.webp" :show-file-list="false"
                     :before-upload="beforeUpload" :http-request="doUpload">
            <el-icon size="36" class="up-icon"><UploadFilled /></el-icon>
            <div class="el-upload__text">拖拽或点击上传实拍图</div>
          </el-upload>

          <div class="imgs">
            <div v-for="im in images" :key="im.id" class="up-item">
              <div class="up-img" :style="`background-image:url('${im.url}')`"></div>
              <el-tag size="small" :type="im.l1_status === 1 ? 'success' : 'danger'" class="up-tag">
                {{ im.l1_status === 1 ? '通过' : '拦截' }}
              </el-tag>
            </div>
          </div>

          <el-alert v-if="assessing" type="warning" :closable="false" show-icon
                    title="AI 评估进行中…" description="评估异步执行，通常几秒内完成；完成后商品详情与审核工作台可见评估卡" />
          <div v-else-if="assessment" class="assess-result">
            <el-divider>AI 评估结果</el-divider>
            <el-descriptions :column="2" border size="small">
              <el-descriptions-item label="建议等级">{{ assessment.ai_grade || '灰（不参与）' }}</el-descriptions-item>
              <el-descriptions-item label="加权置信">{{ assessment.ai_confidence }}</el-descriptions-item>
              <el-descriptions-item label="综合缺陷率">{{ pct(assessment.defect_ratio) }}</el-descriptions-item>
              <el-descriptions-item label="识别粒数">{{ assessment.grain_count }}</el-descriptions-item>
            </el-descriptions>
            <el-button class="re" size="small" plain @click="reassess">重新评估</el-button>
          </div>
        </template>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { createProduct, getProduct, uploadProductImage } from '../../api'
import { auditReassess } from '../../api'

const form = ref({
  title: '', variety: '宁杞5号', origin: '中宁', grade_claim: '特级',
  spec_per_50g: 280, unit_price: 46, stock: 500, min_order_qty: 50,
  description: '',
})
const created = ref(null)
const images = ref([])
const submitting = ref(false)
const assessing = ref(false)
const assessment = ref(null)

const pct = (v) => (v == null ? '—' : (v * 100).toFixed(2) + '%')

// 评估是否完成：ai_grade 或 grain_count 出现即视为完成
const refreshAssessment = computed(() => null)

async function submit() {
  const f = form.value
  if (!f.title || !f.origin) return ElMessage.warning('请填写标题与产区')
  submitting.value = true
  try {
    created.value = await createProduct(f)
    ElMessage.success('商品已创建，请上传实拍图')
  } finally {
    submitting.value = false
  }
}

function beforeUpload(file) {
  const ok = ['image/jpeg', 'image/png', 'image/webp'].includes(file.type)
  if (!ok) ElMessage.error('仅支持 jpg/png/webp')
  return ok
}

async function doUpload({ file }) {
  assessing.value = true
  try {
    const im = await uploadProductImage(created.value.id, file)
    images.value.push(im)
    ElMessage.success(`已上传 ${im.file_name}，评估已排队`)
    setTimeout(pollAssessment, 2500)
  } catch {
    assessing.value = false
  }
}

let pollTimer = null
async function pollAssessment() {
  try {
    const d = await getProduct(created.value.id)
    if (d.ai_grade !== null || d.grain_count !== null) {
      assessment.value = d
      assessing.value = false
    } else {
      pollTimer = setTimeout(pollAssessment, 2000)
    }
  } catch {
    assessing.value = false
  }
}

async function reassess() {
  assessing.value = true
  assessment.value = null
  try {
    await auditReassess(created.value.id)
    await pollAssessment()
  } finally {
    assessing.value = false
  }
}

onMounted(() => clearTimeout(pollTimer))
</script>

<style scoped>
.head { margin-bottom: 10px; display: flex; align-items: baseline; gap: 14px; }
.head h2 { margin: 0; font-size: 18px; }
.dim { font-size: 12.5px; color: var(--ink-3); }
.steps { margin-bottom: 18px; background: #fff; border: 1px solid var(--line); border-radius: 12px; padding: 16px 10px 10px; }
.grid { display: grid; grid-template-columns: minmax(0, 1fr) 420px; gap: 16px; align-items: start; }
.form-card { padding: 20px 22px 8px; }
.hint { font-size: 11.5px; color: var(--ink-4); margin-top: 4px; }
.hint2 { margin-left: 8px; color: var(--ink-3); font-size: 12.5px; }
.up-card { padding: 18px 20px; min-height: 300px; }
.preview { margin-bottom: 4px; }
.pv-head { font-weight: 600; margin-bottom: 8px; }
.pv-card { display: flex; gap: 12px; border: 1px solid var(--line); border-radius: 10px; padding: 12px; background: #fffaf8; }
.pv-img { width: 84px; height: 84px; border-radius: 8px; background: #f3ebe4 center/cover no-repeat; flex: none;
  display: flex; align-items: center; justify-content: center; }
.pv-ph { font-size: 11px; color: var(--ink-4); }
.pv-body { min-width: 0; }
.pv-title { font-size: 13px; font-weight: 600; line-height: 1.4; height: 36px;
  display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden; }
.pv-meta { display: flex; gap: 8px; align-items: center; margin: 6px 0; }
.gtag { display: inline-block; padding: 1px 8px; font-size: 12px; line-height: 18px;
  border: 1px solid transparent; border-radius: 4px; font-weight: 600; }
.pv-price { color: var(--brand); font-weight: 700; font-size: 17px; }
.pv-price i { font-style: normal; font-size: 11px; color: var(--ink-4); font-weight: 400; }
.pv-warn { margin-top: 10px; }
.up-head { margin-bottom: 12px; }
.up-icon { color: var(--brand); }
.imgs { display: grid; grid-template-columns: repeat(4, 1fr); gap: 10px; margin-top: 14px; }
.up-item { position: relative; }
.up-img { height: 92px; border-radius: 8px; background: #f3ebe4 center/cover no-repeat; border: 1px solid var(--line); }
.up-tag { position: absolute; left: 4px; top: 4px; }
.assess-result { margin-top: 4px; }
.re { margin-top: 10px; }
@media (max-width: 1000px) { .grid { grid-template-columns: 1fr; } }
</style>
