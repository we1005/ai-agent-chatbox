<template>
  <div class="memory-audit">
    <header class="page-header">
      <div>
        <h2>长期记忆审计</h2>
        <p class="sub">
          Context Engine v2 · P3.4 · durable memory 列表。
          这些事实由 mem0 在每轮对话后自动抽取（ADD/UPDATE/DELETE judge），
          已失效记录默认隐藏。
        </p>
      </div>
      <div class="actions">
        <el-switch
          v-model="includeInvalidated"
          active-text="含已失效"
          inactive-text="仅生效"
          @change="refresh"
        />
        <el-button size="small" @click="refresh">刷新</el-button>
        <router-link to="/" class="back">← 返回对话</router-link>
      </div>
    </header>

    <el-alert
      v-if="!hasReflectEnabled"
      type="info"
      :closable="false"
      style="margin-bottom: 12px"
    >
      <template #title>
        <strong>MEMORY_REFLECT_ENABLED 当前为 off</strong>——后端未自动写入记忆。
        可在 <code>backend/.env</code> 里设 <code>MEMORY_REFLECT_ENABLED=true</code>
        启用；或在对话里点"立即反思"手工触发。
      </template>
    </el-alert>

    <el-table :data="memories" v-loading="loading" empty-text="暂无 memory 记录">
      <el-table-column label="类型" prop="kind" width="120">
        <template #default="scope">
          <el-tag :type="kindTagType(scope.row.kind)" size="small">{{ scope.row.kind }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="记忆内容">
        <template #default="scope">
          <div :class="{ invalidated: scope.row.invalidated_at }">
            <div v-if="editingId !== scope.row.id">{{ scope.row.object }}</div>
            <el-input
              v-else
              v-model="editBuffer"
              type="textarea"
              :rows="2"
              size="small"
            />
            <div class="meta" v-if="scope.row.invalidated_at">
              已失效：{{ formatTime(scope.row.invalidated_at) }}
              <span v-if="scope.row.superseded_by"> · superseded_by={{ scope.row.superseded_by }}</span>
            </div>
            <div class="meta" v-else-if="scope.row.raw_metadata?.manually_edited">
              ✏️ 已手工编辑
            </div>
          </div>
        </template>
      </el-table-column>
      <el-table-column label="会话" width="120">
        <template #default="scope">
          <span class="mono">{{ (scope.row.conversation_id || '—').slice(-8) }}</span>
        </template>
      </el-table-column>
      <el-table-column label="更新时间" width="170">
        <template #default="scope">
          <span class="meta">{{ formatTime(scope.row.updated_at) }}</span>
        </template>
      </el-table-column>
      <el-table-column label="操作" width="180">
        <template #default="scope">
          <template v-if="editingId === scope.row.id">
            <el-button size="small" type="primary" @click="saveEdit(scope.row)">保存</el-button>
            <el-button size="small" @click="cancelEdit">取消</el-button>
          </template>
          <template v-else>
            <el-button
              size="small"
              :disabled="!!scope.row.invalidated_at"
              @click="startEdit(scope.row)"
            >编辑</el-button>
            <el-button
              size="small"
              type="danger"
              :disabled="!!scope.row.invalidated_at"
              @click="softDelete(scope.row)"
            >软删</el-button>
          </template>
        </template>
      </el-table-column>
    </el-table>

    <footer class="page-footer">
      <span class="meta">共 {{ memories.length }} 条 · 已加载上限 {{ limit }}</span>
    </footer>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'

interface MemoryRecord {
  id: string
  conversation_id: string | null
  user_id: string | null
  kind: string
  subject: string
  predicate: string
  object: string
  valid_at: string | null
  invalidated_at: string | null
  superseded_by: string | null
  source_event_ids: string[]
  confidence: number
  mem0_id: string | null
  created_at: string | null
  updated_at: string | null
  raw_metadata: Record<string, any>
}

const memories = ref<MemoryRecord[]>([])
const loading = ref(false)
const includeInvalidated = ref(false)
const limit = ref(100)
const editingId = ref<string | null>(null)
const editBuffer = ref('')
// 这里不直接读后端 config，给用户一个提示说如果全空可能是 REFLECT 没开
const hasReflectEnabled = ref(true)  // 默认乐观假设开启；若列表空会提示

const kindTagType = (kind: string): ('' | 'success' | 'warning' | 'info' | 'danger') => {
  const map: Record<string, 'success' | 'warning' | 'info' | 'danger'> = {
    user_preference: 'success',
    project_fact: 'warning',
    task_progress: 'info',
    episodic_example: '',
    procedural_rule: 'danger',
    general: '',
  } as any
  return map[kind] || ''
}

const formatTime = (ts: string | null): string => {
  if (!ts) return '—'
  try { return new Date(ts).toLocaleString('zh-CN', { hour12: false }) } catch { return ts }
}

const refresh = async () => {
  loading.value = true
  try {
    const url = `http://localhost:8000/api/memory?include_invalidated=${includeInvalidated.value}&limit=${limit.value}`
    const res = await fetch(url)
    if (!res.ok) {
      ElMessage.error('加载 memory 列表失败')
      return
    }
    const data = await res.json()
    memories.value = data.memories || []
    hasReflectEnabled.value = memories.value.length > 0
  } catch (e: any) {
    ElMessage.error(`加载失败: ${e?.message || e}`)
  } finally {
    loading.value = false
  }
}

const startEdit = (row: MemoryRecord) => {
  editingId.value = row.id
  editBuffer.value = row.object
}

const cancelEdit = () => {
  editingId.value = null
  editBuffer.value = ''
}

const saveEdit = async (row: MemoryRecord) => {
  try {
    const res = await fetch(`http://localhost:8000/api/memory/${row.id}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ object: editBuffer.value }),
    })
    if (!res.ok) {
      ElMessage.error('保存失败')
      return
    }
    ElMessage.success('已保存')
    cancelEdit()
    refresh()
  } catch (e: any) {
    ElMessage.error(`保存失败: ${e?.message || e}`)
  }
}

const softDelete = async (row: MemoryRecord) => {
  const confirmed = await ElMessageBox.confirm(
    `将把这条记忆标记为已失效（不物理删，mem0 Qdrant 侧保留原向量）。`,
    '软删确认',
    { confirmButtonText: '确认软删', cancelButtonText: '取消', type: 'warning' },
  ).catch(() => false)
  if (!confirmed) return
  try {
    const res = await fetch(`http://localhost:8000/api/memory/${row.id}`, { method: 'DELETE' })
    if (!res.ok) {
      ElMessage.error('软删失败')
      return
    }
    ElMessage.success('已软删')
    refresh()
  } catch (e: any) {
    ElMessage.error(`软删失败: ${e?.message || e}`)
  }
}

onMounted(refresh)
</script>

<style scoped>
.memory-audit {
  padding: 24px;
  max-width: 1200px;
  margin: 0 auto;
}
.page-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 20px;
}
.page-header h2 {
  margin: 0 0 6px 0;
  font-size: 22px;
}
.page-header .sub {
  color: var(--text-secondary, #666);
  font-size: 13px;
  margin: 0;
  max-width: 640px;
}
.page-header .actions {
  display: flex;
  gap: 12px;
  align-items: center;
}
.page-header .back {
  color: var(--accent-primary, #409eff);
  text-decoration: none;
  font-size: 13px;
}
.invalidated {
  opacity: 0.55;
  text-decoration: line-through;
  text-decoration-color: #ddd;
}
.meta {
  font-size: 12px;
  color: var(--text-secondary, #999);
  margin-top: 4px;
}
.mono {
  font-family: ui-monospace, 'SF Mono', monospace;
  font-size: 12px;
}
.page-footer {
  margin-top: 16px;
  text-align: right;
}
</style>
