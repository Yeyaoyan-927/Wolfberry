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
        <el-button type="primary" @click="openUpload">
          <el-icon style="margin-right:4px"><UploadFilled /></el-icon>上传文档
        </el-button>
        <span class="dim num">共 {{ total }} 篇</span>
        <span class="flex1"></span>
        <el-button size="small" plain @click="runEval" :loading="evaluating">检索效果评估</el-button>
      </div>

      <el-alert v-if="evalResult" type="success" :closable="true" class="eval-bar"
                :title="`评测完成：${evalResult.cases} 题，Recall@5 = ${evalResult.recall_at_k}，MRR = ${evalResult.mrr}`" />

      <el-alert v-if="loadError" type="error" :closable="false" class="eval-bar"
                :title="`加载失败：${loadError}`" />

      <el-table :data="items" v-loading="loading" :header-cell-style="{ background: '#faf6f3' }">
        <el-table-column label="文档" min-width="230">
          <template #default="{ row }">
            <div class="d-name">{{ row.title }}</div>
            <div class="dim num">{{ row.file_name }}</div>
          </template>
        </el-table-column>
        <el-table-column prop="doc_type" label="分类" width="88" />
        <el-table-column label="切分参数" width="132">
          <template #default="{ row }">
            <span class="dim num">{{ stratLabel(row.chunk_strategy) }} · {{ row.chunk_size }}/{{ row.chunk_overlap }}</span>
          </template>
        </el-table-column>
        <el-table-column label="分块" width="62" align="right">
          <template #default="{ row }"><span class="num">{{ row.chunk_count }}</span></template>
        </el-table-column>
        <el-table-column label="状态" width="86" align="center">
          <template #default="{ row }">
            <span class="st" :class="`st-${row.status}`">
              {{ { 1: '处理中', 2: '已入库', 3: '失败' }[row.status] || row.status }}
            </span>
          </template>
        </el-table-column>
        <el-table-column label="入库时间" width="104" align="center">
          <template #default="{ row }"><span class="dim num">{{ (row.created_at || '').slice(0, 10) }}</span></template>
        </el-table-column>
        <el-table-column label="操作" width="196" fixed="right">
          <template #default="{ row }">
            <el-button size="small" link type="primary" @click="viewChunks(row)">切片</el-button>
            <el-button size="small" link @click="testSearch(row)">测试</el-button>
            <el-button size="small" link @click="openRechunk(row)">重切</el-button>
            <el-button size="small" link type="danger" @click="removeDoc(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
    </div>

    <!-- 上传：试切分 → 确认入库 -->
    <el-dialog v-model="upDialog" title="上传文档" width="880px" top="6vh" @closed="resetUpload">
      <div class="up-row">
        <el-upload :show-file-list="false" accept=".pdf,.docx,.md,.txt,.markdown"
                   :before-upload="pickFile" :auto-upload="false" drag class="up-drop">
          <el-icon size="30"><UploadFilled /></el-icon>
          <div class="up-text">{{ upFile ? upFile.name : '拖拽或点击选择文件（pdf / docx / md / txt）' }}</div>
          <div class="dim">{{ upFile ? `${(upFile.size / 1024).toFixed(0)} KB，可重新选择` : '选好文件后先试切分，确认效果再入库' }}</div>
        </el-upload>
      </div>

      <el-form :inline="true" class="up-form" label-width="76px">
        <el-form-item label="分类">
          <el-select v-model="upForm.doc_type" style="width: 132px">
            <el-option v-for="t in TYPES" :key="t" :label="TYPE_LABELS[t]" :value="t" />
          </el-select>
        </el-form-item>
        <el-form-item label="切分策略">
          <el-select v-model="upForm.chunk_strategy" style="width: 150px">
            <el-option v-for="s in STRATEGIES" :key="s.value" :label="s.label" :value="s.value" />
          </el-select>
        </el-form-item>
        <el-form-item label="块长">
          <el-input-number v-model="upForm.chunk_size" :min="120" :max="4000" :step="100" style="width: 130px" />
        </el-form-item>
        <el-form-item label="重叠">
          <el-input-number v-model="upForm.chunk_overlap" :min="0" :max="500" :step="20" style="width: 110px" />
        </el-form-item>
      </el-form>

      <div class="up-actions">
        <el-button :loading="previewing" :disabled="!upFile" @click="doPreview">试切分</el-button>
        <span class="dim">试切分只解析+切分，不写库；确认切片效果后再入库</span>
      </div>

      <!-- 质量报告 -->
      <div v-if="preview" class="report">
        <div class="r-head">
          <b>切分质量报告</b>
          <span class="dim num">
            实际策略 {{ stratLabel(preview.strategy) }} · {{ preview.chunk_count }} 片 ·
            平均 {{ preview.report.avg_len }} 字（{{ preview.report.min_len }}~{{ preview.report.max_len }}）
          </span>
        </div>
        <div class="r-metrics">
          <div class="rm"><b class="num">{{ preview.report.count }}</b><span>切片数</span></div>
          <div class="rm"><b class="num">{{ preview.report.avg_len }}</b><span>平均字数</span></div>
          <div class="rm" :class="{ warn: preview.report.short_ratio > 0.3 }">
            <b class="num">{{ (preview.report.short_ratio * 100).toFixed(0) }}%</b><span>过短块占比</span>
          </div>
          <div class="rm" :class="{ warn: preview.report.with_section_ratio < 0.5 }">
            <b class="num">{{ (preview.report.with_section_ratio * 100).toFixed(0) }}%</b><span>带章节路径</span>
          </div>
        </div>
        <ul class="advice">
          <li v-for="(a, i) in preview.report.advice" :key="i">{{ a }}</li>
        </ul>

        <div class="c-list">
          <div v-for="c in preview.chunks.slice(0, 12)" :key="c.no" class="chunk">
            <div class="c-path dim">
              #{{ c.no + 1 }} · {{ c.section_path || '（无章节路径）' }} · {{ c.char_count }} 字
            </div>
            <div class="c-text">{{ c.text }}</div>
          </div>
          <div v-if="preview.chunk_count > 12" class="dim more">
            仅展示前 12 片，共 {{ preview.chunk_count }} 片{{ preview.truncated ? '（接口按 200 片截断）' : '' }}
          </div>
        </div>
      </div>

      <template #footer>
        <el-button @click="upDialog = false">取消</el-button>
        <el-button type="primary" :loading="uploading" :disabled="!upFile" @click="doUpload">
          {{ preview ? '按此参数入库' : '直接入库' }}
        </el-button>
      </template>
    </el-dialog>

    <!-- 重切 -->
    <el-dialog v-model="rechunkDialog" :title="`重新切分 · ${curDoc?.title || ''}`" width="480px">
      <el-alert type="info" :closable="false" class="eval-bar"
                title="重切会重新解析原始文件、清空旧切片并重新向量化；已入库的旧切片不会残留。" />
      <el-form label-width="88px">
        <el-form-item label="切分策略">
          <el-select v-model="rechunkForm.chunk_strategy" style="width: 180px">
            <el-option v-for="s in STRATEGIES" :key="s.value" :label="s.label" :value="s.value" />
          </el-select>
        </el-form-item>
        <el-form-item label="块长">
          <el-input-number v-model="rechunkForm.chunk_size" :min="120" :max="4000" :step="100" />
          <span class="dim" style="margin-left:8px">当前 {{ curDoc?.chunk_size }}</span>
        </el-form-item>
        <el-form-item label="重叠">
          <el-input-number v-model="rechunkForm.chunk_overlap" :min="0" :max="500" :step="20" />
          <span class="dim" style="margin-left:8px">当前 {{ curDoc?.chunk_overlap }}</span>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="rechunkDialog = false">取消</el-button>
        <el-button type="primary" :loading="rechunking" @click="submitRechunk">开始重切</el-button>
      </template>
    </el-dialog>

    <!-- 切片详情 -->
    <el-drawer v-model="drawer" :title="`切片详情 · ${curDoc?.title || ''}`" size="52%">
      <div v-if="curDoc" class="ch-meta">
        <div class="cm-row">
          <span class="cm-k">切分策略</span>
          <span class="cm-v">{{ stratLabel(chunkDoc.chunk_strategy || curDoc.chunk_strategy) }}</span>
          <span class="cm-k">块长 / 重叠</span>
          <span class="cm-v num">{{ chunkDoc.chunk_size || curDoc.chunk_size }} / {{ chunkDoc.chunk_overlap ?? curDoc.chunk_overlap }}</span>
        </div>
        <div class="cm-row">
          <span class="cm-k">切片数</span>
          <span class="cm-v num">{{ stats.count }}</span>
          <span class="cm-k">长度分布</span>
          <span class="cm-v num">
            {{ stats.min_len }} ~ {{ stats.max_len }} 字（平均 {{ stats.avg_len }}）
          </span>
          <span class="cm-k">原文</span>
          <span class="cm-v num">{{ chunkDoc.char_count || curDoc.char_count }} 字</span>
        </div>
      </div>

      <div class="ch-tools">
        <el-input v-model="chunkKeyword" placeholder="按切片正文或章节路径过滤" clearable
                  style="width: 260px" @keyup.enter="loadChunks" @clear="loadChunks" />
        <el-button size="small" @click="loadChunks">过滤</el-button>
        <span class="dim num">共 {{ chunkTotal }} 条{{ chunkTotal > chunks.length ? `，当前显示 ${chunks.length} 条` : '' }}</span>
      </div>

      <div v-for="c in chunks" :key="c.id" class="chunk">
        <div class="c-head">
          <span class="c-no num">#{{ c.chunk_no + 1 }}</span>
          <span class="c-path">{{ c.section_path || '（无章节路径）' }}</span>
          <span class="c-tags num">
            {{ c.char_count }} 字 · {{ c.embedding_provider || '—' }} {{ c.embedding_dim }}d
          </span>
        </div>
        <div v-if="c.context && c.context !== c.section_path" class="c-ctx dim">
          上下文：{{ c.context }}
        </div>
        <div class="c-text" :class="{ clamp: !expanded[c.id] && c.content.length > 260 }">{{ c.content }}</div>
        <el-button v-if="c.content.length > 260" link size="small" type="primary" class="c-more"
                   @click="expanded[c.id] = !expanded[c.id]">
          {{ expanded[c.id] ? '收起' : '展开全文' }}
        </el-button>
        <div class="c-act">
          <el-button link size="small" @click="copyChunk(c)">复制正文</el-button>
          <el-button link size="small" @click="probeChunk(c)">用它测召回</el-button>
        </div>
      </div>
      <el-empty v-if="!chunks.length" description="无切片（可能仅切分失败或已被过滤）" />

      <div v-if="chunkTotal > chunks.length" class="ch-more">
        <el-button size="small" :loading="chunkLoading" @click="loadMoreChunks">加载更多</el-button>
      </div>
    </el-drawer>
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { http, kbChunks, kbDelete, kbDocuments, kbEval, kbPreview, kbRechunk, uploadKbDoc } from '../../api'

const items = ref([])
const total = ref(0)
const loading = ref(false)
const keyword = ref('')
const evaluating = ref(false)
const evalResult = ref(null)
const chunks = ref([])
const drawer = ref(false)
const curDoc = ref(null)
const chunkDoc = ref({})
const stats = ref({ count: 0, avg_len: 0, min_len: 0, max_len: 0 })
const chunkKeyword = ref('')
const chunkPage = ref(1)
const chunkTotal = ref(0)
const chunkLoading = ref(false)
const expanded = ref({})
const pick_ = ref({ group: 'type', key: 'ALL' })
const chunksTotal = ref(0)
const loadError = ref('')
const route = useRoute()

// 上传
const upDialog = ref(false)
const upFile = ref(null)
const uploading = ref(false)
const previewing = ref(false)
const preview = ref(null)
const upForm = ref({ doc_type: 'standard', chunk_strategy: 'auto', chunk_size: 500, chunk_overlap: 80 })

// 重切
const rechunkDialog = ref(false)
const rechunking = ref(false)
const rechunkForm = ref({ chunk_strategy: 'auto', chunk_size: 500, chunk_overlap: 80 })

const TYPES = ['standard', 'rule', 'faq', 'variety']
const TYPE_LABELS = { standard: '国标/行标', rule: '平台规则', faq: 'FAQ', variety: '品种产区', other: '其他' }
const STRATEGIES = [
  { value: 'auto', label: 'auto（自动探测）' },
  { value: 'md', label: 'md（按标题层级）' },
  { value: 'clause', label: 'clause（按条款）' },
  { value: 'recursive', label: 'recursive（按段落）' },
  { value: 'qa', label: 'qa（按问答对）' },
]
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

function stratLabel(v) {
  return ({ auto: '自动', md: '标题', clause: '条款', recursive: '段落', qa: '问答' }[v] || v || '—')
}

function pick(group, key) {
  pick_.value = { group, key }
  load()
}

async function load() {
  loading.value = true
  loadError.value = ''
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

    // 树计数（后端 size 上限 100）
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
    loadError.value = (e && e.message) || String(e)
  } finally {
    loading.value = false
  }
}

// ---------- 上传流程 ----------
function openUpload() {
  resetUpload()
  upForm.value.doc_type = pick_.value.group === 'type' && pick_.value.key !== 'ALL' ? pick_.value.key : 'standard'
  upDialog.value = true
}

function resetUpload() {
  upFile.value = null
  preview.value = null
  previewing.value = false
  uploading.value = false
}

function pickFile(file) {
  const ok = /\.(md|markdown|txt|pdf|docx)$/i.test(file.name)
  if (!ok) {
    ElMessage.error('仅支持 pdf / docx / md / txt')
    return false
  }
  if (file.size > 20 * 1024 * 1024) {
    ElMessage.error('文件超过 20MB')
    return false
  }
  upFile.value = file
  preview.value = null
  return false   // 阻止自动上传，走手动入库
}

async function doPreview() {
  if (!upFile.value) return
  previewing.value = true
  try {
    preview.value = await kbPreview(upFile.value, upForm.value)
  } finally {
    previewing.value = false
  }
}

async function doUpload() {
  if (!upFile.value) return
  uploading.value = true
  try {
    const doc = await uploadKbDoc(upFile.value, {
      title: upFile.value.name.replace(/\.[^.]+$/, ''),
      ...upForm.value,
    })
    if (doc.status === 3) {
      ElMessage.error(`入库失败：${doc.error_msg || '未知原因'}`)
    } else {
      ElMessage.success(`已入库：${doc.chunk_count} 片，策略 ${stratLabel(doc.chunk_strategy)}`)
      upDialog.value = false
      load()
    }
  } finally {
    uploading.value = false
  }
}

// ---------- 文档操作 ----------
async function viewChunks(row) {
  curDoc.value = row
  chunkKeyword.value = ''
  expanded.value = {}
  chunkPage.value = 1
  chunks.value = []
  drawer.value = true
  await loadChunks(true)
}

async function loadChunks(reset = true) {
  if (!curDoc.value) return
  chunkLoading.value = true
  try {
    const data = await kbChunks(curDoc.value.id, {
      page: chunkPage.value,
      size: 50,
      keyword: chunkKeyword.value || undefined,
    })
    chunkDoc.value = data.doc || {}
    stats.value = data.stats || { count: 0, avg_len: 0, min_len: 0, max_len: 0 }
    chunkTotal.value = data.total ?? (data.items || []).length
    const list = data.items || []
    chunks.value = reset ? list : [...chunks.value, ...list]
  } finally {
    chunkLoading.value = false
  }
}

async function loadMoreChunks() {
  chunkPage.value += 1
  await loadChunks(false)
}

async function copyChunk(c) {
  try {
    await navigator.clipboard.writeText(c.content)
    ElMessage.success('已复制')
  } catch {
    ElMessage.warning('浏览器不允许剪贴板，请手动选择复制')
  }
}

/** 用该切片的首句作为查询，验证它自己能否被召回（自召回是切片可用性的底线） */
async function probeChunk(c) {
  const query = (c.section_path || c.content).slice(0, 40)
  const res = await http.post('/kb/search', { query, top_k: 5 })
  const hits = res.hits || []
  const self = hits.find((h) => h.chunk_id === c.id)
  ElMessageBox.alert(
    (self
      ? `✅ 本条切片被召回，排名第 ${hits.indexOf(self) + 1}，相似度 ${self.score}\n\n`
      : '⚠️ 本条切片未被召回（说明它与其他内容区分度低，或切分粒度过碎）\n\n')
    + hits.map((h, i) => `${i + 1}. [${h.score}] ${h.section_path || '（无路径）'}\n${h.content.slice(0, 90)}…`).join('\n\n'),
    `召回测试 · 查询「${query}」`,
    { customStyle: { whiteSpace: 'pre-wrap' } },
  )
}

async function testSearch(row) {
  const { value } = await ElMessageBox.prompt(
    `输入测试问题，检索「${row.title}」相关内容`, '检索测试',
    { inputValue: '等级标准是什么？' },
  )
  const res = await http.post('/kb/search', { query: value, top_k: 3 })
  const hits = res.hits || []
  ElMessageBox.alert(
    hits.map((h, i) => `${i + 1}. [${h.score}] ${h.section_path || ''}\n${h.content.slice(0, 140)}…`).join('\n\n') || '无命中',
    `检索结果（${hits.length} 条）`, { customStyle: { whiteSpace: 'pre-wrap' } },
  )
}

function openRechunk(row) {
  curDoc.value = row
  rechunkForm.value = {
    chunk_strategy: row.chunk_strategy || 'auto',
    chunk_size: row.chunk_size || 500,
    chunk_overlap: row.chunk_overlap ?? 80,
  }
  rechunkDialog.value = true
}

async function submitRechunk() {
  if (!curDoc.value) return
  rechunking.value = true
  try {
    const r = await kbRechunk(curDoc.value.id, rechunkForm.value)
    ElMessage.success(`重切完成：${r.chunks} 片（策略 ${stratLabel(r.strategy)}）`)
    rechunkDialog.value = false
    load()
  } finally {
    rechunking.value = false
  }
}

async function removeDoc(row) {
  await ElMessageBox.confirm(
    `删除「${row.title}」将同时移除其 ${row.chunk_count} 个切片与向量，不可恢复。确定删除？`,
    '删除文档', { type: 'warning', confirmButtonText: '删除', confirmButtonClass: 'el-button--danger' },
  )
  await kbDelete(row.id)
  ElMessage.success('已删除')
  load()
}

async function runEval() {
  evaluating.value = true
  try {
    evalResult.value = await kbEval({ k: 5 })
  } finally {
    evaluating.value = false
  }
}

onMounted(async () => {
  await load()
  // 支持深链：/admin/kb?doc=12 直接打开该文档的切片详情（便于分享排查链接）
  const docId = Number(route.query.doc || 0)
  if (docId) {
    const hit = items.value.find((d) => d.id === docId)
      || (await kbDocuments({ size: 100 })).items?.find((d) => d.id === docId)
    if (hit) viewChunks(hit)
  }
})
</script>

<style scoped>
.lr { display: grid; grid-template-columns: 220px minmax(0, 1fr); gap: 14px; align-items: start; }
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
.st { display: inline-block; font-size: 12px; line-height: 18px; padding: 1px 7px; border-radius: 4px;
  border: 1px solid transparent; white-space: nowrap; font-weight: 600; }
.st-2 { color: #1d8a4e; background: #e5f6ec; border-color: #bce5cc; }
.st-1 { color: #b07205; background: #fdf3dd; border-color: #efd9a7; }
.st-3 { color: var(--brand); background: var(--brand-soft); border-color: var(--brand-line); }
.chunk { border: 1px solid var(--line); border-radius: 8px; padding: 10px 12px; margin-bottom: 10px; }
.c-path { font-size: 11px; margin-bottom: 6px; }
.c-text { font-size: 12.5px; line-height: 1.7; white-space: pre-wrap; color: var(--ink-2); }

/* 切片详情 */
.ch-meta { background: #fdfaf8; border: 1px solid var(--line); border-radius: 8px;
  padding: 10px 12px; margin-bottom: 12px; }
.cm-row { display: flex; gap: 10px; align-items: baseline; font-size: 12.5px; padding: 3px 0; flex-wrap: wrap; }
.cm-k { color: var(--ink-4); }
.cm-v { color: var(--ink-1); font-weight: 600; margin-right: 10px; }
.ch-tools { display: flex; gap: 8px; align-items: center; margin-bottom: 12px; }
.c-head { display: flex; gap: 8px; align-items: baseline; margin-bottom: 6px; }
.c-no { font-size: 11px; color: #fff; background: var(--brand); border-radius: 4px;
  padding: 1px 6px; font-weight: 700; flex: none; }
.c-head .c-path { font-size: 12px; color: var(--ink-2); font-weight: 600; margin: 0; flex: 1;
  overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.c-tags { font-size: 11px; color: var(--ink-4); flex: none; }
.c-ctx { font-size: 11.5px; color: var(--ink-3); margin-bottom: 6px; }
.c-text.clamp { display: -webkit-box; -webkit-line-clamp: 5; -webkit-box-orient: vertical; overflow: hidden; }
.c-more { padding: 2px 0 0; }
.c-act { margin-top: 6px; display: flex; gap: 4px; }
.ch-more { text-align: center; padding: 8px 0; }

/* 上传对话框 */
.up-drop { width: 100%; }
.up-drop :deep(.el-upload) { width: 100%; }
.up-drop :deep(.el-upload-dragger) { padding: 18px; width: 100%; }
.up-text { font-size: 13px; margin: 6px 0 4px; }
.up-form { margin-top: 14px; }
.up-actions { display: flex; align-items: center; gap: 12px; margin-bottom: 12px; }
.report { border: 1px solid var(--line); border-radius: 10px; padding: 12px 14px; background: #fdfaf8; }
.r-head { display: flex; justify-content: space-between; align-items: baseline; margin-bottom: 10px; }
.r-metrics { display: grid; grid-template-columns: repeat(4, 1fr); gap: 8px; margin-bottom: 10px; }
.rm { background: #fff; border: 1px solid var(--line); border-radius: 8px; padding: 8px 10px; text-align: center; }
.rm b { display: block; font-size: 17px; color: var(--brand); }
.rm span { font-size: 11px; color: var(--ink-3); }
.rm.warn b { color: #b07205; }
.rm.warn { border-color: #efd9a7; background: #fdf9ee; }
.advice { margin: 0 0 12px; padding-left: 18px; font-size: 12.5px; color: var(--ink-2); line-height: 1.8; }
.c-list { max-height: 260px; overflow-y: auto; }
.more { text-align: center; padding: 6px 0; }
</style>
