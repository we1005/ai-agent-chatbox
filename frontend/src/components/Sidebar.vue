<template>
  <div class="sidebar">
    <div class="sidebar-header">
      <el-button type="primary" @click="createNewChat" class="new-chat-btn" :icon="Plus">
        New Chat
      </el-button>
      <el-input 
        v-model="searchQuery" 
        placeholder="Search conversations..." 
        :prefix-icon="Search" 
        clearable 
        class="search-input"
      />
    </div>
    
    <div class="sidebar-title" v-if="filteredConversations.length > 0">Recent</div>
    
    <div class="history-list">
      <router-link to="/home" class="admin-entry">
        <span class="admin-icon">🏠</span>
        <span>首页 · 玄鉴</span>
      </router-link>
      <router-link to="/admin" class="admin-entry">
        <span class="admin-icon">⚙</span>
        <span>后台管理</span>
      </router-link>
      <router-link to="/wiki" class="admin-entry">
        <span class="admin-icon">📚</span>
        <span>项目 Wiki</span>
      </router-link>
      <router-link to="/vista-chat" class="admin-entry">
        <span class="admin-icon">🪟</span>
        <span>Vista 主题</span>
      </router-link>

      <div
        v-for="result in filteredConversations"
        :key="result.conv.id"
        :class="['history-item', { active: result.conv.id === currentConversationId }]"
        @click="loadConversation(result.conv.id)"
      >
        <el-icon class="item-icon"><ChatDotRound /></el-icon>
        <div class="title-wrap">
          <!-- 标题：命中字符高亮（v-html 安全：preview 由 buildHighlight 转义后注入 <mark>） -->
          <span class="title" v-html="result.titleHtml"></span>
          <!-- 命中正文片段（仅当查询命中消息正文且不在标题里时显示） -->
          <span v-if="result.snippetHtml" class="snippet" v-html="result.snippetHtml"></span>
        </div>
        <el-button
          :icon="Delete"
          circle
          size="small"
          class="delete-btn"
          @click.stop="deleteConversation(result.conv.id)"
        />
      </div>

      <div v-if="filteredConversations.length === 0 && searchQuery" class="empty-state">
        No results found for "{{ searchQuery }}"
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import Fuse from 'fuse.js'
import { useChatStore } from '../store/chat'
import type { Conversation } from '../store/chat'
import { Search, Delete, Plus, ChatDotRound } from '@element-plus/icons-vue'

const store = useChatStore()
const searchQuery = ref('')

const currentConversationId = computed(() => store.conversationId)
const conversations = computed(() => store.conversations)

/**
 * Fuse.js 模糊搜索器：标题权重 2、消息正文权重 1。
 * keys 用 deep path "messages.content"（自动遍历 messages 数组的 content 字段）。
 * threshold 0.4 = 中等模糊（"deeseek" 也能匹配 "deepseek"）。
 */
const fuse = computed(() => new Fuse(conversations.value, {
  keys: [
    { name: 'title', weight: 2 },
    { name: 'messages.content', weight: 1 },
  ],
  threshold: 0.4,
  ignoreLocation: true,
  minMatchCharLength: 2,
  includeMatches: true,
}))

interface SearchResult {
  conv: Conversation
  titleHtml: string
  snippetHtml: string
}

/** HTML 转义（防 XSS：用户输入内容里可能有 <script>） */
function escape(s: string): string {
  return s.replace(/[&<>"']/g, c => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;',
  }[c]!))
}

/**
 * 把 Fuse 返回的 indices [[start,end], ...] 应用到字符串上：
 * 转义后包 <mark>。
 * 过滤掉 length < 3 的零碎子序列段（Fuse 字符级模糊会把 "nt"/"ning" 这种
 * 噪音也标命中，视觉上很脏；3 字符以上才算"有意义命中"）。
 */
function highlight(text: string, indices: readonly (readonly [number, number])[]): string {
  if (!indices.length) return escape(text)
  const significant = indices.filter(([s, e]) => e - s + 1 >= 3)
  if (!significant.length) return escape(text)
  let out = ''
  let last = 0
  const sorted = [...significant].sort((a, b) => a[0] - b[0])
  for (const [start, end] of sorted) {
    if (start < last) continue   // 重叠段跳过
    out += escape(text.slice(last, start))
    out += '<mark>' + escape(text.slice(start, end + 1)) + '</mark>'
    last = end + 1
  }
  out += escape(text.slice(last))
  return out
}

/** 从命中消息正文里截取一段含命中点的短片段（前后各 ~30 字符） */
function buildSnippet(content: string, indices: readonly (readonly [number, number])[]): string {
  if (!indices.length) return ''
  const first = indices[0]
  const winStart = Math.max(0, first[0] - 30)
  const winEnd = Math.min(content.length, first[1] + 30)
  // 把全局 indices 偏移到窗口坐标
  const localIndices = indices
    .filter(([s, e]) => s >= winStart && e < winEnd)
    .map(([s, e]) => [s - winStart, e - winStart] as const)
  let snippet = content.slice(winStart, winEnd)
  let html = highlight(snippet, localIndices)
  if (winStart > 0) html = '…' + html
  if (winEnd < content.length) html = html + '…'
  return html
}

const filteredConversations = computed<SearchResult[]>(() => {
  if (!searchQuery.value.trim()) {
    return conversations.value.map(conv => ({
      conv,
      titleHtml: escape(conv.title),
      snippetHtml: '',
    }))
  }
  const results = fuse.value.search(searchQuery.value)
  return results.map(r => {
    const conv = r.item
    const titleMatch = r.matches?.find(m => m.key === 'title')
    const msgMatch = r.matches?.find(m => m.key === 'messages.content')
    const titleHtml = titleMatch
      ? highlight(conv.title, titleMatch.indices)
      : escape(conv.title)
    const snippetHtml = msgMatch && msgMatch.value
      ? buildSnippet(msgMatch.value, msgMatch.indices)
      : ''
    return { conv, titleHtml, snippetHtml }
  })
})

const createNewChat = () => {
  store.clearMessages()
}

const loadConversation = async (id: string) => {
  await store.loadConversation(id)
}

const deleteConversation = async (id: string) => {
  if (confirm('Are you sure you want to delete this conversation?')) {
    await store.deleteConversation(id)
  }
}

onMounted(() => {
  store.fetchConversations()
})
</script>

<style scoped>
.sidebar {
  height: 100vh;
  background-color: var(--bg-secondary);
  border-right: 1px solid var(--border-color);
  display: flex;
  flex-direction: column;
}

.sidebar-header {
  padding: 20px 16px 10px;
}

.new-chat-btn {
  width: 100%;
  margin-bottom: 16px;
  border-radius: var(--radius-md);
  font-weight: 600;
  font-size: 15px;
  height: 44px;
  background-color: var(--accent-primary);
  border: none;
  transition: all 0.2s ease;
}

.new-chat-btn:hover {
  background-color: var(--accent-secondary);
  transform: translateY(-1px);
  box-shadow: var(--shadow-sm);
}

.search-input :deep(.el-input__wrapper) {
  border-radius: var(--radius-md);
  background-color: var(--bg-tertiary);
  box-shadow: none;
  border: 1px solid transparent;
  transition: all 0.2s;
}

.search-input :deep(.el-input__wrapper:hover),
.search-input :deep(.el-input__wrapper.is-focus) {
  background-color: var(--bg-secondary);
  box-shadow: 0 0 0 1px var(--accent-primary) inset;
}

.sidebar-title {
  font-size: 12px;
  font-weight: 600;
  color: var(--text-tertiary);
  text-transform: uppercase;
  letter-spacing: 0.05em;
  padding: 10px 20px;
}

.history-list {
  flex: 1;
  overflow-y: auto;
  padding: 0 12px 20px;
  font-size: 15px;
}

.history-item {
  padding: 10px 16px;
  color: var(--text-secondary);
  font-size: 15px;
  cursor: pointer;
  border-radius: var(--radius-md);
  display: flex;
  align-items: flex-start;        /* 顶对齐：title + snippet 双行时图标对齐第一行 */
  margin-bottom: 4px;
  transition: all 0.2s ease;
  position: relative;
}

.item-icon {
  margin-right: 12px;
  font-size: 17px;
  opacity: 0.7;
  margin-top: 3px;                /* 微调：与 title 第一行视觉对齐 */
  flex-shrink: 0;
}

.title-wrap {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 2px;
  margin-right: 10px;
}

.snippet {
  font-size: 11.5px;
  color: var(--text-tertiary);
  line-height: 1.4;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

/* Fuse 命中字符高亮 —— mark 默认黄底太刺眼，改成柔和琥珀色 */
.title :deep(mark),
.snippet :deep(mark) {
  background: rgba(249, 115, 22, 0.18);
  color: var(--accent-primary, #c2410c);
  border-radius: 2px;
  padding: 0 1px;
  font-weight: 600;
}

.history-item:hover {
  background-color: var(--bg-tertiary);
  color: var(--text-primary);
}

.history-item.active {
  background-color: var(--accent-light);
  color: var(--accent-primary);
  font-weight: 500;
}

.history-item.active .item-icon {
  opacity: 1;
}

.title {
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  display: block;
}

.delete-btn {
  opacity: 0;
  transition: opacity 0.2s;
  background: transparent;
  border: none;
  position: absolute;
  right: 8px;
}

.delete-btn:hover {
  background-color: rgba(245, 108, 108, 0.1);
  color: #f56c6c;
}

.history-item:hover .delete-btn {
  opacity: 1;
}

.empty-state {
  text-align: center;
  color: var(--text-tertiary);
  font-size: 13px;
  padding: 20px 0;
}

.admin-entry {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 16px;
  margin: 0 0 8px 0;
  border-radius: var(--radius-md);
  color: var(--text-secondary);
  font-size: 14px;
  font-weight: 600;
  text-decoration: none;
  transition: all 0.2s;
  border: 1px dashed var(--border-color);
}
.admin-entry:hover {
  background: var(--bg-tertiary);
  color: var(--accent-primary);
  border-color: var(--accent-primary);
}
.admin-icon {
  font-size: 15px;
}
</style>
