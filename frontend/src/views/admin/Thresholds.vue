<template>
  <div v-loading="loading">
    <el-row :gutter="14">
      <el-col :span="8">
        <div class="card block">
          <div class="b-head">图像评估模型</div>
          <div class="kv">
            <div class="kv-row"><span class="k">模型版本</span><span class="v num">{{ t.model_version }}</span></div>
            <div class="kv-row"><span class="k">阈值版本</span><span class="v num">{{ t.threshold_version }}</span></div>
            <div class="kv-row"><span class="k">检测器</span><span class="v num">{{ t.detector }}</span></div>
          </div>
          <el-alert type="info" :closable="false" class="note"
                    title="换 YOLO 模型：权重放 var/models/goji-seg.onnx，改 ASSESS_MODEL_VERSION 即生效" />
        </div>
      </el-col>
      <el-col :span="8">
        <div class="card block">
          <div class="b-head">置信度门限</div>
          <div class="kv">
            <div class="kv-row"><span class="k">灰线（AI 不参与判定）</span><span class="v num">&lt; {{ t.gray_conf }}</span></div>
            <div class="kv-row"><span class="k">图级剔除线</span><span class="v num">&lt; {{ t.min_image_conf }}</span></div>
            <div class="kv-row"><span class="k">代表性下限（总粒数）</span><span class="v num">{{ t.min_grains }}</span></div>
          </div>
          <div class="dim note">低于灰线时等级判定交人工，商品页显示「AI 不参与判定」。</div>
        </div>
      </el-col>
      <el-col :span="8">
        <div class="card block">
          <div class="b-head">等级判定线</div>
          <el-table :data="t.grade_lines" size="small" :header-cell-style="{ background: '#faf6f3' }">
            <el-table-column prop="grade" label="等级" width="70" />
            <el-table-column prop="defect" label="综合缺陷率" />
            <el-table-column prop="moldy" label="霉变率" />
          </el-table>
        </div>
      </el-col>
    </el-row>

    <div class="card block" style="margin-top:14px">
      <div class="b-head">阈值参数（后端 grading.py）</div>
      <el-table :data="thresholdRows" size="small" border :header-cell-style="{ background: '#faf6f3' }">
        <el-table-column prop="key" label="参数" width="220" />
        <el-table-column prop="value" label="当前值" width="140" align="right" />
        <el-table-column prop="desc" label="含义" />
      </el-table>
    </div>

    <div class="card block" style="margin-top:14px">
      <div class="b-head">审核命中规则（R1~R6）</div>
      <el-table :data="rules" size="small" border :header-cell-style="{ background: '#faf6f3' }">
        <el-table-column prop="code" label="编号" width="70" align="center" />
        <el-table-column prop="desc" label="规则描述" />
        <el-table-column prop="note" label="说明" />
      </el-table>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { adminThresholds } from '../../api'

const t = ref({})
const loading = ref(true)

const LABELS = {
  moldy_veto: ['霉变率一票否决线', '超过即判等外，禁止上架'],
  teyou_defect: ['特优综合缺陷率上限', '≤ 该值且霉变为 0'],
  teyou_moldy: ['特优霉变率上限', '特优不允许有霉变'],
  teji_defect: ['特级综合缺陷率上限', ''],
  teji_moldy: ['特级霉变率上限', ''],
  jia_defect: ['甲级综合缺陷率上限', ''],
  jia_moldy: ['甲级霉变率上限', ''],
  yi_defect: ['乙级综合缺陷率上限', '超过则判等外'],
}

const thresholdRows = computed(() =>
  Object.entries(t.value.thresholds || {}).map(([k, v]) => ({
    key: k,
    value: typeof v === 'number' && v < 1 ? `${(v * 100).toFixed(1)}%` : v,
    desc: LABELS[k]?.[0] || '',
  })),
)

const rules = [
  { code: 'R1', desc: '霉变率 ≤ 1.5%', note: '一票否决：超过直接判等外' },
  { code: 'R2', desc: '特优综合缺陷率 ≤ 1.0%', note: '特优硬性线，且无霉变粒' },
  { code: 'R3', desc: '特级综合缺陷率 ≤ 2.0%', note: '特级硬性线' },
  { code: 'R4', desc: '综合缺陷率 ≤ 5%', note: '甲级线；超过按乙级/等外判定' },
  { code: 'R5', desc: 'AI 置信 < 0.45 不参与判定', note: '灰标，交人工' },
  { code: 'R6', desc: '杂质率 ≤ 1%', note: '超过提示挑拣后重拍' },
]

onMounted(async () => {
  try {
    t.value = await adminThresholds()
  } finally {
    loading.value = false
  }
})
</script>

<style scoped>
.block { padding: 16px 20px; }
.b-head { font-weight: 700; margin-bottom: 12px; }
.kv-row { display: flex; justify-content: space-between; gap: 12px; font-size: 13px; padding: 5px 0;
  border-bottom: 1px dashed var(--line); }
.kv-row:last-child { border-bottom: none; }
.kv-row .k { color: var(--ink-3); }
.dim { color: var(--ink-3); }
.note { margin-top: 10px; font-size: 11.5px; }
</style>
