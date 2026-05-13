<template>
  <div class="chat-area" ref="scrollContainer" @click="handleClick" @mouseover="handleCitationHover" @mouseout="handleCitationOut">
    <div class="chat-container">
      <div v-if="messages.length === 0" class="empty-chat">
        <h2>How can I help you today?</h2>
        <p>Type a message to start a new conversation.</p>
      </div>
      
      <div
        v-for="(msg, index) in messages"
        :key="index"
        :class="['message', msg.role]"
        :data-message-index="index"
      >
        <div class="avatar" v-if="msg.role === 'assistant'">
          <el-icon><Platform /></el-icon>
        </div>
        <div class="message-body">
          <div v-if="msg.reasoning" class="thinking-block">
            <div class="thinking-header" @click="toggleThinking(index)">
              <span class="thinking-icon">💭</span>
              <span class="thinking-label">
                {{ isThinkingInProgress(index) ? '思考中...' : '思考过程' }}
              </span>
              <el-icon class="thinking-toggle">
                <ArrowUp v-if="thinkingExpanded[index]" />
                <ArrowDown v-else />
              </el-icon>
            </div>
            <div
              v-show="thinkingExpanded[index] || isThinkingInProgress(index)"
              class="thinking-content"
            >
              {{ msg.reasoning }}
            </div>
          </div>

          <!-- Solo 模式：Agent Trace（识别需求 / 规划任务 / 调用工具 / 完成回答） -->
          <div
            v-if="hasTrace(msg)"
            class="agent-trace"
          >
            <div class="agent-trace-header" @click="toggleTrace(index)">
              <el-icon class="agent-trace-caret">
                <ArrowUp v-if="traceExpanded[index] !== false" />
                <ArrowDown v-else />
              </el-icon>
              <span class="agent-trace-title">
                {{ isAnswerInProgress(index) ? '思考中…' : '已完成回答' }}
              </span>
            </div>
            <div v-show="traceExpanded[index] !== false" class="agent-trace-body">
              <!-- intent / plan 阶段 -->
              <div
                v-for="stage in visibleStages(msg.stages)"
                :key="'s-' + stage.id"
                class="trace-item"
              >
                <div class="trace-item-head">
                  <el-icon class="trace-check" :class="{ 'is-running': stage.status === 'running' }">
                    <Check v-if="stage.status === 'done'" />
                    <Loading v-else />
                  </el-icon>
                  <span class="trace-item-title">{{ stage.title }}</span>
                </div>
                <div v-if="stage.summary" class="trace-item-body">{{ stage.summary }}</div>
              </div>

              <!-- tool 调用 -->
              <div
                v-for="tc in msg.toolCalls || []"
                :key="'t-' + tc.id"
                class="trace-item"
              >
                <div class="trace-item-head" @click="toggleToolCall(index, tc.id)">
                  <el-icon class="trace-check" :class="{ 'is-running': tc.status === 'running' }">
                    <Check v-if="tc.status === 'done'" />
                    <Loading v-else />
                  </el-icon>
                  <span class="trace-item-title">
                    {{ tc.status === 'done' ? '已调用' : '正在调用' }}
                    <code class="trace-tool-name">{{ tc.name }}</code>
                  </span>
                  <el-icon class="trace-item-caret">
                    <ArrowUp v-if="isToolExpanded(index, tc.id)" />
                    <ArrowDown v-else />
                  </el-icon>
                </div>
                <div v-show="isToolExpanded(index, tc.id)" class="trace-item-body">
                  <div v-if="tc.args && Object.keys(tc.args).length" class="trace-tool-section">
                    <div class="trace-tool-label">参数</div>
                    <pre class="trace-tool-code">{{ formatArgs(tc.args) }}</pre>
                  </div>
                  <div v-if="tc.result_preview" class="trace-tool-section">
                    <div class="trace-tool-label">结果</div>
                    <pre class="trace-tool-code">{{ tc.result_preview }}</pre>
                  </div>
                  <div v-if="!tc.result_preview && tc.status === 'running'" class="trace-tool-pending">
                    执行中…
                  </div>
                </div>
              </div>

              <!-- 完成回答标记 -->
              <div v-if="msg.content" class="trace-item">
                <div class="trace-item-head">
                  <el-icon class="trace-check" :class="{ 'is-running': isAnswerInProgress(index) }">
                    <Check v-if="!isAnswerInProgress(index)" />
                    <Loading v-else />
                  </el-icon>
                  <span class="trace-item-title">完成回答</span>
                </div>
              </div>
            </div>
          </div>

          <div
            v-if="msg.content || !hasTrace(msg)"
            class="message-content"
            v-html="renderMarkdown(msg.content)"
          ></div>
          <div
            v-else-if="!isLoading && hasTrace(msg) && !msg.content"
            class="message-content empty-answer"
          >
            模型仅输出了规划但未给出最终答案。可以点击"重新生成"重试，或切换模型。
          </div>

          <!-- 参考来源面板（按文件名去重） -->
          <div v-if="msg.refs && msg.refs.length" class="sources-panel">
            <div class="sources-title">
              <el-icon style="margin-right:4px"><Document /></el-icon>
              参考来源
            </div>
            <div
              v-for="ref in uniqueRefs(msg.refs)"
              :key="ref.source"
              class="source-item"
            >
              <span class="source-name">{{ ref.source }}</span>
            </div>
          </div>

          <!-- 推荐追问气泡（仅最后一条 assistant 消息显示） -->
          <div
            v-if="msg.recommend && msg.recommend.length && index === messages.length - 1 && !isLoading"
            class="recommend-panel"
          >
            <button
              v-for="(q, qi) in msg.recommend"
              :key="qi"
              class="recommend-bubble"
              @click.stop="sendRecommend(q)"
            >
              {{ q }}
            </button>
          </div>
        </div>
      </div>
      
      <div v-if="showRegenerate" class="regenerate-bar">
        <el-button size="small" @click="regenerate" :icon="RefreshRight" round>
          重新生成
        </el-button>
      </div>
    </div>

    <!-- 引用 Popover（事件委托定位） -->
    <div
      v-if="citationPopover.visible"
      class="citation-popover"
      :style="{ top: citationPopover.y + 'px', left: citationPopover.x + 'px' }"
      @mouseover.stop
    >
      <div class="citation-source">
        <el-icon style="flex-shrink:0"><Document /></el-icon>
        <span class="citation-source-name">{{ citationPopover.source }}</span>
      </div>
      <div class="citation-snippet">"{{ citationPopover.snippet }}"</div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, reactive, watch, nextTick } from 'vue'
import { useChatStore } from '../store/chat'
import MarkdownIt from 'markdown-it'
import hljs from 'highlight.js/lib/core'
import python from 'highlight.js/lib/languages/python'
import javascript from 'highlight.js/lib/languages/javascript'
import typescript from 'highlight.js/lib/languages/typescript'
import bash from 'highlight.js/lib/languages/bash'
import json from 'highlight.js/lib/languages/json'
import sql from 'highlight.js/lib/languages/sql'
import css from 'highlight.js/lib/languages/css'
import xml from 'highlight.js/lib/languages/xml'
import java from 'highlight.js/lib/languages/java'
import go from 'highlight.js/lib/languages/go'
import yaml from 'highlight.js/lib/languages/yaml'
import markdown from 'highlight.js/lib/languages/markdown'
import 'highlight.js/styles/vs2015.css'
import { Platform, RefreshRight, ArrowDown, ArrowUp, Document, Check, Loading } from '@element-plus/icons-vue'
import type { Message, AgentStage } from '../store/chat'

hljs.registerLanguage('python', python)
hljs.registerLanguage('javascript', javascript)
hljs.registerLanguage('js', javascript)
hljs.registerLanguage('typescript', typescript)
hljs.registerLanguage('ts', typescript)
hljs.registerLanguage('bash', bash)
hljs.registerLanguage('shell', bash)
hljs.registerLanguage('sh', bash)
hljs.registerLanguage('json', json)
hljs.registerLanguage('sql', sql)
hljs.registerLanguage('css', css)
hljs.registerLanguage('html', xml)
hljs.registerLanguage('xml', xml)
hljs.registerLanguage('java', java)
hljs.registerLanguage('go', go)
hljs.registerLanguage('yaml', yaml)
hljs.registerLanguage('yml', yaml)
hljs.registerLanguage('markdown', markdown)
hljs.registerLanguage('md', markdown)

function escapeHtml(str: string) {
  return str.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;')
}

const md = new MarkdownIt({
  linkify: true,
  typographer: true,
  breaks: true,
  highlight(str: string, lang: string) {
    const langLabel = lang || 'text'
    let highlighted: string
    if (lang && hljs.getLanguage(lang)) {
      try {
        highlighted = hljs.highlight(str, { language: lang }).value
      } catch {
        highlighted = escapeHtml(str)
      }
    } else {
      highlighted = escapeHtml(str)
    }
    return `<pre><div class="code-header"><span class="code-lang">${langLabel}</span><button class="copy-btn">复制</button></div><code class="hljs">${highlighted}</code></pre>`
  }
})

const store = useChatStore()
const messages = computed(() => store.messages)
const scrollContainer = ref<HTMLElement | null>(null)

const isLoading = computed(() => store.isLoading)

const showRegenerate = computed(() => {
  if (isLoading.value || messages.value.length === 0) return false
  return messages.value[messages.value.length - 1].role === 'assistant'
})

const thinkingExpanded = reactive<Record<number, boolean>>({})

const toggleThinking = (index: number) => {
  thinkingExpanded[index] = !thinkingExpanded[index]
}

const isThinkingInProgress = (index: number) => {
  if (!isLoading.value) return false
  if (index !== messages.value.length - 1) return false
  const msg = messages.value[index]
  return msg.role === 'assistant' && !!msg.reasoning && !msg.content
}

// ── Agent Trace（Solo 模式） ───────────────────────────────────────

// traceExpanded[index] === false 表示用户手动折叠，其它情况（undefined/true）视为展开
const traceExpanded = reactive<Record<number, boolean>>({})
const toggleTrace = (index: number) => {
  traceExpanded[index] = traceExpanded[index] === false ? true : false
}

const toolExpanded = reactive<Record<string, boolean>>({})
const toolKey = (msgIndex: number, toolId: string) => `${msgIndex}::${toolId}`
const toggleToolCall = (msgIndex: number, toolId: string) => {
  const k = toolKey(msgIndex, toolId)
  toolExpanded[k] = !toolExpanded[k]
}
const isToolExpanded = (msgIndex: number, toolId: string) => !!toolExpanded[toolKey(msgIndex, toolId)]

const hasTrace = (msg: Message) => {
  const hasStages = !!msg.stages && msg.stages.some(s => s.id === 'intent' || s.id === 'plan')
  const hasTools = !!msg.toolCalls && msg.toolCalls.length > 0
  return hasStages || hasTools
}

// 过滤掉后端发的 planner/tools 这类节点级 stage（对用户没意义），只保留 intent/plan
const visibleStages = (stages?: AgentStage[]): AgentStage[] => {
  if (!stages) return []
  const order: Record<string, number> = { intent: 0, plan: 1 }
  return stages
    .filter(s => s.id === 'intent' || s.id === 'plan')
    .slice()
    .sort((a, b) => (order[a.id] ?? 99) - (order[b.id] ?? 99))
}

const isAnswerInProgress = (index: number) => {
  if (!isLoading.value) return false
  if (index !== messages.value.length - 1) return false
  return true
}

const formatArgs = (args: Record<string, any>): string => {
  try {
    return JSON.stringify(args, null, 2)
  } catch {
    return String(args)
  }
}

const uniqueRefs = (refs: { index: number; source: string; snippet: string }[]) => {
  const seen = new Set<string>()
  return refs.filter(r => {
    if (seen.has(r.source)) return false
    seen.add(r.source)
    return true
  })
}

const renderMarkdown = (content: string) => {
  // 先将 <ref>N</ref> 转为 MarkdownIt 不会转义的占位符，再还原为 citation HTML
  const withPlaceholders = content.replace(/<ref>(\d+)<\/ref>/g, '[[REF:$1]]')
  let html = md.render(withPlaceholders)
  html = html.replace(
    /\[\[REF:(\d+)\]\]/g,
    '<sup class="citation-ref" data-ref-index="$1">[$1]</sup>'
  )
  return html
}

const regenerate = () => {
  store.regenerateResponse()
}

const sendRecommend = (question: string) => {
  store.sendMessageToApi(question)
}

const handleClick = (e: MouseEvent) => {
  const target = e.target as HTMLElement
  if (target.classList.contains('copy-btn')) {
    const codeEl = target.closest('pre')?.querySelector('code')
    if (codeEl) {
      navigator.clipboard.writeText(codeEl.textContent || '')
      target.textContent = '已复制 ✓'
      setTimeout(() => { target.textContent = '复制' }, 2000)
    }
  }
}

// ── Citation Popover ──────────────────────────────────────────────

const citationPopover = reactive({
  visible: false,
  x: 0,
  y: 0,
  source: '',
  snippet: '',
})

const handleCitationHover = (e: MouseEvent) => {
  const target = e.target as HTMLElement
  if (!target.classList.contains('citation-ref')) return

  const refIndex = parseInt(target.dataset.refIndex || '0')
  const msgEl = target.closest('[data-message-index]') as HTMLElement | null
  if (!msgEl) return
  const msgIndex = parseInt(msgEl.dataset.messageIndex || '0')
  const msg = messages.value[msgIndex]
  const ref = msg?.refs?.find(r => r.index === refIndex)
  if (!ref) return

  const rect = target.getBoundingClientRect()
  const containerRect = scrollContainer.value?.getBoundingClientRect() ?? { left: 0, top: 0 }
  citationPopover.x = Math.max(0, rect.left - containerRect.left)
  citationPopover.y = rect.top - containerRect.top - 108
  citationPopover.source = ref.source
  citationPopover.snippet = ref.snippet || '（无摘要）'
  citationPopover.visible = true
}

const handleCitationOut = (e: MouseEvent) => {
  const target = e.target as HTMLElement
  if (target.classList.contains('citation-ref')) {
    citationPopover.visible = false
  }
}

// 会话切换时清空所有消息级本地展开状态——因为这些 state 是按消息 index 存的，
// 换了消息列表后旧 index 对应到新消息上会造成莫名其妙的折叠/展开。
watch(() => store.conversationId, () => {
  for (const k of Object.keys(thinkingExpanded)) delete thinkingExpanded[+k]
  for (const k of Object.keys(traceExpanded)) delete traceExpanded[+k]
  for (const k of Object.keys(toolExpanded)) delete toolExpanded[k]
})

watch(messages, async () => {
  await nextTick()
  if (scrollContainer.value) {
    scrollContainer.value.scrollTop = scrollContainer.value.scrollHeight
  }
}, { deep: true })
</script>

<style scoped>
.chat-area {
  flex: 1;
  overflow-y: auto;
  padding: 40px 24px;
  background-color: var(--bg-primary);
}

.chat-container {
  max-width: 800px;
  margin: 0 auto;
  display: flex;
  flex-direction: column;
}

.empty-chat {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 60vh;
  color: var(--text-secondary);
  text-align: center;
  padding: 0 20px;
}

.empty-chat h2 {
  font-size: clamp(2.5rem, 5vw, 4.5rem);
  font-weight: 900;
  letter-spacing: -0.05em;
  margin-bottom: 16px;
  color: var(--text-primary);
  line-height: 1.1;
}

.empty-chat p {
  font-size: 1.2rem;
  color: var(--text-secondary);
  max-width: 600px;
}

.message {
  margin-bottom: 24px;
  display: flex;
  align-items: flex-start;
  gap: 16px;
  animation: fadeIn 0.3s ease;
}

@keyframes fadeIn {
  from { opacity: 0; transform: translateY(10px); }
  to { opacity: 1; transform: translateY(0); }
}

.message.user {
  flex-direction: row-reverse;
}

.avatar {
  width: 36px;
  height: 36px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 20px;
  flex-shrink: 0;
  background-color: var(--bg-primary);
  color: var(--accent-primary);
  box-shadow: var(--shadow-sm);
  border: 1px solid var(--border-color);
}

.message-content {
  padding: 12px 18px;
  line-height: 1.6;
  font-size: 15px;
}

.message.user .message-content {
  background-color: var(--msg-user-bg);
  color: var(--msg-user-text);
  border-radius: var(--radius-lg) var(--radius-sm) var(--radius-lg) var(--radius-lg);
}

.message.assistant .message-body {
  background-color: var(--msg-ai-bg);
  color: var(--msg-ai-text);
  border: 1px solid var(--msg-ai-border);
  border-radius: var(--radius-sm) var(--radius-lg) var(--radius-lg) var(--radius-lg);
  box-shadow: var(--shadow-sm);
}

/* ===== Markdown 基础 ===== */
:deep(p) {
  margin: 0 0 12px 0;
}
:deep(p:last-child) {
  margin-bottom: 0;
}
:deep(strong) {
  font-weight: 600;
}
:deep(em) {
  font-style: italic;
}

/* ===== 标题 ===== */
:deep(h1), :deep(h2), :deep(h3), :deep(h4), :deep(h5), :deep(h6) {
  margin: 16px 0 8px 0;
  font-weight: 600;
  line-height: 1.3;
}
:deep(h1) { font-size: 1.4em; }
:deep(h2) { font-size: 1.25em; }
:deep(h3) { font-size: 1.1em; }
:deep(h4) { font-size: 1em; }

/* ===== 代码块 ===== */
:deep(pre) {
  background-color: #1e1e1e;
  color: #d4d4d4;
  border-radius: var(--radius-md);
  overflow-x: auto;
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
  font-size: 13px;
  margin: 12px 0;
  padding: 0;
}
:deep(pre code) {
  display: block;
  padding: 16px;
  background-color: transparent;
  overflow-x: auto;
}
:deep(.code-header) {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 6px 16px;
  background-color: #2d2d2d;
  border-radius: var(--radius-md) var(--radius-md) 0 0;
  font-size: 12px;
  color: #999;
}
:deep(.code-lang) {
  text-transform: uppercase;
  letter-spacing: 0.05em;
  font-weight: 500;
}
:deep(.copy-btn) {
  background: transparent;
  border: 1px solid #555;
  color: #ccc;
  padding: 2px 10px;
  border-radius: 4px;
  cursor: pointer;
  font-size: 12px;
  transition: all 0.2s;
}
:deep(.copy-btn:hover) {
  background-color: #555;
  color: #fff;
}
:deep(.code-header + code) {
  border-radius: 0 0 var(--radius-md) var(--radius-md);
}

/* ===== 行内代码 ===== */
:deep(code) {
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
  background-color: rgba(0, 0, 0, 0.06);
  padding: 2px 6px;
  border-radius: 4px;
  font-size: 0.9em;
}

/* ===== 表格 ===== */
:deep(table) {
  width: 100%;
  border-collapse: collapse;
  margin: 12px 0;
  font-size: 14px;
  overflow-x: auto;
  display: block;
}
:deep(thead) {
  background-color: rgba(0, 0, 0, 0.06);
}
:deep(th) {
  font-weight: 600;
  text-align: left;
  padding: 10px 12px;
  border: 1px solid var(--border-color);
}
:deep(td) {
  padding: 8px 12px;
  border: 1px solid var(--border-color);
}
:deep(tr:nth-child(even)) {
  background-color: rgba(0, 0, 0, 0.02);
}

/* ===== 引用块 ===== */
:deep(blockquote) {
  border-left: 4px solid var(--accent-primary);
  margin: 12px 0;
  padding: 8px 16px;
  background-color: rgba(0, 0, 0, 0.03);
  color: var(--text-secondary);
}
:deep(blockquote p) {
  margin: 0;
}

/* ===== 列表 ===== */
:deep(ul), :deep(ol) {
  margin-top: 0;
  padding-left: 24px;
}
:deep(li) {
  margin-bottom: 4px;
}

/* ===== 分割线 ===== */
:deep(hr) {
  border: none;
  border-top: 1px solid var(--border-color);
  margin: 16px 0;
}

/* ===== 链接 ===== */
:deep(a) {
  color: var(--accent-primary);
  text-decoration: none;
}
:deep(a:hover) {
  text-decoration: underline;
}

/* ===== 图片 ===== */
:deep(img) {
  max-width: 100%;
  border-radius: var(--radius-md);
  margin: 8px 0;
}

/* ===== 思考过程区块 ===== */
.message-body {
  max-width: 80%;
  display: flex;
  flex-direction: column;
}

.thinking-block {
  border: 1px solid var(--border-color);
  border-radius: var(--radius-md);
  margin-bottom: 8px;
  overflow: hidden;
  background-color: rgba(0, 0, 0, 0.02);
}

.thinking-header {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 14px;
  cursor: pointer;
  user-select: none;
  font-size: 13px;
  color: var(--text-secondary);
  transition: background-color 0.2s;
}

.thinking-header:hover {
  background-color: rgba(0, 0, 0, 0.04);
}

.thinking-icon {
  font-size: 16px;
}

.thinking-label {
  flex: 1;
  font-weight: 500;
}

@keyframes thinkingPulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.5; }
}

.thinking-block:has(.thinking-label) .thinking-label {
  /* 思考中动画由 isThinkingInProgress 控制文案 */
}

.thinking-toggle {
  font-size: 14px;
  transition: transform 0.2s;
}

.thinking-content {
  padding: 10px 14px;
  font-size: 13px;
  line-height: 1.7;
  color: var(--text-secondary);
  border-top: 1px solid var(--border-color);
  white-space: pre-wrap;
  word-break: break-word;
  max-height: 400px;
  overflow-y: auto;
}

/* ===== Agent Trace（Solo 模式） ===== */
.agent-trace {
  border: 1px solid var(--border-color);
  border-radius: var(--radius-md);
  margin-bottom: 10px;
  background-color: rgba(0, 0, 0, 0.015);
  overflow: hidden;
}

.agent-trace-header {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 14px;
  cursor: pointer;
  user-select: none;
  font-size: 13px;
  font-weight: 600;
  color: var(--text-primary);
  transition: background-color 0.15s;
}
.agent-trace-header:hover {
  background-color: rgba(0, 0, 0, 0.04);
}
.agent-trace-caret {
  font-size: 14px;
  color: var(--text-secondary);
}
.agent-trace-title {
  flex: 1;
  letter-spacing: 0.02em;
}

.agent-trace-body {
  padding: 4px 14px 10px;
  border-top: 1px solid var(--border-color);
  position: relative;
}
.agent-trace-body::before {
  /* 左侧竖线连通各个阶段 */
  content: '';
  position: absolute;
  left: 22px;
  top: 14px;
  bottom: 14px;
  width: 1px;
  background: var(--border-color);
  pointer-events: none;
}

.trace-item {
  padding: 8px 0 8px 0;
  position: relative;
}
.trace-item + .trace-item {
  border-top: 1px dashed var(--border-color);
}

.trace-item-head {
  display: flex;
  align-items: center;
  gap: 10px;
  font-size: 13.5px;
  color: var(--text-primary);
  cursor: default;
}
.trace-item-head[class*="toggle"],
.trace-item .trace-item-head:hover .trace-item-caret {
  opacity: 1;
}

.trace-check {
  width: 18px;
  height: 18px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border-radius: 50%;
  background: var(--bg-primary);
  border: 1px solid var(--border-color);
  color: #22c55e;  /* done: 绿色对勾 */
  font-size: 12px;
  flex-shrink: 0;
  z-index: 1;
  position: relative;
}
.trace-check.is-running {
  color: var(--accent-primary);
  animation: trace-spin 1s linear infinite;
}
@keyframes trace-spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}

.trace-item-title {
  flex: 1;
  font-weight: 600;
  font-size: 13.5px;
}
.trace-tool-name {
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
  font-size: 12.5px;
  background: rgba(59, 130, 246, 0.1);
  color: var(--accent-primary);
  padding: 1px 6px;
  border-radius: 4px;
  margin-left: 4px;
  font-weight: 500;
}
.trace-item-caret {
  font-size: 13px;
  color: var(--text-secondary);
  cursor: pointer;
  opacity: 0.6;
  transition: opacity 0.15s;
}

.trace-item-body {
  margin: 6px 0 2px 28px;
  padding: 6px 10px;
  font-size: 12.5px;
  line-height: 1.6;
  color: var(--text-secondary);
  background: rgba(0, 0, 0, 0.025);
  border-left: 2px solid var(--border-color);
  border-radius: 4px;
  white-space: pre-wrap;
  word-break: break-word;
}

.trace-tool-section + .trace-tool-section {
  margin-top: 6px;
}
.trace-tool-label {
  font-size: 11px;
  font-weight: 600;
  color: var(--text-secondary);
  text-transform: uppercase;
  letter-spacing: 0.05em;
  margin-bottom: 3px;
}
.trace-tool-code {
  margin: 0;
  padding: 6px 8px;
  background: var(--bg-primary);
  border: 1px solid var(--border-color);
  border-radius: 4px;
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
  font-size: 12px;
  color: var(--text-primary);
  white-space: pre-wrap;
  word-break: break-all;
  max-height: 200px;
  overflow-y: auto;
}
.trace-tool-pending {
  font-style: italic;
  color: var(--text-secondary);
}

.message-content.empty-answer {
  font-style: italic;
  color: var(--text-secondary);
  font-size: 13px;
  opacity: 0.85;
}

/* ===== 引用角标 ===== */
:deep(.citation-ref) {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 16px;
  height: 16px;
  padding: 0 3px;
  font-size: 11px;
  font-weight: 600;
  border-radius: 4px;
  background: rgba(59, 130, 246, 0.12);
  color: var(--accent-primary);
  cursor: pointer;
  vertical-align: super;
  margin: 0 1px;
  transition: background 0.15s, color 0.15s;
  text-decoration: none;
  line-height: 16px;
  border: none;
}
:deep(.citation-ref:hover) {
  background: var(--accent-primary);
  color: #fff;
}

/* ===== 引用 Popover ===== */
.citation-popover {
  position: absolute;
  z-index: 200;
  width: 300px;
  background: var(--bg-secondary);
  border: 1px solid var(--border-color);
  border-radius: 10px;
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.15);
  padding: 12px 14px;
  pointer-events: none;
}
.citation-source {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 13px;
  font-weight: 600;
  color: var(--text-primary);
  margin-bottom: 8px;
}
.citation-source-name {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.citation-snippet {
  font-size: 12px;
  line-height: 1.6;
  color: var(--text-secondary);
  font-style: italic;
  overflow: hidden;
  display: -webkit-box;
  -webkit-line-clamp: 4;
  -webkit-box-orient: vertical;
}

/* ===== 参考来源面板 ===== */
.sources-panel {
  margin: 10px 18px 4px 18px;
  padding: 10px 12px;
  background: rgba(0, 0, 0, 0.03);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-md);
  font-size: 13px;
}
.sources-title {
  font-weight: 600;
  color: var(--text-secondary);
  font-size: 12px;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  display: flex;
  align-items: center;
  margin-bottom: 8px;
}
.source-item {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 3px 0;
  color: var(--text-secondary);
}
.source-index {
  font-weight: 600;
  color: var(--accent-primary);
  min-width: 20px;
}
.source-name {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

/* ===== 推荐追问气泡 ===== */
.recommend-panel {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  padding: 10px 18px 14px 18px;
}
.recommend-bubble {
  background: transparent;
  border: 1px dashed var(--border-color);
  border-radius: 20px;
  padding: 6px 14px;
  font-size: 13px;
  color: var(--text-secondary);
  cursor: pointer;
  transition: all 0.18s;
  text-align: left;
  line-height: 1.4;
}
.recommend-bubble:hover {
  border-style: solid;
  border-color: var(--accent-primary);
  color: var(--accent-primary);
  background: rgba(59, 130, 246, 0.06);
}

/* ===== 重新生成按钮 ===== */
.regenerate-bar {
  display: flex;
  justify-content: center;
  margin: -8px 0 16px 0;
}

.regenerate-bar .el-button {
  color: var(--text-secondary);
  border-color: var(--border-color);
  background-color: var(--bg-secondary);
  font-size: 13px;
  transition: all 0.2s;
}

.regenerate-bar .el-button:hover {
  color: var(--accent-primary);
  border-color: var(--accent-primary);
  background-color: var(--bg-tertiary);
}
</style>
