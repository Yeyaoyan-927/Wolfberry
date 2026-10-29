<template>
  <div class="page narrow">
    <div class="head">
      <h2>卖家资质认证</h2>
      <span class="dim">通过后才能发布商品；资料仅用于平台审核，不对外公开</span>
    </div>

    <!-- 状态卡 -->
    <div class="card status-card" v-if="q">
      <div class="s-left">
        <span class="st" :class="`sq-${q.status}`">{{ q.status_label }}</span>
        <div class="s-desc">
          <template v-if="q.status === 0">尚未提交资质，填写下方资料后提交，平台将在工作时段内审核。</template>
          <template v-else-if="q.status === 1">资料已提交，等待平台审核。审核期间无法发布商品。</template>
          <template v-else-if="q.status === 2">
            已通过认证，可正常发布商品。经营概况：共 {{ q.products_total }} 件商品，在售 {{ q.products_on_shelf }} 件。
          </template>
          <template v-else>审核未通过：{{ q.reject_reason || '未填写原因' }}。请修改后重新提交。</template>
        </div>
      </div>
      <el-button v-if="q.status === 2" plain @click="$router.push('/publish')">去发布商品</el-button>
    </div>

    <!-- 提交表单：未认证/驳回时可见 -->
    <div class="card form-card" v-if="canSubmit">
      <div class="sec-t">{{ q?.status === 3 ? '修改并重新提交' : '提交认证资料' }}</div>
      <el-form label-width="150px">
        <el-form-item label="企业名称" required>
          <el-input v-model="form.company_name" maxlength="128" placeholder="与营业执照一致" />
        </el-form-item>
        <el-form-item label="信用代码">
          <el-input v-model="form.credit_code" maxlength="32" placeholder="个人卖家可留空" />
        </el-form-item>
        <el-form-item label="法定代表人">
          <el-input v-model="form.legal_person" maxlength="64" />
        </el-form-item>
        <el-form-item label="主要产区" required>
          <el-select v-model="form.origin" style="width: 200px">
            <el-option v-for="o in ['中宁', '诺木洪', '靖远', '其他']" :key="o" :label="o" :value="o" />
          </el-select>
        </el-form-item>
        <el-form-item label="联系电话">
          <el-input v-model="form.contact_phone" maxlength="24" placeholder="仅用于平台联系" />
        </el-form-item>
        <el-form-item label="资质说明">
          <el-input v-model="form.intro" type="textarea" :rows="3" maxlength="1000" show-word-limit
                    placeholder="种植规模、加工能力、是否有质检报告等" />
        </el-form-item>
        <el-form-item label="证件照片">
          <div class="uploads">
            <div v-for="(u, i) in form.licenses" :key="i" class="up-img" :style="{ backgroundImage: `url(${u})` }">
              <span class="del" @click="form.licenses.splice(i, 1)">×</span>
            </div>
            <el-upload v-if="form.licenses.length < 6" :show-file-list="false" accept="image/*"
                       :http-request="uploadLicense">
              <div class="up-add">＋</div>
            </el-upload>
          </div>
          <div class="dim hint">营业执照、产地证明、质检报告等，最多 6 张</div>
        </el-form-item>
        <el-form-item>
          <el-button type="primary" :loading="submitting" @click="submit">提交审核</el-button>
        </el-form-item>
      </el-form>
    </div>

    <!-- 已提交资料回显 -->
    <div class="card" v-if="q && q.id">
      <div class="sec-t">已提交资料</div>
      <el-descriptions :column="2" border size="small">
        <el-descriptions-item label="企业名称">{{ q.company_name }}</el-descriptions-item>
        <el-descriptions-item label="信用代码">{{ q.credit_code || '—' }}</el-descriptions-item>
        <el-descriptions-item label="法定代表人">{{ q.legal_person || '—' }}</el-descriptions-item>
        <el-descriptions-item label="主要产区">{{ q.origin || '—' }}</el-descriptions-item>
        <el-descriptions-item label="提交时间">{{ (q.created_at || '').slice(0, 16) }}</el-descriptions-item>
        <el-descriptions-item label="审核时间">{{ (q.audited_at || '').slice(0, 16) || '—' }}</el-descriptions-item>
      </el-descriptions>
      <div v-if="q.licenses?.length" class="lic">
        <div class="sec-t">证件</div>
        <div class="uploads">
          <el-image v-for="(u, i) in q.licenses" :key="i" :src="u" :preview-src-list="q.licenses"
                    fit="cover" class="up-img" />
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { myQualification, submitQualification, uploadImage } from '../../api'

const q = ref(null)
const submitting = ref(false)
const form = reactive({
  company_name: '', credit_code: '', legal_person: '', origin: '中宁',
  contact_phone: '', intro: '', licenses: [],
})

const canSubmit = computed(() => !q.value || [0, 3].includes(q.value.status))

async function load() {
  q.value = await myQualification()
  if (q.value.id) {
    Object.assign(form, {
      company_name: q.value.company_name, credit_code: q.value.credit_code,
      legal_person: q.value.legal_person, origin: q.value.origin || '中宁',
      contact_phone: q.value.contact_phone, intro: q.value.intro,
      licenses: [...(q.value.licenses || [])],
    })
  }
}

async function uploadLicense({ file }) {
  const r = await uploadImage(file, 'after-sale/evidence')
  form.licenses.push(r.url)
}

async function submit() {
  if (form.company_name.trim().length < 2) return ElMessage.warning('请填写企业/合作社名称')
  if (!form.origin) return ElMessage.warning('请选择主要产区')
  submitting.value = true
  try {
    q.value = await submitQualification({ ...form })
    ElMessage.success('已提交，等待平台审核')
  } finally {
    submitting.value = false
  }
}

onMounted(load)
</script>

<style scoped>
.narrow { max-width: 880px; margin: 0 auto; }
.head { display: flex; align-items: baseline; gap: 14px; margin-bottom: 14px; }
.head h2 { margin: 0; font-size: 18px; }
.dim { font-size: 12.5px; color: var(--ink-3); }
.card { padding: 16px 20px; margin-bottom: 14px; }
.status-card { display: flex; align-items: center; justify-content: space-between; gap: 16px; }
.s-left { display: flex; align-items: flex-start; gap: 12px; }
.s-desc { font-size: 13px; color: var(--ink-2); line-height: 1.7; }
.sec-t { font-weight: 700; font-size: 13.5px; margin-bottom: 12px; }
.st { display: inline-block; font-size: 12px; line-height: 20px; padding: 2px 10px;
  border-radius: 4px; border: 1px solid transparent; white-space: nowrap; font-weight: 700; flex: none; }
.sq-0 { color: #8a7462; background: #f1ece7; border-color: #ddd3c9; }
.sq-1 { color: #b07205; background: #fdf3dd; border-color: #efd9a7; }
.sq-2 { color: #1d8a4e; background: #e5f6ec; border-color: #bce5cc; }
.sq-3 { color: var(--brand); background: var(--brand-soft); border-color: var(--brand-line); }
.uploads { display: flex; gap: 8px; flex-wrap: wrap; }
.up-img { width: 88px; height: 88px; border-radius: 8px; border: 1px solid var(--line);
  background: #f3ebe4 center/cover no-repeat; position: relative; }
.up-img .del { position: absolute; right: -6px; top: -6px; width: 18px; height: 18px; border-radius: 50%;
  background: var(--brand); color: #fff; font-size: 13px; line-height: 18px; text-align: center; cursor: pointer; }
.up-add { width: 88px; height: 88px; border: 1px dashed var(--line); border-radius: 8px; display: grid;
  place-items: center; font-size: 22px; color: var(--ink-4); cursor: pointer; }
.up-add:hover { border-color: var(--brand); color: var(--brand); }
.hint { margin-top: 6px; }
.lic { margin-top: 14px; }
</style>
