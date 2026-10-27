<template>
  <div class="page chat-page">
    <div class="chat card">
      <div class="side">
        <div class="s-head">问 AI</div>
        <div class="s-sub">标准 / 行情 / 选品 · 答案附引用来源</div>
        <div v-for="s in samples" :key="s" class="sample" @click="ask(s)">{{ s }}</div>
      </div>

      <div class="main">
        <div class="msgs" ref="msgsEl">
          <div v-for="(m, i) in msgs" :key="i" class="msg" :class="m.role">
            <!-- 执行过程：只在 AI 回答上显示，随流式事件实时刷新 -->
            <div v-if="m.role === 'ai' && m.flow?.length" class="flow" :class="{ done: !m.running }">
              <div class="f-head" @click="m.collapsed = !m.collapsed">
                <span class="f-title">
                  执行过程
                  <template v-if="m.running"><span class="dots"></span></template>
                  <template v-else>· {{ m.flow.length }} 步 · {{ fmtMs(m.elapsed) }}</template>
                </span>
                <span class="f-toggle">{{ m.collapsed ? '展开' : '收起' }}</span>
              </div>
              <template v-if="!m.collapsed">
                <div v-for="(s, si) in m.flow" :key="si" class="f-step" :class="s.status">
                  <span class="f-ico">
                    <span v-if="s.status === 'running'" class="spin"></span>
                    <span v-else class="tick">✓</span>
                  </span>
                  <span class="f-name">{{ s.order }}. {{ s.title }}</span>
                  <span v-if="s.elapsed_ms != null" class="f-ms num">{{ fmtMs(s.elapsed_ms) }}</span>
                  <span v-else-if="s.status === 'running'" class="f-ms running-txt">进行中</span>
                  <div v-if="s.detail" class="f-detail">{{ s.detail }}</div>
                  <div v-for="(t, ti) in (s.extra?.tools || [])" :key="ti" class="f-tool"
                       :class="{ fail: !t.ok }">
                    <span class="t-ico">{{ t.ok ? '✓' : '✕' }}</span>
                    <b>{{ t.tool }}</b> · {{ t.summary }}
                  </div>
                </div>
              </template>
            </div>

            <div v-if="m.html || m.role === 'user'" class="bubble">
              <div v-if="m.role === 'ai'" class="answer" v-html="m.html"></div>
              <template v-else>{{ m.text }}</template>
            </div>
            <div v-if="m.citations?.length" class="cites">
              <span class="cite" v-for="(c, j) in m.citations" :key="j"
                    :title="c.text?.slice(0, 120)">[{{ c.no }}] {{ c.title || c.doc_title || '知识条目' }}</span>
            </div>
          </div>
        </div>
        <div class="input">
          <el-input v-model="text" size="large" placeholder="例如：特优和特级差在哪？中宁枸杞现在什么价？"
                    @keyup.enter="send" :disabled="pending" />
          <el-button type="primary" size="large" :loading="pending" @click="send">发送</el-button>
        </div>
        <div class="foot-note">AI 回答仅供参考，不构成交易依据；等级判定与价格以平台规则与人工审核为准</div>
      </div>

      <!-- 右：引用来源 + Agent 轨迹 -->
      <div class="ref">
        <div class="r-sec">
          <div class="r-head">引用来源</div>
          <div v-if="last?.citations?.length" class="r-cites">
            <div v-for="c in last.citations" :key="c.no" class="r-cite">
              <div class="r-cite-t">[{{ c.no }}] {{ c.title }}</div>
              <div class="r-cite-x">{{ (c.text || '').slice(0, 90) }}…</div>
            </div>
          </div>
          <div v-else class="dim r-empty">提问后，引用的标准条款将显示在这里</div>
        </div>
        <div class="r-sec" v-if="last?.steps?.length">
          <div class="r-head">Agent 轨迹</div>
          <div class="r-steps">
            <div v-for="(s, i) in last.steps" :key="i" class="r-step">
              <span class="r-dot"></span>{{ s }}
            </div>
          </div>
          <div class="r-meta dim" v-if="last.intent">
            意图 {{ last.intent }} · 工具 {{ (last.tools_used || []).join('、') || '无' }}
            <template v-if="last.elapsed_ms"> · {{ last.elapsed_ms }}ms</template>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, nextTick, onMounted, reactive, ref } from 'vue'
import { useRoute } from 'vue-router'
import { kbAskStream } from '../../api'

const route = useRoute()

const samples = [
  '特优和特级差在哪？',
  '霉变率超多少不能上架？',
  '现在中宁宁杞5号什么价？',
  '280粒和220粒怎么选？',
]
const msgs = ref([
  { role: 'ai', html: '你好！我是杞市智能问答，可以查<b>分级标准</b>、<b>行情价格</b>、<b>选品建议</b>。回答会附引用来源。' },
])
const text = ref('')
const pending = ref(false)
const msgsEl = ref(null)
// 右栏展示最近一条 AI 回答的引用与 Agent 轨迹
const last = computed(() => [...msgs.value].reverse().find((m) => m.role === 'ai' && (m.citations?.length || m.steps?.length)) || {})

function esc(s) {
  return s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
}

function render(md) {
  // 极简 markdown：换行 + [n] 引用标红
  return esc(md)
    .replace(/\[(\d+)\]/g, '<sup class="cite-mark">[$1]</sup>')
    .replace(/\*\*(.+?)\*\*/g, '<b>$1</b>')
    .replace(/\n/g, '<br>')
}

async function scrollBottom() {
  await nextTick()
  msgsEl.value?.scrollTo({ top: msgsEl.value.scrollHeight, behavior: 'smooth' })
}

async function ask(q) {
  if (pending.value) return
  text.value = q
  await send()
}

async function send() {
  const q = text.value.trim()
  if (!q || pending.value) return
  text.value = ''
  msgs.value.push({ role: 'user', text: q })
  pending.value = true

  // AI 消息先占位：流程会随 SSE 事件逐条填充，用户不用干等
  const msg = reactive({
    role: 'ai',
    html: '',
    citations: [],
    steps: [],
    flow: [],
    running: true,
    collapsed: false,
    intent: '',
    tools_used: [],
    elapsed_ms: 0,
  })
  msgs.value.push(msg)
  scrollBottom()

  try {
    await kbAskStream(q, (event, data) => {
      if (event === 'step') {
        const idx = msg.flow.findIndex((s) => s.node === data.node)
        if (idx >= 0) {
          // 同一节点从 running 变 done：原地更新，不重复堆叠
          Object.assign(msg.flow[idx], data)
        } else {
          msg.flow.push({ ...data })
        }
        scrollBottom()
      } else if (event === 'done') {
        msg.html = render(data.answer || '（无回答）')
        msg.citations = data.citations || []
        msg.steps = data.steps || []
        msg.intent = data.intent
        msg.tools_used = data.tools_used || []
        msg.elapsed_ms = data.elapsed_ms
        msg.running = false
        scrollBottom()
      } else if (event === 'error') {
        msg.html = `抱歉，问答服务暂时不可用：${data.message || '未知错误'}`
        msg.running = false
      }
    })
  } catch (e) {
    msg.html = `抱歉，问答服务暂时不可用（${e.message || e}）`
    msg.running = false
  } finally {
    pending.value = false
    scrollBottom()
  }
}

onMounted(() => {
  // /chat?q=xxx 直接发起提问，便于分享结论与自动化验证
  const q = String(route.query.q || '').trim()
  if (q) ask(q)
})

onMounted(() => {
  // /chat?q=xxx 直接发起提问，便于分享结论与自动化验证
  const q = String(route.query.q || '').trim()
  if (q) ask(q)
})

function fmtMs(ms) {
  if (ms == null) return ''
  return ms >= 1000 ? `${(ms / 1000).toFixed(1)}s` : `${ms}ms`
}
</script>

<style scoped>
.chat-page { display: flex; justify-content: center; }
.chat { width: min(1280px, 100%); height: min(680px, calc(100vh - 150px)); margin: 20px auto;
  display: grid; grid-template-columns: 230px minmax(0, 1fr) 290px; overflow: hidden; }
.side { border-right: 1px solid var(--line); padding: 18px 16px; background: #fff; }
.s-head { font-weight: 800; font-size: 16px; }
.s-sub { font-size: 11.5px; color: var(--ink-3); margin: 6px 0 16px; }
.sample { font-size: 12.5px; background: #fff; border: 1px solid var(--brand-line); color: var(--ink-2);
  border-radius: 8px; padding: 8px 10px; margin-bottom: 8px; cursor: pointer; transition: all .15s; }
.sample:hover { border-color: var(--brand); color: var(--brand); }
.main { display: flex; flex-direction: column; min-height: 0; background: var(--bg); }
.msgs { flex: 1; overflow-y: auto; padding: 18px 22px; }
.msg { display: flex; flex-direction: column; margin-bottom: 14px; }
.msg.user { align-items: flex-end; }
.bubble { max-width: 78%; background: #fff; border: 1px solid var(--line); border-radius: 10px;
  padding: 10px 14px; font-size: 13.5px; line-height: 1.75; }
.msg.user .bubble { background: var(--brand); color: #fff; border-color: var(--brand); }
.answer :deep(.cite-mark) { color: var(--brand); font-weight: 700; }
.cites { max-width: 78%; display: flex; flex-wrap: wrap; gap: 6px; margin-top: 6px; }
.cite { font-size: 11px; color: var(--ink-3); background: #fff; border: 1px solid var(--line);
  border-radius: 4px; padding: 2px 6px; cursor: default; }
.flow { width: 100%; max-width: 100%; background: #fff; border: 1px solid var(--line);
  border-radius: 10px; padding: 10px 12px; margin-bottom: 8px; }
.flow.done { background: #fcfaf9; }
.f-head { display: flex; justify-content: space-between; align-items: center; cursor: pointer; }
.f-title { font-size: 12px; font-weight: 700; color: var(--ink-2); }
.f-toggle { font-size: 11px; color: var(--ink-4); }
.f-step { display: grid; grid-template-columns: 16px auto 1fr; gap: 6px 4px;
  padding: 6px 0 2px; border-top: 1px dashed var(--line); margin-top: 6px; }
.f-step.running .f-name { color: var(--brand); font-weight: 600; }
.f-ico { display: flex; align-items: center; justify-content: center; height: 18px; }
.tick { color: #1d8a4e; font-size: 12px; font-weight: 700; }
.spin { width: 10px; height: 10px; border: 2px solid var(--brand-line); border-top-color: var(--brand);
  border-radius: 50%; animation: spin .7s linear infinite; display: inline-block; }
@keyframes spin { to { transform: rotate(360deg); } }
.f-name { font-size: 12px; color: var(--ink-1); grid-column: 2; }
.f-ms { font-size: 11px; color: var(--ink-4); grid-column: 3; text-align: right; }
.running-txt { color: var(--brand); }
.f-detail { grid-column: 2 / 4; font-size: 11.5px; color: var(--ink-3); line-height: 1.6;
  word-break: break-all; }
.f-tool { grid-column: 2 / 4; font-size: 11px; color: var(--ink-2); background: #fff;
  border: 1px solid var(--line); border-radius: 6px; padding: 4px 8px; margin-top: 4px; }
.f-tool.fail { border-color: #f0c9c2; background: #fdf4f2; color: var(--brand); }
.t-ico { color: #1d8a4e; margin-right: 4px; }
.f-tool.fail .t-ico { color: var(--brand); }
.dots::after { content: "…"; animation: blink 1s infinite; }
@keyframes blink { 50% { opacity: .2; } }
.input { display: flex; gap: 10px; padding: 12px 18px; background: #fff; border-top: 1px solid var(--line); }
.foot-note { text-align: center; font-size: 11px; color: var(--ink-4); padding: 6px 0 10px; background: #fff; }
.ref { border-left: 1px solid var(--line); background: #fff; overflow-y: auto; padding: 16px 14px; }
.r-sec { margin-bottom: 18px; }
.r-head { font-weight: 700; font-size: 13px; margin-bottom: 10px; padding-left: 9px; position: relative; }
.r-head::before { content: ""; position: absolute; left: 0; top: .3em; width: 6px; height: 6px;
  border-radius: 50% 50% 46% 46% / 58% 58% 42% 42%; background: var(--brand); }
.r-cite { border: 1px solid var(--line); border-radius: 8px; padding: 8px 10px; margin-bottom: 8px; }
.r-cite-t { font-size: 12px; font-weight: 600; color: var(--brand); margin-bottom: 4px; }
.r-cite-x { font-size: 11.5px; color: var(--ink-3); line-height: 1.6; }
.r-empty { font-size: 12px; line-height: 1.7; }
.r-steps { display: flex; flex-direction: column; gap: 6px; }
.r-step { font-size: 11.5px; color: var(--ink-2); display: flex; align-items: baseline; gap: 6px; line-height: 1.5; }
.r-dot { width: 5px; height: 5px; border-radius: 50%; background: var(--brand); flex: none; transform: translateY(-2px); }
.r-meta { font-size: 11px; margin-top: 8px; }
</style>
