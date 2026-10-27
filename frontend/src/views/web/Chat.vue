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
            <div class="bubble">
              <div v-if="m.role === 'ai'" class="answer" v-html="m.html"></div>
              <template v-else>{{ m.text }}</template>
            </div>
            <div v-if="m.citations?.length" class="cites">
              <span class="cite" v-for="(c, j) in m.citations" :key="j"
                    :title="c.text?.slice(0, 120)">[{{ c.no }}] {{ c.title || c.doc_title || '知识条目' }}</span>
            </div>
          </div>
          <div v-if="pending" class="msg ai"><div class="bubble typing">AI 正在检索知识与数据<span class="dots"></span></div></div>
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
import { computed, nextTick, ref } from 'vue'
import { kbAsk } from '../../api'

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
  scrollBottom()
  try {
    const data = await kbAsk(q)
    msgs.value.push({
      role: 'ai',
      html: render(data.answer || '（无回答）'),
      citations: data.citations || [],
      steps: data.steps || [],
      intent: data.intent,
      tools_used: data.tools_used || [],
      elapsed_ms: data.elapsed_ms,
    })
  } catch {
    msgs.value.push({ role: 'ai', html: '抱歉，问答服务暂时不可用，请稍后重试。' })
  } finally {
    pending.value = false
    scrollBottom()
  }
}
</script>

<style scoped>
.chat-page { display: flex; justify-content: center; }
.chat { width: min(1280px, 100%); height: min(680px, calc(100vh - 150px)); margin: 20px auto;
  display: grid; grid-template-columns: 230px minmax(0, 1fr) 290px; overflow: hidden; }
.side { border-right: 1px solid var(--line); padding: 18px 16px; background: linear-gradient(180deg, #fff, var(--brand-soft)); }
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
.typing::after { content: ""; }
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
