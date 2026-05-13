<script setup lang="ts">
import { ref, nextTick, onMounted, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'

const router = useRouter()

interface Msg {
  role: 'user' | 'assistant'
  content: string
  time: string
  streaming?: boolean
}

// ── 状态 ───────────────────────────────────────────
const messages = ref<Msg[]>([
  {
    role: 'user',
    content: '请介绍一下 Windows Vista 的设计风格特点。',
    time: nowTime(),
  },
  {
    role: 'assistant',
    content: 'Windows Vista 的设计风格是 "Aero"，带来了全新的视觉体验。\n\n其主要特点包括：\n\n• 半透明的动态窗口效果（Aero Glass）\n• 高光和水晶般的质感\n• 精致的图标、阴影和动画\n• 更好的视觉层次和组织\n\n这套语言让操作系统看起来更有现代、未来感。',
    time: '14:12',
  },
])
const input = ref('')
const streaming = ref(false)
const clock = ref(nowTime())
const chatBox = ref<HTMLElement | null>(null)

const sessions = [
  { name: '有朋友一封信', preview: '昨天跟你说的方案...', unread: 0, avatar: '🎭', active: true },
  { name: '翻译设计稿', preview: '请查收附件里的最终版', unread: 2, avatar: '🎨', active: false },
  { name: '周末爬山', preview: '周六上午 8 点集合', unread: 0, avatar: '🏔️', active: false },
  { name: '学习人工智能的未来', preview: 'Vista 这个设计语言放到...', unread: 5, avatar: '🤖', active: false },
  { name: '产品周会', preview: '周五下午 3 点同步进度', unread: 0, avatar: '💼', active: false },
]

const suggestions = [
  'Vista 和 Windows 7 Aero 有什么区别？',
  'Vista 发布于哪一年？',
  '介绍一下 Aero Glass 技术',
]

// ── 时间钟 ───────────────────────────────────────────
function nowTime() {
  const d = new Date()
  const hh = String(d.getHours()).padStart(2, '0')
  const mm = String(d.getMinutes()).padStart(2, '0')
  return `${hh}:${mm}`
}

let clockTimer: ReturnType<typeof setInterval> | null = null
onMounted(() => {
  clockTimer = setInterval(() => { clock.value = nowTime() }, 30_000)
  scrollToBottom()
})
onUnmounted(() => { if (clockTimer) clearInterval(clockTimer) })

// ── 发送消息 · 走项目现有 /api/chat/completions（全部开关关闭，最简聊天）──
async function sendMessage(text?: string) {
  const content = (text ?? input.value).trim()
  if (!content || streaming.value) return

  messages.value.push({ role: 'user', content, time: nowTime() })
  input.value = ''
  await nextTick()
  scrollToBottom()

  // 先记录要发给后端的消息列表（过滤掉即将 push 的 streaming assistant 占位）
  const payloadMessages = messages.value.map(m => ({ role: m.role, content: m.content }))

  messages.value.push({ role: 'assistant', content: '', time: nowTime(), streaming: true })
  // 通过索引拿 Vue 代理后的响应式引用（直接用 push 前的本地对象不会触发响应式）
  const assistantIdx = messages.value.length - 1
  streaming.value = true

  // 用于跨 chunk 清洗 XML 的累积缓冲（LLM 输出的 <content>/<recommend> 会分块到达）
  let rawAccum = ''
  const cleanAll = (raw: string) => raw
    .replace(/<\/?content>/g, '')
    .replace(/<recommend>[\s\S]*?<\/recommend>/g, '')
    .replace(/<recommend>[\s\S]*$/g, '')  // 流式中 recommend 未关闭时也隐藏
    .replace(/<ref>\d+<\/ref>/g, '')

  try {
    const resp = await fetch('http://localhost:8000/api/chat/completions', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        model: 'deepseek-chat',
        messages: payloadMessages,
        use_knowledge_base: false,
        use_reranker: false,
        use_web_search: false,
        enable_thinking: false,
      }),
    })

    if (!resp.ok || !resp.body) throw new Error(`HTTP ${resp.status}`)

    const reader = resp.body.getReader()
    const decoder = new TextDecoder()
    let buffer = ''
    while (true) {
      const { value, done } = await reader.read()
      if (done) break
      buffer += decoder.decode(value, { stream: true })
      const parts = buffer.split('\n\n')
      buffer = parts.pop() || ''
      for (const p of parts) {
        const line = p.trim()
        if (!line.startsWith('data:')) continue
        const data = line.slice(5).trim()
        if (data === '[DONE]') continue
        try {
          const evt = JSON.parse(data)
          if (evt.content) {
            rawAccum += evt.content
            // 每次 chunk 来都重跑 cleanAll（正则在单 chunk 上匹配不到跨块 XML 标签）
            messages.value[assistantIdx].content = cleanAll(rawAccum)
            await nextTick()
            scrollToBottom()
          }
        } catch { /* skip malformed */ }
      }
    }
    messages.value[assistantIdx].streaming = false
  } catch (e: any) {
    messages.value[assistantIdx].content = `⚠ 请求失败：${e?.message ?? e}\n\n（请确认 backend 已启动在 :8000）`
    messages.value[assistantIdx].streaming = false
  } finally {
    streaming.value = false
  }
}

function scrollToBottom() {
  const el = chatBox.value
  if (!el) return
  el.scrollTop = el.scrollHeight
}

function onEnter(ev: KeyboardEvent) {
  if (ev.shiftKey) return
  ev.preventDefault()
  sendMessage()
}

function closeWindow() {
  // 让"关闭窗口"真的做点什么 —— 返回首页
  router.push('/home')
}
</script>

<template>
  <div class="vista-desktop">
    <!-- 桌面 · 经典 Vista Aurora 壁纸（CSS 画） -->
    <div class="wallpaper"></div>

    <!-- 主窗口 · 整体可拖动的感觉（仅视觉） -->
    <div class="vista-window">
      <!-- 标题栏 · Aero Glass 蓝色渐变 + 窗口控件 -->
      <div class="title-bar">
        <div class="app-icon">💬</div>
        <div class="title-text">ChatGPT</div>
        <div class="title-spacer"></div>
        <button class="win-btn min" title="最小化"><span>_</span></button>
        <button class="win-btn max" title="最大化"><span>□</span></button>
        <button class="win-btn close" title="关闭" @click="closeWindow"><span>×</span></button>
      </div>

      <!-- Tab 条 · 装饰性 -->
      <div class="tab-strip">
        <button class="tab-icon active" title="对话">💬</button>
        <button class="tab-icon" title="联系人">👤</button>
        <button class="tab-icon" title="设置">⚙️</button>
        <button class="tab-icon" title="附件">📎</button>
        <button class="tab-icon" title="音乐">🎵</button>
        <div class="tab-spacer"></div>
        <div class="status-pill">
          <span class="dot"></span>
          <span>在线</span>
        </div>
      </div>

      <!-- 主体：左侧会话列表 + 右侧聊天区 -->
      <div class="main-body">
        <!-- 左侧：会话 + 联系人 -->
        <aside class="sidebar">
          <div class="sidebar-section">
            <div class="section-title">聊天</div>
            <div
              v-for="s in sessions.slice(0, 3)" :key="s.name"
              class="sidebar-item" :class="{ active: s.active }"
            >
              <span class="avatar">{{ s.avatar }}</span>
              <div class="meta">
                <div class="name">{{ s.name }}</div>
                <div class="preview">{{ s.preview }}</div>
              </div>
              <span v-if="s.unread > 0" class="badge">{{ s.unread }}</span>
            </div>
          </div>

          <div class="sidebar-section">
            <div class="section-title">最近对话</div>
            <div
              v-for="s in sessions.slice(3)" :key="s.name"
              class="sidebar-item" :class="{ active: s.active }"
            >
              <span class="avatar">{{ s.avatar }}</span>
              <div class="meta">
                <div class="name">{{ s.name }}</div>
                <div class="preview">{{ s.preview }}</div>
              </div>
              <span v-if="s.unread > 0" class="badge">{{ s.unread }}</span>
            </div>
          </div>

          <div class="sidebar-footer">
            <button class="vista-btn small">
              <span>+</span> 新建对话
            </button>
            <button class="vista-btn small">
              <span>📁</span> 我的收藏
            </button>
          </div>
        </aside>

        <!-- 右侧：聊天主区 -->
        <main class="chat-area">
          <div class="chat-header">
            <span class="chat-title">💬 Windows Vista 风格</span>
            <span class="chat-today">今天 · {{ clock }}</span>
          </div>

          <div ref="chatBox" class="chat-box">
            <transition-group name="msg" tag="div">
              <div
                v-for="(m, i) in messages" :key="i"
                :class="['msg-wrap', m.role === 'user' ? 'from-user' : 'from-bot']"
              >
                <div class="msg-head">
                  <span class="msg-name">{{ m.role === 'user' ? '我' : 'ChatGPT' }}</span>
                  <span class="msg-time">[{{ m.time }}]</span>
                </div>
                <div class="msg-bubble" v-text="m.content"></div>
                <div v-if="m.streaming" class="streaming-dot">
                  <span></span><span></span><span></span>
                </div>
              </div>
            </transition-group>
          </div>

          <div class="suggestions">
            <button
              v-for="s in suggestions" :key="s"
              class="chip" :disabled="streaming"
              @click="sendMessage(s)"
            >{{ s }}</button>
          </div>

          <div class="input-area">
            <div class="input-wrap">
              <textarea
                v-model="input"
                class="input-field"
                placeholder="请输入消息..."
                rows="2"
                @keydown.enter="onEnter"
                :disabled="streaming"
              ></textarea>
              <span class="emoji-btn">☺</span>
            </div>
            <button
              class="vista-btn primary send-btn"
              :disabled="!input.trim() || streaming"
              @click="sendMessage()"
            >
              <span class="btn-icon">▶</span>
              发送
            </button>
          </div>
        </main>
      </div>

      <!-- 状态栏（底部） -->
      <div class="status-bar">
        <span>就绪</span>
        <span class="status-spacer"></span>
        <span>{{ messages.length }} 条消息</span>
        <span class="sep">|</span>
        <span>backend :8000</span>
      </div>
    </div>

    <!-- 经典 Vista 任务栏（装饰） -->
    <div class="taskbar">
      <button class="start-btn">
        <span class="orb">⊙</span>
        <span>开始</span>
      </button>
      <div class="task-spacer"></div>
      <button class="tray-item" @click="router.push('/home')">🏠</button>
      <button class="tray-item" @click="router.push('/wiki')">📚</button>
      <div class="clock-box">
        <div class="clock-time">{{ clock }}</div>
        <div class="clock-date">2026-04-24</div>
      </div>
    </div>
  </div>
</template>

<style scoped>
/*
 * ═══════════════════════════════════════════════════════════
 * Windows Vista Aero Glass · 完全复刻
 * 核心技术：蓝色渐变 + inset 白光 + 毛玻璃 + Vista 按钮反光
 * ═══════════════════════════════════════════════════════════
 */

.vista-desktop {
  position: fixed;
  inset: 0;
  overflow: hidden;
  font-family: 'Segoe UI', 'Microsoft YaHei UI', 'Microsoft YaHei',
               -apple-system, BlinkMacSystemFont, sans-serif;
  color: #1a2d4d;
  user-select: none;
}

/* ── 经典 Vista Aurora 壁纸（纯 CSS）── */
.wallpaper {
  position: absolute;
  inset: 0;
  background:
    radial-gradient(ellipse 90% 60% at 50% 100%, rgba(50, 150, 220, 0.7), transparent 60%),
    radial-gradient(ellipse 80% 50% at 20% 20%, rgba(40, 90, 180, 0.4), transparent 65%),
    radial-gradient(ellipse 60% 40% at 80% 30%, rgba(20, 60, 140, 0.35), transparent 70%),
    linear-gradient(180deg, #0a1f42 0%, #0e2d63 40%, #1c4a91 80%, #2c6ebf 100%);
  z-index: 0;
}
.wallpaper::after {
  /* 极光流动 */
  content: '';
  position: absolute;
  inset: 0;
  background: radial-gradient(ellipse 70% 30% at 50% 50%, rgba(120, 200, 255, 0.25), transparent 70%);
  filter: blur(40px);
  animation: aurora-drift 20s ease-in-out infinite alternate;
}
@keyframes aurora-drift {
  0%   { transform: translate(-5%, -3%) scale(1); opacity: 0.7; }
  100% { transform: translate(5%, 5%)  scale(1.2); opacity: 1; }
}

/* ── 主窗口容器 ───────────────────────────── */
.vista-window {
  position: absolute;
  top: 2.5%;
  left: 50%;
  transform: translateX(-50%);
  width: 900px;
  height: calc(100% - 90px);
  max-height: 720px;
  display: flex;
  flex-direction: column;
  background: linear-gradient(180deg, rgba(234, 244, 253, 0.95), rgba(214, 230, 247, 0.92));
  border: 1px solid rgba(60, 100, 160, 0.8);
  border-radius: 8px;
  box-shadow:
    0 0 0 1px rgba(255, 255, 255, 0.5) inset,       /* 内侧白光 */
    0 30px 60px -10px rgba(10, 30, 70, 0.5),         /* 落影 */
    0 10px 30px -5px rgba(10, 30, 70, 0.3);
  overflow: hidden;
  animation: win-in 500ms cubic-bezier(0.2, 0.8, 0.2, 1.1);
}
@keyframes win-in {
  0%   { transform: translateX(-50%) scale(0.9) translateY(20px); opacity: 0; }
  100% { transform: translateX(-50%) scale(1) translateY(0); opacity: 1; }
}

/* ── 标题栏 · Vista Aero Glass 蓝色渐变 ── */
.title-bar {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 8px;
  height: 34px;
  background:
    linear-gradient(180deg,
      rgba(255, 255, 255, 0.5) 0%,
      rgba(255, 255, 255, 0.1) 40%,
      rgba(100, 160, 220, 0.2) 50%,
      rgba(70, 130, 195, 0.35) 100%),
    linear-gradient(180deg, #b0d0ea 0%, #7ba4ce 50%, #4d7cae 100%);
  border-bottom: 1px solid #3a5f8d;
  box-shadow:
    inset 0 1px 0 rgba(255, 255, 255, 0.7),
    inset 0 -1px 0 rgba(0, 0, 0, 0.15);
  position: relative;
}
.title-bar::before {
  /* 顶部反光 */
  content: '';
  position: absolute;
  top: 0; left: 0; right: 0; height: 50%;
  background: linear-gradient(180deg, rgba(255,255,255,0.4), transparent);
  pointer-events: none;
}
.app-icon {
  font-size: 16px;
  filter: drop-shadow(0 1px 1px rgba(0,0,0,0.3));
}
.title-text {
  font-size: 12px;
  font-weight: 700;
  color: #1a2d4d;
  text-shadow: 0 1px 0 rgba(255, 255, 255, 0.7);
}
.title-spacer { flex: 1; }

.win-btn {
  width: 26px;
  height: 22px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border: 1px solid rgba(60, 100, 160, 0.5);
  border-radius: 3px;
  background: linear-gradient(180deg, rgba(255,255,255,0.6) 0%, rgba(200,220,240,0.5) 100%);
  box-shadow: inset 0 1px 0 rgba(255,255,255,0.8);
  cursor: pointer;
  transition: all 120ms;
  color: #1a2d4d;
  font-size: 14px;
  line-height: 1;
  font-weight: 700;
}
.win-btn:hover {
  background: linear-gradient(180deg, rgba(255,255,255,0.9), rgba(190,220,245,0.8));
  box-shadow: inset 0 1px 0 rgba(255,255,255,1), 0 0 6px rgba(100,160,220,0.6);
}
.win-btn.close:hover {
  background: linear-gradient(180deg, #ff8b8b, #d93e3e);
  color: white;
  border-color: #a02020;
}

/* ── Tab 条 ─────────────────────────────── */
.tab-strip {
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 4px 6px;
  background: linear-gradient(180deg, #e0edf8 0%, #c5dcf0 100%);
  border-bottom: 1px solid rgba(100, 140, 190, 0.4);
  box-shadow: inset 0 1px 0 rgba(255,255,255,0.6);
  position: relative;
}
.tab-icon {
  width: 30px; height: 26px;
  border: 1px solid transparent;
  border-radius: 3px;
  background: transparent;
  font-size: 14px;
  cursor: pointer;
  transition: all 120ms;
  padding: 0;
}
.tab-icon:hover {
  background: linear-gradient(180deg, rgba(255,255,255,0.8), rgba(190,220,245,0.6));
  border-color: rgba(100,140,190,0.6);
  box-shadow: 0 0 6px rgba(100,160,220,0.4);
}
.tab-icon.active {
  background: linear-gradient(180deg, #fcfeff 0%, #dcebf7 100%);
  border-color: rgba(60,100,160,0.6);
  box-shadow:
    inset 0 1px 0 rgba(255,255,255,0.9),
    0 0 8px rgba(100,160,220,0.7);
}
.tab-spacer { flex: 1; }

.status-pill {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  padding: 2px 10px;
  border: 1px solid rgba(60, 150, 60, 0.4);
  border-radius: 10px;
  background: linear-gradient(180deg, #e8f8e0 0%, #c6e8b8 100%);
  box-shadow: inset 0 1px 0 rgba(255,255,255,0.8);
  font-size: 11px;
  color: #2d5d2d;
  font-weight: 600;
}
.status-pill .dot {
  width: 8px; height: 8px; border-radius: 50%;
  background: radial-gradient(circle at 30% 30%, #a8e87a, #3d9430);
  box-shadow: 0 0 4px rgba(80, 180, 60, 0.8);
  animation: pulse 2s ease-in-out infinite;
}
@keyframes pulse {
  0%, 100% { box-shadow: 0 0 4px rgba(80, 180, 60, 0.8); }
  50%      { box-shadow: 0 0 10px rgba(100, 220, 70, 1); }
}

/* ── 主体（左右布局）─────────────────────── */
.main-body {
  flex: 1;
  display: flex;
  min-height: 0;
  background: linear-gradient(180deg, #dde8f2 0%, #e7f0f8 100%);
}

/* 左侧栏 */
.sidebar {
  width: 230px;
  flex-shrink: 0;
  background: linear-gradient(180deg, #e8f1f9 0%, #d3e3f2 100%);
  border-right: 1px solid rgba(100, 140, 190, 0.3);
  box-shadow: inset -1px 0 0 rgba(255,255,255,0.5);
  display: flex;
  flex-direction: column;
  overflow-y: auto;
}

.sidebar-section { padding: 8px 6px; }
.section-title {
  padding: 4px 10px;
  font-size: 11px;
  color: #4a6a8e;
  font-weight: 700;
  text-shadow: 0 1px 0 rgba(255,255,255,0.6);
  border-bottom: 1px solid rgba(100, 140, 190, 0.2);
  margin-bottom: 4px;
}
.sidebar-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 7px 10px;
  border-radius: 4px;
  cursor: pointer;
  transition: all 120ms;
  position: relative;
}
.sidebar-item:hover {
  background: linear-gradient(180deg, rgba(255,255,255,0.8), rgba(200,225,245,0.6));
  box-shadow: inset 0 1px 0 rgba(255,255,255,0.8);
}
.sidebar-item.active {
  background: linear-gradient(180deg, #cbe2f5 0%, #8fbce0 100%);
  box-shadow:
    inset 0 1px 0 rgba(255,255,255,0.9),
    inset 0 -1px 0 rgba(60, 100, 160, 0.3),
    0 0 8px rgba(100, 160, 220, 0.4);
  border: 1px solid rgba(60, 100, 160, 0.4);
  padding: 6px 9px;
}
.avatar {
  width: 28px; height: 28px;
  border-radius: 50%;
  background: linear-gradient(135deg, #a8c8e8, #5e8cb8);
  display: grid; place-items: center;
  font-size: 14px;
  box-shadow: inset 0 1px 0 rgba(255,255,255,0.5), 0 1px 2px rgba(30,60,100,0.3);
  flex-shrink: 0;
}
.meta { flex: 1; min-width: 0; }
.name {
  font-size: 12px; font-weight: 600;
  color: #1a2d4d;
  overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
}
.preview {
  font-size: 11px; color: #5a7a9c;
  overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
  margin-top: 1px;
}
.badge {
  background: linear-gradient(180deg, #ff7575, #d93030);
  color: white;
  font-size: 10px;
  font-weight: 700;
  min-width: 18px;
  height: 16px;
  padding: 0 4px;
  border-radius: 8px;
  display: grid; place-items: center;
  box-shadow: inset 0 1px 0 rgba(255,255,255,0.4), 0 1px 2px rgba(100,20,20,0.4);
}

.sidebar-footer {
  margin-top: auto;
  padding: 8px;
  border-top: 1px solid rgba(100, 140, 190, 0.3);
  display: flex;
  flex-direction: column;
  gap: 6px;
}

/* ── 右侧聊天区 ─────────────────────────── */
.chat-area {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  padding: 10px 14px 12px;
  background: linear-gradient(180deg, rgba(255,255,255,0.3), rgba(220,235,248,0.2));
}
.chat-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 6px 10px;
  border-radius: 4px;
  background: linear-gradient(180deg, rgba(255,255,255,0.6), rgba(210,230,250,0.5));
  box-shadow: inset 0 1px 0 rgba(255,255,255,0.8);
  margin-bottom: 8px;
}
.chat-title { font-size: 12px; font-weight: 700; color: #1a2d4d; }
.chat-today { font-size: 11px; color: #5a7a9c; }

.chat-box {
  flex: 1;
  overflow-y: auto;
  padding: 4px 6px;
  scroll-behavior: smooth;
}

.msg-wrap {
  margin-bottom: 12px;
}
.msg-head {
  display: flex; align-items: center; gap: 6px;
  margin-bottom: 3px;
  font-size: 11px;
}
.from-user .msg-head { color: #2a5a8c; justify-content: flex-end; }
.from-bot .msg-head { color: #4a7aac; }
.msg-name { font-weight: 700; }
.msg-time { color: #8fa8c4; font-family: 'Segoe UI', monospace; }

.msg-bubble {
  max-width: 82%;
  padding: 8px 12px;
  border-radius: 4px;
  font-size: 13px;
  line-height: 1.55;
  white-space: pre-wrap;
  word-break: break-word;
  position: relative;
}
.from-user .msg-bubble {
  margin-left: auto;
  background: linear-gradient(180deg, #ffffff 0%, #eaf3fb 100%);
  border: 1px solid rgba(60, 100, 160, 0.35);
  box-shadow:
    inset 0 1px 0 rgba(255,255,255,0.9),
    0 1px 2px rgba(60, 100, 160, 0.15);
  color: #1a2d4d;
}
.from-bot .msg-bubble {
  background: linear-gradient(180deg, #f5fafe 0%, #dbe9f6 100%);
  border: 1px solid rgba(100, 140, 190, 0.4);
  box-shadow:
    inset 0 1px 0 rgba(255,255,255,0.95),
    0 1px 3px rgba(60, 100, 160, 0.2);
  color: #1a2d4d;
}

/* 流式"..."指示 */
.streaming-dot {
  display: inline-flex; gap: 3px;
  margin-top: 4px; padding-left: 8px;
}
.streaming-dot span {
  width: 6px; height: 6px; border-radius: 50%;
  background: #6a9ac7;
  animation: blink 1.2s ease-in-out infinite;
}
.streaming-dot span:nth-child(2) { animation-delay: 0.2s; }
.streaming-dot span:nth-child(3) { animation-delay: 0.4s; }
@keyframes blink {
  0%, 80%, 100% { opacity: 0.3; transform: scale(0.8); }
  40%           { opacity: 1;   transform: scale(1.2); }
}

/* 消息入场动画 */
.msg-enter-active {
  transition: all 300ms cubic-bezier(0.2, 0.8, 0.2, 1);
}
.msg-enter-from {
  opacity: 0;
  transform: translateY(10px) scale(0.98);
}

/* ── 推荐追问 chips ────────────────────────── */
.suggestions {
  display: flex; gap: 6px; flex-wrap: wrap;
  padding: 6px 4px 0;
}
.chip {
  padding: 4px 10px;
  font-size: 11px;
  border-radius: 12px;
  border: 1px solid rgba(100, 140, 190, 0.5);
  background: linear-gradient(180deg, rgba(255,255,255,0.9), rgba(220,235,250,0.7));
  box-shadow: inset 0 1px 0 rgba(255,255,255,0.9);
  cursor: pointer;
  color: #2a5a8c;
  transition: all 120ms;
}
.chip:hover:not(:disabled) {
  background: linear-gradient(180deg, #ffffff, #d0e5f8);
  box-shadow: inset 0 1px 0 rgba(255,255,255,1), 0 0 6px rgba(100,160,220,0.6);
}
.chip:disabled { opacity: 0.5; cursor: not-allowed; }

/* ── 输入区 ─────────────────────────────── */
.input-area {
  display: flex;
  gap: 8px;
  padding: 10px 4px 0;
  align-items: stretch;
}
.input-wrap {
  flex: 1;
  position: relative;
  background: white;
  border: 1px solid rgba(100, 140, 190, 0.6);
  border-radius: 4px;
  box-shadow:
    inset 0 1px 3px rgba(60, 100, 160, 0.15),
    inset 0 0 0 1px rgba(255,255,255,0.5);
  transition: box-shadow 150ms;
}
.input-wrap:focus-within {
  border-color: rgba(60, 100, 160, 0.8);
  box-shadow:
    inset 0 1px 3px rgba(60, 100, 160, 0.15),
    0 0 0 2px rgba(100, 160, 220, 0.35);
}
.input-field {
  width: 100%;
  padding: 8px 32px 8px 10px;
  border: none;
  background: transparent;
  resize: none;
  font-family: inherit;
  font-size: 13px;
  color: #1a2d4d;
  outline: none;
}
.input-field::placeholder { color: #8fa8c4; }
.emoji-btn {
  position: absolute;
  right: 8px;
  bottom: 4px;
  font-size: 16px;
  color: #6a9ac7;
  cursor: pointer;
  user-select: none;
}

/* ── Vista 经典按钮（反光 · inset 高光 · hover glow）── */
.vista-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  padding: 5px 16px;
  min-height: 26px;
  font-size: 12px;
  font-weight: 600;
  color: #1a2d4d;
  border: 1px solid rgba(60, 100, 160, 0.65);
  border-radius: 3px;
  background:
    linear-gradient(180deg,
      rgba(255, 255, 255, 0.9) 0%,
      rgba(225, 235, 248, 0.8) 50%,
      rgba(175, 200, 225, 0.85) 51%,
      rgba(195, 215, 235, 0.9) 100%);
  box-shadow:
    inset 0 1px 0 rgba(255,255,255,0.95),
    inset 0 -1px 0 rgba(60,100,160,0.25),
    0 1px 2px rgba(30,60,100,0.15);
  cursor: pointer;
  transition: all 150ms;
  font-family: inherit;
}
.vista-btn:hover:not(:disabled) {
  background:
    linear-gradient(180deg,
      rgba(255, 255, 255, 1) 0%,
      rgba(240, 248, 255, 0.95) 50%,
      rgba(180, 215, 245, 0.95) 51%,
      rgba(200, 225, 245, 1) 100%);
  box-shadow:
    inset 0 1px 0 rgba(255,255,255,1),
    inset 0 -1px 0 rgba(60,100,160,0.35),
    0 0 8px rgba(100, 170, 230, 0.8),
    0 1px 2px rgba(30,60,100,0.2);
}
.vista-btn:active:not(:disabled) {
  box-shadow:
    inset 0 2px 3px rgba(60,100,160,0.25),
    inset 0 0 0 1px rgba(60,100,160,0.4);
}
.vista-btn:disabled { opacity: 0.45; cursor: not-allowed; }

.vista-btn.primary {
  color: white;
  border-color: #2a5a9e;
  background:
    linear-gradient(180deg,
      rgba(150, 200, 250, 0.95) 0%,
      rgba(90, 150, 220, 1) 50%,
      rgba(40, 95, 170, 1) 51%,
      rgba(60, 110, 185, 1) 100%);
  text-shadow: 0 1px 1px rgba(0,0,0,0.35);
  box-shadow:
    inset 0 1px 0 rgba(255,255,255,0.5),
    inset 0 -1px 0 rgba(0,0,0,0.2),
    0 1px 3px rgba(30,60,100,0.3);
}
.vista-btn.primary:hover:not(:disabled) {
  background:
    linear-gradient(180deg,
      rgba(170, 215, 255, 1) 0%,
      rgba(110, 170, 235, 1) 50%,
      rgba(50, 110, 190, 1) 51%,
      rgba(80, 135, 210, 1) 100%);
  box-shadow:
    inset 0 1px 0 rgba(255,255,255,0.6),
    inset 0 -1px 0 rgba(0,0,0,0.2),
    0 0 12px rgba(100, 170, 230, 0.9);
}

.vista-btn.small { padding: 3px 10px; font-size: 11px; min-height: 22px; }

.send-btn {
  padding: 5px 22px;
  min-width: 80px;
}
.btn-icon { font-size: 10px; }

/* ── 状态栏 ─────────────────────────────── */
.status-bar {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 3px 10px;
  font-size: 11px;
  color: #4a6a8e;
  background: linear-gradient(180deg, #d8e5f2 0%, #b6ccdf 100%);
  border-top: 1px solid rgba(100, 140, 190, 0.4);
  box-shadow: inset 0 1px 0 rgba(255,255,255,0.7);
  height: 22px;
}
.status-spacer { flex: 1; }
.sep { color: rgba(100, 140, 190, 0.6); }

/* ═══════════════════════════════════════════════════════════
 * Vista 任务栏（装饰）
 * ═══════════════════════════════════════════════════════════ */
.taskbar {
  position: absolute;
  bottom: 0; left: 0; right: 0;
  height: 40px;
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 0 6px 0 0;
  background:
    linear-gradient(180deg,
      rgba(255, 255, 255, 0.2) 0%,
      rgba(140, 180, 230, 0.35) 30%,
      rgba(50, 100, 170, 0.55) 70%,
      rgba(20, 50, 110, 0.75) 100%);
  backdrop-filter: blur(20px) saturate(150%);
  -webkit-backdrop-filter: blur(20px) saturate(150%);
  border-top: 1px solid rgba(255, 255, 255, 0.4);
  box-shadow:
    inset 0 1px 0 rgba(255,255,255,0.3),
    inset 0 -1px 0 rgba(0,0,0,0.3);
  z-index: 10;
}

.start-btn {
  display: inline-flex; align-items: center; gap: 6px;
  height: 32px; padding: 0 14px 0 10px;
  background:
    radial-gradient(circle at 30% 40%, rgba(255,255,255,0.8), transparent 60%),
    linear-gradient(180deg, #6ab04c 0%, #2a7810 40%, #1e5a06 100%);
  border: none;
  border-radius: 20px;
  color: white;
  font-weight: 700;
  font-size: 13px;
  cursor: pointer;
  text-shadow: 0 1px 1px rgba(0,0,0,0.4);
  box-shadow:
    inset 0 1px 0 rgba(255,255,255,0.5),
    inset 0 -1px 0 rgba(0,0,0,0.3),
    0 2px 4px rgba(0,0,0,0.3);
  transition: all 150ms;
}
.start-btn:hover {
  filter: brightness(1.15);
  box-shadow:
    inset 0 1px 0 rgba(255,255,255,0.6),
    inset 0 -1px 0 rgba(0,0,0,0.3),
    0 0 12px rgba(120, 220, 80, 0.7);
}
.orb { font-size: 14px; }

.task-spacer { flex: 1; }

.tray-item {
  width: 28px; height: 28px;
  border: 1px solid transparent;
  border-radius: 3px;
  background: rgba(255, 255, 255, 0.05);
  font-size: 15px;
  cursor: pointer;
  transition: all 120ms;
}
.tray-item:hover {
  background: rgba(255, 255, 255, 0.2);
  border-color: rgba(255,255,255,0.4);
  box-shadow: 0 0 6px rgba(255,255,255,0.3);
}

.clock-box {
  display: flex; flex-direction: column; align-items: flex-end;
  margin-left: 8px; padding: 0 10px 0 8px;
  height: 32px; justify-content: center;
  border-left: 1px solid rgba(255,255,255,0.2);
  color: white;
  text-shadow: 0 1px 1px rgba(0,0,0,0.5);
  font-size: 11px;
  line-height: 1.3;
}
.clock-time { font-weight: 700; }
.clock-date { font-size: 10px; opacity: 0.85; }

/* ── 滚动条（Vista 细滑风格）── */
.chat-box::-webkit-scrollbar, .sidebar::-webkit-scrollbar {
  width: 14px;
}
.chat-box::-webkit-scrollbar-thumb, .sidebar::-webkit-scrollbar-thumb {
  background: linear-gradient(90deg, #c5dcf0, #95b5d0);
  border: 1px solid rgba(80, 120, 170, 0.5);
  border-radius: 7px;
  box-shadow: inset 0 1px 0 rgba(255,255,255,0.6);
}
.chat-box::-webkit-scrollbar-thumb:hover, .sidebar::-webkit-scrollbar-thumb:hover {
  background: linear-gradient(90deg, #d5e8f8, #7ba4c8);
}
.chat-box::-webkit-scrollbar-track, .sidebar::-webkit-scrollbar-track {
  background: #e8f0f7;
}

/* ── 小屏适配 ─────────────────────────── */
@media (max-width: 960px) {
  .vista-window { width: 96%; height: calc(100% - 70px); }
  .sidebar { width: 180px; }
}
@media (max-width: 700px) {
  .sidebar { display: none; }
}
</style>
