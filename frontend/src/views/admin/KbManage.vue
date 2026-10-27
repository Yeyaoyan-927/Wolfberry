<template>
  <div class="lr">
    <!-- 左树：知识分类 + 状态 -->
    <div class="tree card">
      <div class="t-head">知识分类</div>
      <div class="t-group" v-for="g in tree" :key="g.name">
        <div class="t-lv1">{{ g.name }}</div>
        <div v-for="n in g.children" :key="g.name + n.key" class="t-node"
             :class="{ on: pick_.group === g.name && pick_.key === n.key }" @click="pick(g.name, n.key)">
          {{ n.label }}<span class="cnt num">{{ n.count }}</span>
        </div>
      </div>
      <div class="kb-status dim num">MySQL 切片：{{ chunksTotal }} 条</div>
    </div>

    <!-- 右表 -->
    <div class="card table-card">
      <div class="bar">
        <el-input v-model="keyword" placeholder="搜索标题" clearable style="width: 200px" @keyup.enter="load" />
        <el-upload :show-file-list="false" accept=".pdf,.docx,.md,.txt,.markdown" :before-upload="beforeUpload"
                   :http-request="doUpload">
          <el-button type="primary" :loading="uploading">
            <el-icon style="margin-right:4px"><UploadFilled /></el-icon>上传文档
          </el-button>
        </el-upload>
        <span class="dim num">共 {{ total }} 篇</span>
        <span class="flex1"></span>
        <el-button size="small" plain @click="runEval" :loading="evaluating">检索效果评估</el-button>
      </div>

      <el-alert v-if="evalResult" type="success" :closable="true" class="eval-bar"
                :title="`评测完成：${evalResult.cases} 题，Recall@5 = ${evalResult.recall_at_k}，MRR = ${evalResult.mrr}`" />

      <el-alert v-if="loadError" type="error" :closable="false" class="eval-bar"
                :title="`加载失败：${loadError}`" />

      <el-table :data="items" v-loading="loading" :header-cell-style="{ background: '#faf6f3' }">
        <el-table-column label="文档" min-width="280">
          <template #default="{ row }">
            <div class="d-name">{{ row.title }}</div>
            <div class="dim num">{{ row.file_name }}</div>
          </template>
        </el-table-column>
        <el-table-column prop="doc_type" label="分类" width="100" />
        <el-table-column label="分块" width="70" align="right">
          <template #default="{ row }"><span class="num">{{ row.chunk_count }}</span></template>
        </el-table-column>
        <el-table-column label="状态" width="90" align="center">
          <template #default="{ row }">
            <el-tag size="small" :type="{ 2: 'success', 3: 'danger', 1: 'warning' }[row.status]">
              {{ { 1: '处理中', 2: '已入库', 3: '失败' }[row.status] || row.status }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="入库时间" width="110" align="center">
          <template #default="{ row }"><span class="dim num">{{ (row.created_at || '').slice(0, 10) }}</span></template>
        </el-table-column>
        <el-table-column label="操作" width="120" fixed="right">
          <template #default="{ row }">
            <el-button size="small" link type="primary" @click="viewChunks(row)">切片预览</el-button>
            <el-button size="small" link @click="testSearch(row)">检索测试</el-button>
          </template>
        </el-table-column>
      </el-table>

      <!-- 切片预览 -->
      <el-drawer v-model="drawer" :title="`切片预览 · ${curDoc?.title || ''}`" size="46%">
        <div v-for="c in chunks" :key="c.id" class="chunk">
          <div class="c-path dim">{{ c.section_path || '（无章节路径）' }}</div>
          <div class="c-text">{{ c.content }}</div>
        </div>
        <el-empty v-if="!chunks.length" description="无切片" />
      </el-drawer>
    </div>
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { kbChunks, kbDocuments, kbEval, uploadKbDoc } from '../../api'

const items = ref([])
const total = ref(0)
const loading = ref(false)
const keyword = ref('')
const uploading = ref(false)
const evaluating = ref(false)
const evalResult = ref(null)
const chunks = ref([])
const drawer = ref(false)
const curDoc = ref(null)
const pick_ = ref({ group: 'type', key: 'ALL' })
const chunksTotal = ref(0)
const loadError = ref('')

const TYPES = ['standard', 'rule', 'faq', 'variety']
const TYPE_LABELS = { standard: '国标/行标', rule: '平台规则', faq: 'FAQ', variety: '品种产区' }
const STATUS = [
  { key: 'ALL', label: '全部' },
  { key: '2', label: '已入库' },
  { key: '1', label: '处理中' },
  { key: '3', label: '失败' },
]

const tree = ref([
  { name: '分类', key: 'type', children: [{ key: 'ALL', label: '全部', count: 0 },
    ...TYPES.map((t) => ({ key: t, label: TYPE_LABELS[t], count: 0 }))] },
  { name: '状态', key: 'status', children: STATUS.map((s) => ({ ...s, count: 0 })) },
])

function pick(group, key) {
  pick_.value = { group, key }
  load()
}

async function load() {
  loading.value = true
  try {
    const params = { size: 50, keyword: keyword.value || undefined }
    if (pick_.value.group === 'type' && pick_.value.key !== 'ALL') params.doc_type = pick_.value.key
    if (pick_.value.group === 'status' && pick_.value.key !== 'ALL') {
      params.status = Number(pick_.value.key)
    }
    const data = await kbDocuments(params)
    const list = data.items || data
    items.value = Array.isArray(list) ? list : []
    total.value = data.total ?? items.value.length
    // 树计数
    const all = await kbDocuments({ size: 100 })
    const arr = all.items || all
    const byType = {}
    const byStatus = {}
    let ck = 0
    arr.forEach((d) => {
      byType[d.doc_type] = (byType[d.doc_type] || 0) + 1
      byStatus[d.status] = (byStatus[d.status] || 0) + 1
      ck += d.chunk_count || 0
    })
    chunksTotal.value = ck
    tree.value[0].children.forEach((n) => { n.count = n.key === 'ALL' ? arr.length : (byType[n.key] || 0) })
    tree.value[1].children.forEach((n) => { n.count = n.key === 'ALL' ? arr.length : (byStatus[Number(n.key)] || 0) })
  } catch (e) {
    // 显示加载错误，便于排查
    loadError.value = (e && e.message) || String(e)
  } finally {
    loading.value = false
  }
}

function beforeUpload(file) {
  const ok = ['application/pdf', 'text/plain', 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'].includes(file.type)
    || /\.(md|markdown|txt|pdf|docx)$/i.test(file.name)
  if (!ok) ElMessage.error('仅支持 pdf / docx / md / txt')
  return ok
}

async function doUpload({ file }) {
  uploading.value = true
  try {
    const docType = pick_.value.group === 'type' && pick_.value.key !== 'ALL' ? pick_.value.key : 'standard'
    await uploadKbDoc(file, { title: file.name.replace(/\.[^.]+$/, ''), doc_type: docType })
    ElMessage.success('已上传并完成切分/向量化入库')
    load()
  } finally {
    uploading.value = false
  }
}

async function viewChunks(row) {
  curDoc.value = row
  const list = await kbChunks(row.id)
  chunks.value = (list.items || list || []).slice(0, 50)
  drawer.value = true
}

async function testSearch(row) {
  const { value } = await ElMessageBox.prompt(
    `输入测试问题，检索「${row.title}」相关内容`, '检索测试',
    { inputValue: '等级标准是什么？' },
  )
  const res = await http.post('/kb/search', { query: value, top_k: 3 })
  const hits = res.hits || []
  ElMessageBox.alert(
    hits.map((h, i) => `${i + 1}. [${h.score}] ${h.content.slice(0, 120)}…`).join('\n\n') || '无命中',
    `检索结果（${hits.length} 条）`, { customStyle: { whiteSpace: 'pre-wrap' } },
  )
}

async function runEval() {
  evaluating.value = true
  try {
    evalResult.value = await kbEval({ k: 5 })
  } finally {
    evaluating.value = false
  }
}

onMounted(load)
</script>

<style scoped>
.lr { display: grid; grid-template-columns: 230px minmax(0, 1fr); gap: 14px; align-items: start; }
.tree { padding: 14px; position: sticky; top: 12px; }
.t-head { font-weight: 700; margin-bottom: 10px; }
.t-group { margin-bottom: 12px; }
.t-lv1 { font-size: 12px; color: var(--ink-3); margin: 8px 0 4px; }
.t-node { display: flex; justify-content: space-between; align-items: center; font-size: 13px;
  padding: 6px 10px; border-radius: 6px; cursor: pointer; }
.t-node:hover { background: var(--brand-soft); }
.t-node.on { background: var(--brand); color: #fff; font-weight: 600; }
.t-node.on .cnt { color: #fff; }
.cnt { font-size: 11px; color: var(--ink-4); }
.kb-status { font-size: 11.5px; margin-top: 10px; }
.table-card { padding: 14px 16px; }
.bar { display: flex; gap: 10px; align-items: center; margin-bottom: 12px; }
.flex1 { flex: 1; }
.dim { font-size: 12px; color: var(--ink-3); }
.d-name { font-size: 13px; font-weight: 600; }
.eval-bar { margin-bottom: 12px; }
.chunk { border: 1px solid var(--line); border-radius: 8px; padding: 10px 12px; margin-bottom: 10px; }
.c-path { font-size: 11px; margin-bottom: 6px; }
.c-text { font-size: 12.5px; line-height: 1.7; white-space: pre-wrap; color: var(--ink-2); }
</style>
