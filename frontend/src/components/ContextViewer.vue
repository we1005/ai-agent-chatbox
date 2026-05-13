<template>
  <el-drawer
    v-model="visible"
    title="上下文视图"
    size="440px"
    direction="rtl"
    :with-header="true"
  >
    <template #header>
      <div class="viewer-header">
        <strong>Context Engine · View</strong>
        <span class="meta">{{ conversationId?.slice(-8) || '—' }}</span>
      </div>
    </template>

    <div v-if="loading" class="loading">加载中…</div>

    <div v-else-if="!viewData" class="empty">
      未获取到上下文——选中会话后再打开本面板。
    </div>

    <template v-else>
      <!-- Rolling Summary -->
      <section class="panel-section">
        <h3>Rolling Summary</h3>
        <div v-if="viewData.rolling_summary" class="summary-card">
          <div class="summary-meta">
            覆盖到 turn {{ viewData.rolling_summary.turn_id }} ·
            压缩了 {{ viewData.rolling_summary.covered_event_count ?? '—' }} 个 events
          </div>
          <div class="summary-content">{{ viewData.rolling_summary.content }}</div>
        </div>
        <div v-else class="hint">本会话还未生成 summary（需要 20 轮以上触发摘要）</div>
      </section>

      <!-- Memory Hits -->
      <section class="panel-section">
        <h3>Memory Hits <span class="count">({{ viewData.memory_hits.length }})</span></h3>
        <ul v-if="viewData.memory_hits.length > 0" class="memory-list">
          <li v-for="m in viewData.memory_hits" :key="m.id">
            <el-tag size="small" :type="kindTagType(m.kind)">{{ m.kind }}</el-tag>
            <span class="mem-text">{{ m.object }}</span>
          </li>
        </ul>
        <div v-else class="hint">本会话无相关的 durable memory 记录</div>
      </section>

      <!-- Recent Events -->
      <section class="panel-section">
        <h3>Recent Events <span class="count">({{ viewData.events_recent.length }} / {{ viewData.events_total }})</span></h3>
        <ol class="event-list">
          <li v-for="e in viewData.events_recent" :key="e.id" :class="kindClass(e.kind)">
            <span class="event-kind">{{ e.kind }}</span>
            <span class="event-turn">turn {{ e.turn_id }}</span>
            <span class="event-preview">{{ e.content_preview }}</span>
            <span v-if="e.content_length > 200" class="event-trunc">
              …（共 {{ e.content_length }} 字符）
            </span>
          </li>
        </ol>
      </section>

      <footer class="panel-footer">
        <el-button size="small" @click="refresh">刷新</el-button>
        <router-link to="/settings/memory" class="deep-link">去 memory 审计页 →</router-link>
      </footer>
    </template>
  </el-drawer>
</template>

<script setup lang="ts">
import { ref, watch } from 'vue'

interface EventPreview {
  id: string
  turn_id: number
  kind: string
  role: string | null
  content_preview: string
  content_length: number
  created_at: string | null
  metadata_keys: string[]
}

interface MemoryHit {
  id: string
  kind: string
  object: string
  valid_at: string | null
}

interface ViewData {
  conversation_id: string
  events_recent: EventPreview[]
  events_total: number
  rolling_summary: {
    content: string | null
    turn_id: number | null
    covered_event_count: number | null
  } | null
  memory_hits: MemoryHit[]
}

const props = defineProps<{
  modelValue: boolean
  conversationId: string | null
}>()

const emit = defineEmits<{
  (e: 'update:modelValue', v: boolean): void
}>()

const visible = ref(props.modelValue)
const loading = ref(false)
const viewData = ref<ViewData | null>(null)

watch(() => props.modelValue, (v) => { visible.value = v })
watch(visible, (v) => {
  emit('update:modelValue', v)
  if (v) refresh()
})

const refresh = async () => {
  if (!props.conversationId) {
    viewData.value = null
    return
  }
  loading.value = true
  try {
    const res = await fetch(`http://localhost:8000/api/conversations/${props.conversationId}/context-view`)
    if (res.ok) {
      viewData.value = await res.json()
    } else {
      viewData.value = null
    }
  } catch (e) {
    console.error('[context-viewer]', e)
    viewData.value = null
  } finally {
    loading.value = false
  }
}

const kindTagType = (kind: string): ('' | 'success' | 'warning' | 'info' | 'danger') => {
  const map: Record<string, 'success' | 'warning' | 'info' | 'danger'> = {
    user_preference: 'success',
    project_fact: 'warning',
    task_progress: 'info',
    general: '',
  } as any
  return map[kind] || ''
}

const kindClass = (kind: string) => ({
  'event-user': kind === 'user_msg',
  'event-assistant': kind === 'assistant_msg',
  'event-summary': kind === 'summary',
  'event-memory-flush': kind === 'memory_flush',
  'event-tool': kind === 'tool_call' || kind === 'tool_result',
})
</script>

<style scoped>
.viewer-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}
.meta {
  font-family: ui-monospace, 'SF Mono', monospace;
  font-size: 12px;
  color: var(--text-secondary, #999);
}
.loading, .empty, .hint {
  color: var(--text-secondary, #999);
  font-size: 13px;
  padding: 12px 0;
}
.panel-section {
  margin-bottom: 20px;
}
.panel-section h3 {
  font-size: 14px;
  margin: 0 0 10px 0;
  color: var(--text-primary, #333);
}
.count {
  color: var(--text-secondary, #999);
  font-weight: normal;
  font-size: 12px;
}
.summary-card {
  background: var(--bg-tertiary, #f5f5f5);
  padding: 10px;
  border-radius: 6px;
  font-size: 13px;
}
.summary-meta {
  font-size: 11px;
  color: var(--text-secondary, #999);
  margin-bottom: 6px;
}
.summary-content {
  line-height: 1.5;
}
.memory-list {
  list-style: none;
  padding: 0;
  margin: 0;
}
.memory-list li {
  display: flex;
  gap: 8px;
  padding: 6px 0;
  border-bottom: 1px dashed var(--border-color, #eee);
  font-size: 13px;
  align-items: flex-start;
}
.memory-list li:last-child { border-bottom: none; }
.mem-text { flex: 1; }
.event-list {
  list-style: none;
  padding: 0;
  margin: 0;
  font-size: 12px;
  font-family: ui-monospace, 'SF Mono', monospace;
}
.event-list li {
  display: grid;
  grid-template-columns: 90px 50px 1fr;
  gap: 8px;
  padding: 4px 0;
  border-bottom: 1px dashed var(--border-color, #eee);
}
.event-kind { color: var(--accent-primary, #409eff); }
.event-turn { color: var(--text-secondary, #999); }
.event-preview {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.event-trunc {
  grid-column: 1 / -1;
  color: var(--text-secondary, #999);
  font-size: 11px;
}
.event-user { background: #f8fafe; }
.event-assistant { background: #fafafe; }
.event-summary { background: #fffbe6; }
.event-memory-flush { background: #f0f9ff; color: #666; }
.panel-footer {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding-top: 16px;
  border-top: 1px solid var(--border-color, #eee);
  margin-top: 16px;
}
.deep-link {
  font-size: 12px;
  color: var(--accent-primary, #409eff);
  text-decoration: none;
}
</style>
