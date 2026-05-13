<template>
  <div class="rag-test-layout">
    <el-container>
      <el-header>
        <div class="header-content">
          <div class="left-section">
            <el-button :icon="Back" circle @click="goBack" style="margin-right: 15px;" />
            <h3>RAG 策略对比：传统 dense vs 混合 hybrid</h3>
          </div>
          <router-link to="/knowledge" class="link-subtle">
            ← 回到知识库
          </router-link>
        </div>
      </el-header>

      <el-main>
        <!-- 控制面板 -->
        <el-card class="control-card">
          <div class="control-row">
            <el-input
              v-model="query"
              placeholder="输入一个问题，比如：计算所复试名单有哪些人？"
              clearable
              class="query-input"
              @keyup.enter="runCompare"
            >
              <template #prepend>Query</template>
            </el-input>
            <div class="control-right">
              <span class="env-sub">Top-K</span>
              <el-input-number v-model="k" :min="1" :max="30" size="default" style="width: 110px;" />
              <el-button type="primary" :loading="running" :disabled="!embeddingReady || !query.trim()" @click="runCompare">
                对比检索
              </el-button>
            </div>
          </div>

          <!-- 环境状态 -->
          <div class="status-row">
            <el-tag v-if="embeddingReady" type="success" size="small">✅ Embedding 已就绪</el-tag>
            <el-tag v-else type="danger" size="small">❌ Embedding 未加载，先去知识库页激活</el-tag>
            <el-tag v-if="sparseSupported" type="success" size="small">✅ sparse 通道可用（BGE-M3）</el-tag>
            <el-tag v-else type="warning" size="small">⚠️ 当前模型不支持 sparse，hybrid 会降级为 dense</el-tag>
          </div>
        </el-card>

        <!-- 结果概览 -->
        <el-card v-if="result" class="summary-card" shadow="never">
          <div class="summary-grid">
            <div class="summary-item">
              <div class="summary-num">{{ result.dense.length }}</div>
              <div class="summary-label">dense 返回条数</div>
            </div>
            <div class="summary-item">
              <div class="summary-num">{{ result.hybrid.length }}</div>
              <div class="summary-label">hybrid 返回条数</div>
            </div>
            <div class="summary-item">
              <div class="summary-num">{{ result.overlap_count }}</div>
              <div class="summary-label">重合 chunk 数</div>
            </div>
            <div class="summary-item">
              <div class="summary-num">{{ (result.overlap_ratio * 100).toFixed(0) }}%</div>
              <div class="summary-label">重合率（按 top-{{ result.k }}）</div>
            </div>
            <div class="summary-item">
              <div class="summary-num" :class="rankShiftColor(avgRankShift)">
                {{ avgRankShift > 0 ? '+' : '' }}{{ avgRankShift.toFixed(2) }}
              </div>
              <div class="summary-label">hybrid 平均排名变化 *</div>
            </div>
          </div>
          <div class="summary-hint">
            * 正数表示 hybrid 把文档往前排（更相关），负数表示往后；仅统计两边都命中的 chunk。重合率高说明两种策略差异小；重合率低而 hybrid 返回含更多稀有词匹配 chunk 时，才是 hybrid 真正带来价值的场景。
          </div>
        </el-card>

        <!-- 并排结果 -->
        <div v-if="result" class="compare-grid">
          <!-- dense 列 -->
          <el-card class="compare-col">
            <template #header>
              <div class="col-header">
                <el-tag type="info" effect="plain">dense 传统 RAG</el-tag>
                <span class="env-sub">仅 1024 维语义向量（Cosine）</span>
              </div>
            </template>
            <div v-if="result.dense.length === 0" class="empty-state">无召回结果</div>
            <div
              v-for="doc in result.dense"
              :key="`dense-${doc.rank}`"
              class="doc-card"
              :class="{ 'doc-overlap': isOverlap(doc, 'dense') }"
            >
              <div class="doc-head">
                <span class="rank">#{{ doc.rank }}</span>
                <span class="src">{{ doc.metadata.original_filename || '未知文件' }}</span>
                <el-tag v-if="isOverlap(doc, 'dense')" size="small" type="success" effect="light" class="overlap-badge">
                  两边都命中
                </el-tag>
                <el-tag
                  v-else
                  size="small"
                  type="warning"
                  effect="light"
                  class="overlap-badge"
                >
                  仅 dense
                </el-tag>
              </div>
              <div class="doc-content">{{ doc.content }}</div>
            </div>
          </el-card>

          <!-- hybrid 列 -->
          <el-card class="compare-col">
            <template #header>
              <div class="col-header">
                <el-tag type="primary" effect="plain">hybrid 混合检索</el-tag>
                <span class="env-sub">dense + learned sparse → 服务端 RRF 融合</span>
              </div>
            </template>
            <div v-if="result.hybrid.length === 0" class="empty-state">无召回结果</div>
            <div
              v-for="doc in result.hybrid"
              :key="`hybrid-${doc.rank}`"
              class="doc-card"
              :class="{ 'doc-overlap': isOverlap(doc, 'hybrid') }"
            >
              <div class="doc-head">
                <span class="rank">#{{ doc.rank }}</span>
                <span class="src">{{ doc.metadata.original_filename || '未知文件' }}</span>
                <el-tag v-if="isOverlap(doc, 'hybrid')" size="small" type="success" effect="light" class="overlap-badge">
                  两边都命中
                </el-tag>
                <el-tag v-else size="small" type="primary" effect="light" class="overlap-badge">
                  仅 hybrid
                </el-tag>
                <el-tag
                  v-if="rankDelta(doc) !== null"
                  size="small"
                  effect="plain"
                  :type="rankDelta(doc)! > 0 ? 'success' : (rankDelta(doc)! < 0 ? 'danger' : 'info')"
                  class="delta-badge"
                >
                  Δ rank: {{ rankDelta(doc)! > 0 ? '+' : '' }}{{ rankDelta(doc) }}
                </el-tag>
              </div>
              <div class="doc-content">{{ doc.content }}</div>
            </div>
          </el-card>
        </div>

        <!-- 使用提示 -->
        <el-card v-if="!result && !running" class="hint-card" shadow="never">
          <h4>📝 使用说明</h4>
          <ul>
            <li>这个页面不走 Reranker，展示的是两种策略<strong>最原始的召回结果</strong>，便于肉眼评估差异。</li>
            <li>"重合率"是两种策略 top-K 结果中内容基本一致的比例；重合率过高（&gt;90%）意味着 hybrid 对你的查询几乎没有带来新信息。</li>
            <li>hybrid 通常在这些查询上明显更好：<strong>含专有名词、人名、型号、代码标识符</strong>的查询。</li>
            <li>如果你当前 Embedding 模型不是 BGE-M3，sparse 通道不可用，hybrid 会自动降级为 dense（两列会完全一致）。</li>
            <li>在知识库页面的"检索策略"开关切换后，这个页面的对比结果<strong>不会改变</strong> —— 对比页面始终同时跑两种策略，用于决策参考。</li>
          </ul>
        </el-card>
      </el-main>
    </el-container>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { Back } from '@element-plus/icons-vue'

const router = useRouter()

interface DocItem {
  rank: number
  content: string
  metadata: Record<string, any>
  source_file_id: string | null
}

interface CompareResult {
  query: string
  k: number
  sparse_supported: boolean
  dense: DocItem[]
  hybrid: DocItem[]
  overlap_count: number
  overlap_ratio: number
}

const query = ref('')
const k = ref(10)
const running = ref(false)
const result = ref<CompareResult | null>(null)
const embeddingReady = ref(false)
const sparseSupported = ref(false)

const goBack = () => router.push('/knowledge')

const fetchEnv = async () => {
  try {
    const res = await fetch('http://localhost:8000/api/embedding/search-mode')
    if (res.ok) {
      const data = await res.json()
      embeddingReady.value = data.embedding_ready ?? false
      sparseSupported.value = data.sparse_supported ?? false
    }
  } catch (e) {
    console.error(e)
  }
}

const runCompare = async () => {
  const q = query.value.trim()
  if (!q) return
  if (!embeddingReady.value) {
    ElMessage.warning('Embedding 未就绪，请先到知识库页激活模型')
    return
  }
  running.value = true
  result.value = null
  try {
    const url = `http://localhost:8000/api/vs/compare?q=${encodeURIComponent(q)}&k=${k.value}`
    const res = await fetch(url)
    if (!res.ok) {
      const err = await res.json().catch(() => ({}))
      ElMessage.error(typeof err.detail === 'string' ? err.detail : 'compare 失败')
      return
    }
    result.value = await res.json()
  } catch (e) {
    ElMessage.error('请求失败')
  } finally {
    running.value = false
  }
}

// ── 两边重合计算（前端 mirror 后端 fingerprint 逻辑）─────────────────

const fingerprint = (doc: DocItem) => `${doc.source_file_id ?? ''}::${doc.content.slice(0, 60)}`

const denseFpMap = computed(() => {
  const m = new Map<string, DocItem>()
  result.value?.dense.forEach(d => m.set(fingerprint(d), d))
  return m
})
const hybridFpMap = computed(() => {
  const m = new Map<string, DocItem>()
  result.value?.hybrid.forEach(d => m.set(fingerprint(d), d))
  return m
})

const isOverlap = (doc: DocItem, side: 'dense' | 'hybrid') => {
  const fp = fingerprint(doc)
  return side === 'dense' ? hybridFpMap.value.has(fp) : denseFpMap.value.has(fp)
}

// hybrid 文档在 dense 中的排名差（正数 = hybrid 把它往前排了）
const rankDelta = (doc: DocItem): number | null => {
  const denseDoc = denseFpMap.value.get(fingerprint(doc))
  if (!denseDoc) return null
  return denseDoc.rank - doc.rank
}

const avgRankShift = computed(() => {
  if (!result.value) return 0
  const deltas: number[] = []
  result.value.hybrid.forEach(h => {
    const d = rankDelta(h)
    if (d !== null) deltas.push(d)
  })
  if (deltas.length === 0) return 0
  return deltas.reduce((a, b) => a + b, 0) / deltas.length
})

const rankShiftColor = (v: number) => {
  if (v > 0.5) return 'shift-pos'
  if (v < -0.5) return 'shift-neg'
  return ''
}

onMounted(fetchEnv)
</script>

<style scoped>
.rag-test-layout {
  height: 100vh;
  background-color: var(--bg-primary);
  overflow-y: auto;
}
.el-header {
  background-color: var(--bg-secondary);
  border-bottom: 1px solid var(--border-color);
  display: flex;
  align-items: center;
  padding: 0 32px;
  height: 72px;
}
.header-content {
  display: flex;
  justify-content: space-between;
  width: 100%;
  align-items: center;
}
.left-section { display: flex; align-items: center; }
.left-section h3 {
  font-size: 1.25rem;
  font-weight: 700;
  margin: 0;
  color: var(--text-primary);
}
.link-subtle {
  color: var(--text-secondary);
  text-decoration: none;
  font-size: 13px;
}
.link-subtle:hover { color: var(--accent-primary, #409eff); }
.el-main { padding: 24px 32px; }

.control-card { margin-bottom: 20px; max-width: 1400px; margin-left: auto; margin-right: auto; }
.control-row {
  display: flex;
  gap: 16px;
  align-items: center;
  flex-wrap: wrap;
}
.query-input { flex: 1; min-width: 320px; }
.control-right {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}
.status-row {
  margin-top: 12px;
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}
.env-sub {
  font-size: 12px;
  color: var(--text-secondary);
}

.summary-card {
  max-width: 1400px;
  margin: 0 auto 20px;
}
.summary-grid {
  display: grid;
  grid-template-columns: repeat(5, 1fr);
  gap: 20px;
}
.summary-item {
  text-align: center;
  padding: 12px;
  background: var(--bg-secondary);
  border-radius: 6px;
}
.summary-num {
  font-size: 1.6rem;
  font-weight: 700;
  color: var(--text-primary);
}
.summary-num.shift-pos { color: #67c23a; }
.summary-num.shift-neg { color: #f56c6c; }
.summary-label {
  font-size: 12px;
  color: var(--text-secondary);
  margin-top: 4px;
}
.summary-hint {
  margin-top: 14px;
  font-size: 12px;
  color: var(--text-secondary);
  line-height: 1.6;
}

.compare-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 20px;
  max-width: 1400px;
  margin: 0 auto;
}
.compare-col { min-height: 200px; }
.col-header {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}

.doc-card {
  border: 1px solid var(--border-color);
  border-radius: 6px;
  padding: 10px 12px;
  margin-bottom: 10px;
  background: var(--bg-primary);
  transition: all 0.2s;
}
.doc-card.doc-overlap {
  border-left: 3px solid #67c23a;
  background: rgba(103, 194, 58, 0.04);
}
.doc-head {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 6px;
  flex-wrap: wrap;
}
.rank {
  font-weight: 700;
  color: var(--accent-primary, #409eff);
  font-size: 14px;
}
.src {
  font-size: 13px;
  color: var(--text-secondary);
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.overlap-badge { flex-shrink: 0; }
.delta-badge { flex-shrink: 0; }
.doc-content {
  font-size: 13px;
  line-height: 1.55;
  color: var(--text-primary);
  word-break: break-all;
}
.empty-state {
  text-align: center;
  color: var(--text-secondary);
  padding: 30px;
}

.hint-card {
  max-width: 1000px;
  margin: 40px auto;
  background: var(--bg-secondary);
}
.hint-card h4 { margin: 0 0 10px 0; }
.hint-card ul {
  margin: 0;
  padding-left: 20px;
  color: var(--text-secondary);
  font-size: 13px;
  line-height: 1.8;
}
</style>
