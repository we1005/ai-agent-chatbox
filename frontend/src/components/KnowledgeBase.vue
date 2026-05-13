<template>
  <div class="knowledge-base-layout">
    <el-container>
      <el-header>
        <div class="header-content">
          <div class="left-section">
            <el-button :icon="Back" circle @click="goBack" style="margin-right: 15px;" />
            <h3>Knowledge Base Management</h3>
          </div>
          <el-upload
            class="upload-demo"
            action="#"
            accept=".pdf,.txt,.md,.docx,.csv,.xlsx,.xls,.pptx,.epub"
            :auto-upload="false"
            :show-file-list="false"
            :on-change="handleFileChange"
            :disabled="!embeddingReady"
          >
            <el-tooltip
              :content="embeddingReady ? '' : 'Embedding 模型未就绪，请先完成下方配置'"
              :disabled="embeddingReady"
              placement="bottom"
            >
              <el-button
                type="primary"
                :loading="uploading"
                :icon="Upload"
                :disabled="!embeddingReady"
              >Upload New Document</el-button>
            </el-tooltip>
          </el-upload>
        </div>
      </el-header>

      <el-main>
        <!-- ── Embedding 配置面板 ─────────────────────────────── -->
        <el-card class="box-card env-card" style="margin-bottom: 20px;">
          <template #header>
            <div class="card-header">
              <span>Embedding 模型配置</span>
              <el-button size="small" :icon="Refresh" circle plain @click="fetchSystemInfo" :loading="loadingInfo" />
            </div>
          </template>

          <div class="env-grid">
            <!-- GPU 状态 -->
            <div class="env-item">
              <div class="env-label">GPU 硬件</div>
              <div class="env-value">
                <template v-if="sysInfo?.gpu?.hardware_available">
                  <el-tag type="success" size="small">✅ {{ sysInfo.gpu.name }}</el-tag>
                  <span class="env-sub">{{ sysInfo.gpu.vram_total_gb }} GB VRAM</span>
                </template>
                <el-tag v-else type="info" size="small">ℹ️ 未检测到 GPU / Apple Silicon</el-tag>
              </div>
            </div>

            <!-- PyTorch 加速后端状态（CUDA / MPS / CPU） -->
            <div class="env-item">
              <div class="env-label">PyTorch 加速</div>
              <div class="env-value">
                <template v-if="sysInfo?.gpu?.accelerator === 'cuda'">
                  <el-tag type="success" size="small">✅ {{ sysInfo.gpu.pytorch_version }}</el-tag>
                  <span class="env-sub">CUDA {{ sysInfo.gpu.cuda_version }}</span>
                </template>
                <template v-else-if="sysInfo?.gpu?.accelerator === 'mps'">
                  <el-tag type="success" size="small">✅ {{ sysInfo.gpu.pytorch_version }}</el-tag>
                  <span class="env-sub">MPS (Apple Silicon)</span>
                </template>
                <template v-else-if="sysInfo?.gpu?.hardware_available && !sysInfo?.gpu?.pytorch_cuda_available">
                  <!-- 有 NVIDIA 硬件但装了 CPU 版 torch，给安装命令 -->
                  <el-tag type="warning" size="small">⚠️ {{ sysInfo.gpu.pytorch_version || '未知版本' }}（CPU 版）</el-tag>
                  <div class="install-hint">
                    安装 GPU 版：
                    <code class="code-snippet" @click="copyInstallCmd">
                      pip install torch --index-url https://download.pytorch.org/whl/cu121
                    </code>
                    <el-tag size="small" type="info" style="cursor:pointer" @click="copyInstallCmd">复制</el-tag>
                  </div>
                </template>
                <el-tag v-else type="info" size="small">— CPU 模式</el-tag>
              </div>
            </div>

            <!-- BGE-M3 本地模型 -->
            <div class="env-item">
              <div class="env-label">BGE-M3 模型</div>
              <div class="env-value">
                <template v-if="sysInfo?.local_models?.bge_m3?.downloaded">
                  <el-tag type="success" size="small">✅ 已下载</el-tag>
                  <span class="env-sub">{{ sysInfo.local_models.bge_m3.size_gb }} GB</span>
                </template>
                <template v-else-if="downloadState.status === 'idle' || downloadState.status === 'failed'">
                  <el-tag type="danger" size="small">❌ 未下载</el-tag>
                  <span class="env-sub">约 {{ sysInfo?.local_models?.bge_m3?.expected_gb ?? 2.27 }} GB</span>
                  <el-button size="small" type="primary" plain @click="startDownload(true)" style="margin-left: 8px;">
                    下载模型
                  </el-button>
                </template>
                <template v-else-if="downloadState.status === 'paused'">
                  <el-tag type="warning" size="small">⏸ 已暂停</el-tag>
                  <span class="env-sub">
                    {{ downloadState.downloaded_mb.toFixed(0) }} / {{ downloadState.total_mb.toFixed(0) }} MB
                  </span>
                  <el-button size="small" type="primary" @click="startDownload(true)" style="margin-left: 8px;">
                    继续下载
                  </el-button>
                  <el-button size="small" type="default" @click="startDownload(false)">
                    重新下载
                  </el-button>
                </template>
                <template v-else-if="downloadState.status === 'downloading'">
                  <el-tag type="info" size="small">⬇ 下载中</el-tag>
                  <span class="env-sub">约 {{ sysInfo?.local_models?.bge_m3?.expected_gb ?? 2.27 }} GB</span>
                </template>
              </div>
            </div>

            <!-- 下载进度条（下载中 / 暂停中） -->
            <div v-if="downloadState.status === 'downloading' || downloadState.status === 'paused'" class="env-item env-full">
              <div class="env-label">下载进度</div>
              <div class="download-progress-row">
                <el-progress
                  :percentage="Math.round(downloadState.progress * 100)"
                  :status="downloadState.status === 'paused' ? 'warning' : undefined"
                  class="download-progress-bar"
                />
                <div class="download-meta">
                  <span class="env-sub">
                    {{ downloadState.downloaded_mb.toFixed(0) }} / {{ downloadState.total_mb.toFixed(0) }} MB
                  </span>
                  <span v-if="downloadState.status === 'downloading' && downloadState.speed_mbps > 0" class="download-speed">
                    {{ downloadState.speed_mbps.toFixed(1) }} MB/s
                    · 剩余约 {{ estimateRemaining() }}
                  </span>
                  <span v-else-if="downloadState.status === 'paused'" class="env-sub" style="color: #e6a23c;">
                    已暂停
                  </span>
                </div>
                <el-button
                  v-if="downloadState.status === 'downloading'"
                  size="small"
                  type="danger"
                  plain
                  @click="cancelDownload"
                  style="margin-left: 12px; flex-shrink: 0;"
                >
                  停止
                </el-button>
              </div>
            </div>

            <div v-if="downloadState.status === 'failed'" class="env-item env-full">
              <el-tag type="danger">下载失败：{{ downloadState.error }}</el-tag>
              <el-button size="small" type="primary" plain @click="startDownload(false)" style="margin-left: 8px;">
                重新下载
              </el-button>
            </div>

            <!-- 推理设备切换 -->
            <div class="env-item">
              <div class="env-label">推理设备</div>
              <div class="env-value">
                <el-radio-group v-model="embeddingConfig.use_gpu" size="small" @change="saveConfig">
                  <el-radio-button :value="true" :disabled="!sysInfo?.gpu?.hardware_available">
                    GPU 推理
                  </el-radio-button>
                  <el-radio-button :value="false">CPU 推理</el-radio-button>
                </el-radio-group>
              </div>
            </div>

            <!-- 激活/重载按钮 -->
            <div class="env-item">
              <div class="env-label">服务状态</div>
              <div class="env-value">
                <el-tag v-if="embeddingReady" type="success">✅ 已就绪</el-tag>
                <el-tag v-else type="danger">❌ 未就绪</el-tag>
                <el-button
                  v-if="!embeddingReady && sysInfo?.local_models?.bge_m3?.downloaded"
                  size="small"
                  type="primary"
                  style="margin-left: 8px;"
                  @click="activateModel"
                  :loading="activating"
                >
                  加载模型
                </el-button>
              </div>
            </div>

            <!-- Reranker 模型状态 -->
            <div class="env-item">
              <div class="env-label">BGE-Reranker</div>
              <div class="env-value">
                <template v-if="sysInfo?.local_models?.bge_reranker?.downloaded">
                  <el-tag type="success" size="small">✅ 已下载</el-tag>
                  <span class="env-sub">{{ sysInfo.local_models.bge_reranker.size_gb }} GB</span>
                </template>
                <template v-else>
                  <el-tag type="info" size="small">— 未下载</el-tag>
                  <span class="env-sub">约 2.4 GB（可选，精排用）</span>
                </template>
              </div>
            </div>

            <!-- 检索策略 -->
            <div class="env-item">
              <div class="env-label">检索策略</div>
              <div class="env-value">
                <template v-if="ragStrategy?.strategy === 'recall+rerank'">
                  <el-tag type="success" size="small">Recall + Rerank</el-tag>
                  <span class="env-sub">
                    向量召回 Top-{{ ragStrategy.recall_k }} → Reranker 精排 → Top-{{ ragStrategy.rerank_top_n }}
                  </span>
                </template>
                <template v-else>
                  <el-tag type="warning" size="small">仅 Recall</el-tag>
                  <span class="env-sub">
                    向量召回 Top-4（下载并加载 BGE-Reranker 后自动升级为两阶段检索）
                  </span>
                </template>
              </div>
            </div>

            <!-- Reranker 开关：开启时动态加载到显存，关闭时释放 -->
            <div class="env-item">
              <div class="env-label">启用 Reranker</div>
              <div class="env-value">
                <el-tooltip
                  :content="rerankerTooltip"
                  placement="right"
                >
                  <el-switch
                    v-model="useReranker"
                    :disabled="!embeddingReady || !rerankerDownloaded"
                    :loading="rerankerLoading"
                    :before-change="handleRerankerToggle"
                    active-text="开启"
                    inactive-text="关闭"
                  />
                </el-tooltip>
                <span v-if="rerankerDownloaded" class="env-sub" style="margin-left: 12px;">
                  {{ useReranker
                    ? '已加载：Recall Top-20 → Reranker → Top-4'
                    : '未加载（约 2.4GB VRAM，开启时按需加载）' }}
                </span>
              </div>
            </div>

            <!-- 混合检索开关：默认关闭 = 传统 RAG（dense-only）；开启 = Qdrant 原生 hybrid -->
            <div class="env-item">
              <div class="env-label">检索策略</div>
              <div class="env-value">
                <el-tooltip :content="hybridTooltip" placement="right">
                  <el-switch
                    v-model="hybridEnabled"
                    :disabled="!embeddingReady || (!sparseSupported && hybridEnabled === false)"
                    :loading="hybridSwitching"
                    :before-change="handleHybridToggle"
                    active-text="Hybrid"
                    inactive-text="传统 RAG"
                  />
                </el-tooltip>
                <span class="env-sub" style="margin-left: 12px;">
                  {{ hybridEnabled
                    ? '混合检索：dense + learned sparse（BGE-M3）→ 服务端 RRF 融合'
                    : '传统 RAG：仅 dense 语义检索（默认）' }}
                </span>
                <router-link
                  to="/rag-test"
                  class="env-sub"
                  style="margin-left: 12px; color: var(--accent-primary, #409eff); text-decoration: underline; cursor: pointer;"
                >
                  去策略对比 →
                </router-link>
              </div>
            </div>

            <!-- Multi-Query 多路召回：LLM 生成 3 个 variant 并行召回，默认关闭 -->
            <div class="env-item">
              <div class="env-label">Multi-Query</div>
              <div class="env-value">
                <el-tooltip
                  :content="graphRagEnabled ? 'Graph RAG 启用时此开关不生效（Graph RAG 覆盖）' : '开启后每次 RAG 检索由 LLM 生成 3 个不同角度的 query 变体并行召回，再合并 / RRF 融合。提升主题模糊查询的召回完整性，但额外 +1 次 LLM 调用（~500ms）。仅 classic 路径生效，Solo 不受影响。'"
                  placement="right"
                >
                  <el-switch
                    v-model="multiQueryEnabled"
                    :disabled="!embeddingReady || graphRagEnabled"
                    :loading="multiQuerySwitching"
                    :before-change="handleMultiQueryToggle"
                    active-text="多路召回"
                    inactive-text="单 query"
                  />
                </el-tooltip>
                <span class="env-sub" style="margin-left: 12px;">
                  {{ multiQueryEnabled
                    ? '开启后 classic 路径每次检索跑 4 路 query（原 + 3 variants），与狭义 Rewrite 互斥'
                    : '默认：单 query 检索 + 启发式 Rewrite（代词/过短触发）' }}
                </span>
              </div>
            </div>

            <!-- Agentic RAG 档位：off / grading_only / grading_rewrite / full，默认 off -->
            <!-- 只影响 classic 路径；Solo 启用时置灰（Solo 自带 agentic 行为） -->
            <!-- Graph RAG 启用时也置灰（Graph RAG 覆盖 Agentic） -->
            <div class="env-item">
              <div class="env-label">Agentic RAG</div>
              <div class="env-value">
                <el-tooltip
                  :content="graphRagEnabled ? 'Graph RAG 启用时此档位不生效（Graph RAG 覆盖）' : agenticRagTooltip"
                  placement="right"
                >
                  <el-segmented
                    v-model="agenticRagMode"
                    :options="agenticRagOptions"
                    :disabled="!embeddingReady || store.enableSolo || graphRagEnabled"
                    size="small"
                    @change="handleAgenticRagModeChange"
                  />
                </el-tooltip>
                <span class="env-sub" style="margin-left: 12px;">
                  {{ agenticRagDescription }}
                </span>
              </div>
            </div>

            <!-- Graph RAG（LightRAG）开关 + 查询模式 + 索引构建 -->
            <!-- 启用时拥有最高优先级，覆盖 Agentic / Multi-Query。默认 OFF。 -->
            <div class="env-item">
              <div class="env-label">Graph RAG</div>
              <div class="env-value">
                <el-tooltip
                  :content="graphRagTooltip"
                  placement="right"
                >
                  <el-switch
                    v-model="graphRagEnabled"
                    :disabled="!embeddingReady || store.enableSolo || !graphRagStats.exists || graphRagStats.nodes === 0"
                    :before-change="handleGraphRagToggle"
                    active-text="Graph RAG"
                    inactive-text="Vector"
                  />
                </el-tooltip>
                <el-select
                  v-model="graphRagQueryMode"
                  :disabled="!graphRagEnabled"
                  size="small"
                  style="width: 110px; margin-left: 12px;"
                  @change="handleGraphRagModeChange"
                >
                  <el-option
                    v-for="m in graphRagModeOptions"
                    :key="m.value"
                    :label="m.label"
                    :value="m.value"
                  />
                </el-select>
                <span class="env-sub" style="margin-left: 12px;">
                  {{ graphRagDescription }}
                </span>
              </div>
            </div>

            <!-- Graph RAG 索引构建 / 清空 / 统计 -->
            <div class="env-item">
              <div class="env-label">图索引</div>
              <div class="env-value" style="display: flex; align-items: center; gap: 12px; flex-wrap: wrap;">
                <el-button
                  type="primary"
                  size="small"
                  :disabled="!embeddingReady || graphRagBuildState.status === 'running'"
                  :loading="graphRagBuildState.status === 'running'"
                  @click="handleGraphRagBuild"
                >构建 / 增量更新</el-button>
                <el-button
                  size="small"
                  :disabled="!graphRagStats.exists || graphRagBuildState.status === 'running'"
                  @click="handleGraphRagClear"
                >清空索引</el-button>
                <span class="env-sub">
                  节点 {{ graphRagStats.nodes }} · 边 {{ graphRagStats.edges }} · 文档 {{ graphRagStats.documents }}
                </span>
                <span v-if="graphRagBuildState.status === 'running'" class="env-sub" style="color: var(--accent-primary);">
                  构建中 {{ graphRagBuildState.processed }}/{{ graphRagBuildState.total }}
                  <template v-if="graphRagBuildState.current_doc"> · {{ graphRagBuildState.current_doc }}</template>
                </span>
                <span v-else-if="graphRagBuildState.message" class="env-sub">{{ graphRagBuildState.message }}</span>
              </div>
            </div>
          </div>
        </el-card>

        <!-- ── 文档列表 ──────────────────────────────────────── -->
        <el-card class="box-card" v-loading="loading">
          <template #header>
            <div class="card-header">
              <span>Uploaded Documents</span>
              <el-tag v-if="!embeddingReady" type="warning" size="small">
                上传功能不可用（模型未就绪）
              </el-tag>
            </div>
          </template>

          <el-table :data="documents" style="width: 100%" empty-text="No documents uploaded yet">
            <el-table-column label="File Name">
              <template #default="scope">
                <div class="file-name-cell">
                  <el-icon class="file-icon" :class="getFileIconColor(scope.row.extension)">
                    <component :is="getFileIcon(scope.row.extension)" />
                  </el-icon>
                  <span>{{ scope.row.filename }}</span>
                </div>
              </template>
            </el-table-column>
            <el-table-column label="Size" width="120">
              <template #default="scope">
                {{ formatBytes(scope.row.size) }}
              </template>
            </el-table-column>
            <el-table-column label="Status" width="140">
              <template #default="scope">
                <el-tag
                  :type="statusTagType(scope.row.status)"
                  size="small"
                  effect="light"
                >{{ statusLabel(scope.row.status) }}</el-tag>
                <el-tooltip v-if="scope.row.status === 'failed'" :content="scope.row.error_message" placement="top">
                  <el-icon style="margin-left:4px;color:#f56c6c;cursor:pointer;"><Warning /></el-icon>
                </el-tooltip>
              </template>
            </el-table-column>
            <el-table-column label="Upload Date" width="180">
              <template #default="scope">
                {{ formatDate(scope.row.uploaded_at) }}
              </template>
            </el-table-column>
            <el-table-column label="Actions" width="120" align="right">
              <template #default="scope">
                <el-button
                  type="primary"
                  :icon="Refresh"
                  circle
                  plain
                  size="small"
                  @click="revectorizeDocument(scope.row)"
                  title="Re-vectorize Document"
                  style="margin-right: 8px;"
                  :disabled="!embeddingReady"
                />
                <el-button
                  type="danger"
                  :icon="Delete"
                  circle
                  size="small"
                  @click="deleteDocument(scope.row)"
                  title="Delete Document"
                />
              </template>
            </el-table-column>
          </el-table>
        </el-card>
      </el-main>
    </el-container>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted, computed, watch } from 'vue'
import { useRouter } from 'vue-router'
import { useChatStore } from '../store/chat'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Back, Upload, Document, Picture, Management, List, Delete, Refresh, Warning, Grid, Tickets, Reading } from '@element-plus/icons-vue'

const router = useRouter()
const store = useChatStore()

interface DocumentItem {
  filename: string
  file_id: string
  extension: string
  size: number
  chunks: number
  status: string
  error_message: string
  uploaded_at: string | null
  vectorized_at: string | null
}

interface SystemInfo {
  gpu: {
    hardware_available: boolean
    name: string | null
    vram_total_gb: number | null
    vram_free_gb: number | null
    pytorch_cuda_available: boolean
    pytorch_mps_available?: boolean
    accelerator?: 'cuda' | 'mps' | 'cpu'
    pytorch_version: string | null
    cuda_version: string | null
    error: string | null
  }
  local_models: {
    bge_m3: {
      downloaded: boolean
      path: string
      size_gb: number
      expected_gb: number
    }
    bge_reranker: {
      downloaded: boolean
      path: string
      size_gb: number
      expected_gb: number
    }
  }
  current_config: {
    mode: string
    local_model: string
    use_gpu: boolean
    online_provider: string | null
  }
  embedding_ready: boolean
}

interface DownloadState {
  status: 'idle' | 'downloading' | 'paused' | 'done' | 'failed'
  progress: number
  downloaded_mb: number
  total_mb: number
  speed_mbps: number
  error: string
}

const documents = ref<DocumentItem[]>([])
const loading = ref(false)
const uploading = ref(false)
const loadingInfo = ref(false)
const activating = ref(false)

const sysInfo = ref<SystemInfo | null>(null)
const embeddingConfig = ref({ use_gpu: true })
const downloadState = ref<DownloadState>({
  status: 'idle', progress: 0, downloaded_mb: 0, total_mb: 2270, speed_mbps: 0, error: ''
})

interface RagStrategy {
  reranker_downloaded: boolean
  reranker_loaded: boolean
  strategy: 'recall+rerank' | 'recall_only'
  recall_k: number
  rerank_top_n: number
}
const ragStrategy = ref<RagStrategy | null>(null)

let downloadPollTimer: ReturnType<typeof setInterval> | null = null

const embeddingReady = computed(() => {
  return sysInfo.value?.embedding_ready ?? false
})

const rerankerDownloaded = computed(() => {
  return sysInfo.value?.local_models?.bge_reranker?.downloaded ?? false
})

const useReranker = computed({
  get: () => store.useReranker,
  set: (val: boolean) => store.setUseReranker(val),
})

const rerankerLoading = ref(false)

const rerankerTooltip = computed(() => {
  if (!embeddingReady.value) return 'Embedding 模型未加载，请先加载 Embedding 模型'
  if (!rerankerDownloaded.value) return 'Reranker 模型未下载，无法启用'
  return useReranker.value
    ? '关闭后立即释放显存'
    : '开启后将加载 Reranker 模型到显存（约 2.4GB）'
})

// ── 检索策略（dense 传统 / hybrid 混合）──────────────────────────────

const hybridEnabled = ref(false)           // false = 传统 dense；true = hybrid
const sparseSupported = ref(false)
const hybridSwitching = ref(false)

const hybridTooltip = computed(() => {
  if (!embeddingReady.value) return 'Embedding 模型未加载'
  if (!sparseSupported.value) return '当前 Embedding 模型不支持 sparse（仅 BGE-M3 支持），无法开启 Hybrid'
  return hybridEnabled.value
    ? '关闭后回退到传统 dense 语义检索'
    : '开启后走 dense + learned sparse 双通道 + 服务端 RRF 融合'
})

const fetchSearchMode = async () => {
  try {
    const res = await fetch('http://localhost:8000/api/embedding/search-mode')
    if (res.ok) {
      const data = await res.json()
      hybridEnabled.value = data.mode === 'hybrid'
      sparseSupported.value = data.sparse_supported ?? false
    }
  } catch (e) {
    console.error('Failed to fetch search mode', e)
  }
}

// embedding 从"未就绪"切换到"就绪"时，立即刷新 search-mode，让 Hybrid 开关
// 根据最新的 sparse_supported 状态解除/保持禁用，而不是停留在上次的旧值上。
watch(embeddingReady, (ready, prev) => {
  if (ready && !prev) {
    fetchSearchMode()
  }
})

const handleHybridToggle = async (): Promise<boolean> => {
  const turningOn = !hybridEnabled.value
  const target = turningOn ? 'hybrid' : 'dense'
  hybridSwitching.value = true
  try {
    const res = await fetch('http://localhost:8000/api/embedding/search-mode', {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ mode: target }),
    })
    if (!res.ok) {
      const err = await res.json().catch(() => ({}))
      ElMessage.error(typeof err.detail === 'string' ? err.detail : '切换失败')
      return false
    }
    const data = await res.json()
    if (target === 'hybrid' && !data.sparse_supported) {
      ElMessage.warning('当前模型不支持 sparse，已切换字段但实际仍走 dense')
    } else {
      ElMessage.success(data.message || `已切换到${turningOn ? ' Hybrid ' : '传统 RAG '}检索`)
    }
    return true
  } catch (e) {
    ElMessage.error('切换失败')
    return false
  } finally {
    hybridSwitching.value = false
  }
}

// ── Multi-Query 多路召回开关（classic 路径） ──────────────────────────

const multiQueryEnabled = ref(false)
const multiQuerySwitching = ref(false)

const fetchMultiQuery = async () => {
  try {
    const res = await fetch('http://localhost:8000/api/embedding/multi-query')
    if (res.ok) {
      const data = await res.json()
      multiQueryEnabled.value = !!data.enabled
    }
  } catch (e) {
    console.error('Failed to fetch multi-query mode', e)
  }
}

watch(embeddingReady, (ready, prev) => {
  if (ready && !prev) fetchMultiQuery()
})

const handleMultiQueryToggle = async (): Promise<boolean> => {
  const turningOn = !multiQueryEnabled.value
  multiQuerySwitching.value = true
  try {
    const res = await fetch('http://localhost:8000/api/embedding/multi-query', {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ enabled: turningOn }),
    })
    if (!res.ok) {
      const err = await res.json().catch(() => ({}))
      ElMessage.error(typeof err.detail === 'string' ? err.detail : '切换失败')
      return false
    }
    const data = await res.json()
    ElMessage.success(data.message || (turningOn ? 'Multi-Query 已启用' : 'Multi-Query 已关闭'))
    return true
  } catch (e) {
    ElMessage.error('切换失败')
    return false
  } finally {
    multiQuerySwitching.value = false
  }
}

// ── Agentic RAG 档位（classic 路径，4 档）──────────────────────────────
// 详见 plan-doc-dir/本项目是否真的实现了Agentic-RAG.md
type AgenticRagMode = 'off' | 'grading_only' | 'grading_rewrite' | 'full'
const agenticRagMode = ref<AgenticRagMode>('off')

const agenticRagOptions = [
  { label: '关闭', value: 'off' },
  { label: 'Grading', value: 'grading_only' },
  { label: '+ Rewrite', value: 'grading_rewrite' },
  { label: 'Full (CRAG)', value: 'full' },
]

const agenticRagDescription = computed(() => {
  if (store.enableSolo) return 'Solo 模式自带 agentic 行为，此档位对 Solo 无效'
  switch (agenticRagMode.value) {
    case 'off':
      return '关闭：走现有 classical（一击即中）。切开后可对比召回质量差异'
    case 'grading_only':
      return 'Grading：检索后 LLM 评分过滤不相关 chunk（+1 次 LLM / 请求）'
    case 'grading_rewrite':
      return 'Grading + Rewrite：通过率低时改写 query 重试（最多 2 次；Multi-Query ON 时 1 次）'
    case 'full':
      return '完整 CRAG：+ Hallucination Check（答案缺文档支撑时挂警告 banner，不重生成）'
    default:
      return ''
  }
})

const agenticRagTooltip = computed(() => {
  if (store.enableSolo) {
    return 'Solo 模式已是 ReAct Agent，自带多轮工具决策；此档位仅对 classic 路径生效，已置灰。'
  }
  return '切换 classical → agentic RAG 档位，用于对比同一 query 在不同自我纠错强度下的表现。默认 off 向后兼容。只在 intent=general AND use_knowledge_base=true 时触发。'
})

const fetchAgenticRagMode = async () => {
  try {
    const res = await fetch('http://localhost:8000/api/embedding/agentic-rag')
    if (res.ok) {
      const data = await res.json()
      if (typeof data.mode === 'string') {
        agenticRagMode.value = data.mode as AgenticRagMode
      }
    }
  } catch (e) {
    console.error('Failed to fetch agentic-rag mode', e)
  }
}

watch(embeddingReady, (ready, prev) => {
  if (ready && !prev) fetchAgenticRagMode()
})

const handleAgenticRagModeChange = async (value: string | number | boolean) => {
  const target = String(value) as AgenticRagMode
  const old = agenticRagMode.value
  // segmented 已双向绑定 v-model，此时 agenticRagMode.value 已经变了
  // 若后端失败需要回滚
  try {
    const res = await fetch('http://localhost:8000/api/embedding/agentic-rag', {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ mode: target }),
    })
    if (!res.ok) {
      const err = await res.json().catch(() => ({}))
      ElMessage.error(typeof err.detail === 'string' ? err.detail : 'Agentic RAG 档位切换失败')
      agenticRagMode.value = old
      return
    }
    const data = await res.json()
    ElMessage.success(data.message || `Agentic RAG: ${target}`)
  } catch (e) {
    ElMessage.error('Agentic RAG 档位切换失败')
    agenticRagMode.value = old
  }
}

// ── Graph RAG（LightRAG）开关 + 查询模式 + 索引构建 ──────────────────
// 详见 plan-doc-dir/LightRAG集成落地.md 与 Graph-RAG适合的文档特征与开源评测集.md

type GraphRagMode = 'naive' | 'local' | 'global' | 'hybrid' | 'mix'

const graphRagEnabled = ref(false)
const graphRagQueryMode = ref<GraphRagMode>('hybrid')
const graphRagStats = ref<{ exists: boolean; nodes: number; edges: number; documents: number; path?: string }>({
  exists: false, nodes: 0, edges: 0, documents: 0,
})
const graphRagBuildState = ref<{
  status: string; phase: string | null; total: number; processed: number;
  current_doc: string | null; message: string | null;
}>({
  status: 'idle', phase: null, total: 0, processed: 0, current_doc: null, message: null,
})

const graphRagModeOptions = [
  { label: 'hybrid', value: 'hybrid' },
  { label: 'local',  value: 'local' },
  { label: 'global', value: 'global' },
  { label: 'naive',  value: 'naive' },
  { label: 'mix',    value: 'mix' },
]

const graphRagTooltip = computed(() => {
  if (store.enableSolo) return 'Solo 模式走独立路径，此开关不生效（已置灰）'
  if (!graphRagStats.value.exists || graphRagStats.value.nodes === 0) return '请先点下方"构建 / 增量更新"生成图索引'
  return '启用后覆盖 Agentic / Multi-Query，用 LightRAG 做多跳 / 聚合查询。仅 classic 路径、intent=general + use_knowledge_base=true 时触发。'
})

const graphRagDescription = computed(() => {
  if (!graphRagEnabled.value) return '默认关闭：走向量/ Agentic 路径'
  const map: Record<GraphRagMode, string> = {
    hybrid: 'hybrid：local + global 合并（推荐）',
    local:  'local：从单实体邻域展开，聚焦型多跳',
    global: 'global：社区级聚合，主题/趋势',
    naive:  'naive：纯向量（LightRAG 内置），与 Vector RAG 近似',
    mix:    'mix：naive + hybrid 融合，覆盖最全',
  }
  return map[graphRagQueryMode.value] || ''
})

let _graphRagPollTimer: number | null = null

const fetchGraphRagConfig = async () => {
  try {
    const res = await fetch('http://localhost:8000/api/embedding/graph-rag')
    if (res.ok) {
      const data = await res.json()
      graphRagEnabled.value = !!data.enabled
      if (typeof data.query_mode === 'string') {
        graphRagQueryMode.value = data.query_mode as GraphRagMode
      }
    }
  } catch (e) { console.error('fetch graph-rag config failed', e) }
}

const fetchGraphRagStats = async () => {
  try {
    const res = await fetch('http://localhost:8000/api/embedding/graph-rag/stats')
    if (res.ok) graphRagStats.value = await res.json()
  } catch (e) { console.error('fetch graph-rag stats failed', e) }
}

const fetchGraphRagBuildStatus = async () => {
  try {
    const res = await fetch('http://localhost:8000/api/embedding/graph-rag/build/status')
    if (res.ok) {
      const data = await res.json()
      graphRagBuildState.value = {
        status: data.status || 'idle',
        phase: data.phase ?? null,
        total: data.total || 0,
        processed: data.processed || 0,
        current_doc: data.current_doc ?? null,
        message: data.message ?? null,
      }
    }
  } catch (e) { /* silent */ }
}

const startGraphRagPolling = () => {
  if (_graphRagPollTimer !== null) return
  _graphRagPollTimer = window.setInterval(async () => {
    await fetchGraphRagBuildStatus()
    if (graphRagBuildState.value.status !== 'running') {
      stopGraphRagPolling()
      await fetchGraphRagStats()
    }
  }, 1500)
}
const stopGraphRagPolling = () => {
  if (_graphRagPollTimer !== null) {
    clearInterval(_graphRagPollTimer)
    _graphRagPollTimer = null
  }
}

watch(embeddingReady, (ready, prev) => {
  if (ready && !prev) {
    fetchGraphRagConfig(); fetchGraphRagStats(); fetchGraphRagBuildStatus()
  }
})

const handleGraphRagToggle = async (): Promise<boolean> => {
  const turningOn = !graphRagEnabled.value
  try {
    const res = await fetch('http://localhost:8000/api/embedding/graph-rag', {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ enabled: turningOn }),
    })
    if (!res.ok) {
      const err = await res.json().catch(() => ({}))
      ElMessage.error(typeof err.detail === 'string' ? err.detail : 'Graph RAG 切换失败')
      return false
    }
    const data = await res.json()
    ElMessage.success(data.message || (turningOn ? 'Graph RAG 已启用' : 'Graph RAG 已关闭'))
    return true
  } catch (e) {
    ElMessage.error('Graph RAG 切换失败')
    return false
  }
}

const handleGraphRagModeChange = async (value: string | number | boolean | (string | number | boolean)[]) => {
  const target = String(value) as GraphRagMode
  const old = graphRagQueryMode.value
  try {
    const res = await fetch('http://localhost:8000/api/embedding/graph-rag', {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ query_mode: target }),
    })
    if (!res.ok) {
      const err = await res.json().catch(() => ({}))
      ElMessage.error(typeof err.detail === 'string' ? err.detail : '切换查询模式失败')
      graphRagQueryMode.value = old
      return
    }
    ElMessage.success(`Graph RAG 查询模式：${target}`)
  } catch (e) {
    ElMessage.error('切换查询模式失败')
    graphRagQueryMode.value = old
  }
}

const handleGraphRagBuild = async () => {
  const confirmed = await ElMessageBox.confirm(
    '将为全部已入库文档构建 Graph RAG 索引（LightRAG）。\n\n' +
    '• 每个文档需多次调用 LLM 抽取实体关系，单篇预估耗时 1-5 分钟、成本数元到数十元。\n' +
    '• LightRAG 自带 LLM cache，重复构建几乎免费。\n' +
    '• 已入图的文档会自动跳过（增量）。',
    '构建 Graph RAG 索引',
    { confirmButtonText: '开始构建', cancelButtonText: '取消', type: 'warning' },
  ).catch(() => false)
  if (!confirmed) return

  try {
    const res = await fetch('http://localhost:8000/api/embedding/graph-rag/build', { method: 'POST' })
    if (!res.ok) {
      const err = await res.json().catch(() => ({}))
      ElMessage.error(err.detail?.message || '启动构建失败')
      return
    }
    ElMessage.success('构建已启动')
    startGraphRagPolling()
  } catch (e) {
    ElMessage.error('启动构建失败')
  }
}

const handleGraphRagClear = async () => {
  const confirmed = await ElMessageBox.confirm(
    '将清空 backend/data/lightrag/ 下所有图索引文件。\n' +
    '不会影响向量库（Qdrant）与 MongoDB 文档记录。',
    '清空 Graph RAG 索引',
    { confirmButtonText: '确认清空', cancelButtonText: '取消', type: 'warning' },
  ).catch(() => false)
  if (!confirmed) return

  try {
    const res = await fetch('http://localhost:8000/api/embedding/graph-rag/clear', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ confirm: true }),
    })
    if (!res.ok) {
      const err = await res.json().catch(() => ({}))
      ElMessage.error(err.detail?.message || '清空失败')
      return
    }
    ElMessage.success('索引已清空')
    // 清空后 Graph RAG 自动关闭（后端开关保留，但无数据可查 → 前端强制 off）
    if (graphRagEnabled.value) {
      await handleGraphRagToggle()
    }
    await fetchGraphRagStats()
    await fetchGraphRagBuildStatus()
  } catch (e) {
    ElMessage.error('清空失败')
  }
}

const handleRerankerToggle = async (): Promise<boolean> => {
  const turningOn = !store.useReranker
  rerankerLoading.value = true
  try {
    const url = turningOn
      ? 'http://localhost:8000/api/embedding/reranker/load'
      : 'http://localhost:8000/api/embedding/reranker/unload'
    const res = await fetch(url, { method: 'POST' })
    if (!res.ok) {
      const err = await res.json().catch(() => ({}))
      const msg = typeof err.detail === 'string' ? err.detail : err.detail?.message ?? (turningOn ? 'Reranker 加载失败' : 'Reranker 卸载失败')
      ElMessage.error(msg)
      return false
    }
    store.rerankerLoaded = turningOn
    ElMessage.success(turningOn ? 'Reranker 已加载到显存' : 'Reranker 已卸载，显存已释放')
    await fetchSystemInfo()
    return true
  } catch (e) {
    ElMessage.error(turningOn ? 'Reranker 加载失败' : 'Reranker 卸载失败')
    return false
  } finally {
    rerankerLoading.value = false
  }
}

// ── 系统信息 ────────────────────────────────────────────────────────

const fetchSystemInfo = async () => {
  loadingInfo.value = true
  try {
    const [infoRes, strategyRes] = await Promise.all([
      fetch('http://localhost:8000/api/embedding/system-info'),
      fetch('http://localhost:8000/api/embedding/rag-strategy'),
    ])
    if (infoRes.ok) {
      sysInfo.value = await infoRes.json()
      embeddingConfig.value.use_gpu = sysInfo.value?.current_config?.use_gpu ?? true
    }
    if (strategyRes.ok) {
      ragStrategy.value = await strategyRes.json()
    }
  } catch (e) {
    console.error('Failed to fetch system info', e)
  } finally {
    loadingInfo.value = false
  }
}

// ── 下载 ────────────────────────────────────────────────────────────

const startDownload = async (resume: boolean = true) => {
  try {
    const url = `http://localhost:8000/api/embedding/download?resume=${resume}`
    const res = await fetch(url, { method: 'POST' })
    const data = await res.json()
    if (!resume) {
      ElMessage.info('已清空旧数据，重新开始下载…')
    } else {
      ElMessage.info(data.message || '下载已开始')
    }
    startDownloadPolling()
  } catch (e) {
    ElMessage.error('启动下载失败')
  }
}

const cancelDownload = async () => {
  try {
    const res = await fetch('http://localhost:8000/api/embedding/download/cancel', { method: 'POST' })
    const data = await res.json()
    ElMessage.warning(data.message || '停止信号已发送')
  } catch (e) {
    ElMessage.error('停止失败')
  }
}

const estimateRemaining = () => {
  const speed = downloadState.value.speed_mbps
  if (speed <= 0) return '计算中…'
  const remaining = (downloadState.value.total_mb - downloadState.value.downloaded_mb) / speed
  if (remaining < 60) return `${Math.round(remaining)} 秒`
  if (remaining < 3600) return `${Math.round(remaining / 60)} 分钟`
  return `${(remaining / 3600).toFixed(1)} 小时`
}

const fetchDownloadStatus = async () => {
  try {
    const res = await fetch('http://localhost:8000/api/embedding/download/status')
    if (res.ok) {
      downloadState.value = await res.json()
      if (downloadState.value.status === 'done') {
        stopDownloadPolling()
        await fetchSystemInfo()
        ElMessage.success('BGE-M3 下载完成！点击"加载模型"激活。')
      } else if (downloadState.value.status === 'paused') {
        stopDownloadPolling()
        ElMessage.warning(`下载已暂停（${downloadState.value.downloaded_mb.toFixed(0)} / ${downloadState.value.total_mb} MB）。可点击"继续下载"或"重新下载"。`)
      } else if (downloadState.value.status === 'failed') {
        stopDownloadPolling()
        ElMessage.error(`下载失败：${downloadState.value.error}`)
      }
    }
  } catch (e) {
    console.error('Failed to fetch download status', e)
  }
}

const startDownloadPolling = () => {
  if (downloadPollTimer) return
  downloadPollTimer = setInterval(fetchDownloadStatus, 2000)
}

const stopDownloadPolling = () => {
  if (downloadPollTimer) {
    clearInterval(downloadPollTimer)
    downloadPollTimer = null
  }
}

// ── 激活模型 ────────────────────────────────────────────────────────

const activateModel = async () => {
  activating.value = true
  try {
    const res = await fetch('http://localhost:8000/api/embedding/activate', { method: 'POST' })
    const data = await res.json()
    if (res.ok) {
      ElMessage.success('模型加载成功，Embedding 服务已就绪！')
      await fetchSystemInfo()
      await store.fetchEmbeddingStatus()
    } else {
      ElMessage.error(data.detail || '模型加载失败')
    }
  } catch (e) {
    ElMessage.error('激活失败')
  } finally {
    activating.value = false
  }
}

// ── 配置保存 ─────────────────────────────────────────────────────────

const saveConfig = async () => {
  try {
    const res = await fetch('http://localhost:8000/api/embedding/config', {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ use_gpu: embeddingConfig.value.use_gpu }),
    })
    const data = await res.json()
    if (res.ok) {
      if (data.needs_revectorize) {
        ElMessage.warning('模型已切换，所有文档将重新向量化。')
      } else {
        ElMessage.success('配置已保存')
      }
      await fetchSystemInfo()
      await fetchDocuments()
    }
  } catch (e) {
    ElMessage.error('保存配置失败')
  }
}

// ── 复制安装命令 ─────────────────────────────────────────────────────

const copyInstallCmd = () => {
  navigator.clipboard.writeText(
    'pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121'
  )
  ElMessage.success('命令已复制（安装后需重启后端服务）')
}

// ── 文档操作 ─────────────────────────────────────────────────────────

const getFileIcon = (ext: string) => {
  if (!ext) return Document
  ext = ext.toLowerCase()
  if (['.pdf'].includes(ext)) return Management
  if (['.md', '.txt', '.csv'].includes(ext)) return List
  if (['.doc', '.docx'].includes(ext)) return Tickets
  if (['.xlsx', '.xls'].includes(ext)) return Grid
  if (['.pptx'].includes(ext)) return Management
  if (['.epub'].includes(ext)) return Reading
  if (['.jpg', '.jpeg', '.png', '.gif', '.svg'].includes(ext)) return Picture
  return Document
}

const getFileIconColor = (ext: string) => {
  if (!ext) return 'icon-default'
  ext = ext.toLowerCase()
  if (['.pdf'].includes(ext)) return 'icon-pdf'
  if (['.md', '.txt', '.csv'].includes(ext)) return 'icon-text'
  if (['.jpg', '.jpeg', '.png', '.gif', '.svg'].includes(ext)) return 'icon-image'
  if (['.doc', '.docx'].includes(ext)) return 'icon-word'
  if (['.xlsx', '.xls'].includes(ext)) return 'icon-excel'
  if (['.pptx'].includes(ext)) return 'icon-pptx'
  if (['.epub'].includes(ext)) return 'icon-epub'
  return 'icon-default'
}

const fetchDocuments = async () => {
  loading.value = true
  try {
    const res = await fetch('http://localhost:8000/api/documents')
    if (res.ok) {
      documents.value = await res.json()
    }
  } catch (e) {
    console.error('Failed to fetch documents', e)
    ElMessage.error('Failed to load documents')
  } finally {
    loading.value = false
  }
}

const deleteDocument = async (doc: DocumentItem) => {
  try {
    await ElMessageBox.confirm(
      `Are you sure you want to delete "${doc.filename}"? This will also remove it from the AI's knowledge base.`,
      'Warning',
      { confirmButtonText: 'Delete', cancelButtonText: 'Cancel', type: 'warning' }
    )
    loading.value = true
    const res = await fetch(`http://localhost:8000/api/documents/${doc.file_id}`, { method: 'DELETE' })
    if (res.ok) {
      ElMessage.success('Document deleted successfully')
      await fetchDocuments()
    } else {
      throw new Error('Failed to delete')
    }
  } catch (e) {
    if (e !== 'cancel') {
      console.error('Failed to delete document', e)
      ElMessage.error('Failed to delete document')
    }
  } finally {
    loading.value = false
  }
}

const revectorizeDocument = async (doc: DocumentItem) => {
  try {
    loading.value = true
    const res = await fetch(`http://localhost:8000/api/documents/${doc.file_id}/revectorize`, { method: 'POST' })
    if (res.ok) {
      const data = await res.json()
      ElMessage.success(`Re-vectorized successfully (${data.details.chunks} chunks generated)`)
      await fetchDocuments()
    } else {
      throw new Error('Failed to revectorize')
    }
  } catch (e) {
    console.error('Failed to revectorize document', e)
    ElMessage.error('Failed to revectorize document')
  } finally {
    loading.value = false
  }
}

const handleFileChange = async (file: any) => {
  if (!file.raw) return
  if (!embeddingReady.value) {
    ElMessage.warning('Embedding 模型未就绪，请先完成上方配置。')
    return
  }
  uploading.value = true
  try {
    const res = await store.uploadFile(file.raw)
    ElMessage.success(`已上传 ${res.details?.filename ?? file.raw.name}，正在后台向量化…`)
    await fetchDocuments()
  } catch (e) {
    ElMessage.error('Upload failed')
  } finally {
    uploading.value = false
  }
}

const goBack = () => router.push('/')

const formatBytes = (bytes: number, decimals = 2) => {
  if (!+bytes) return '0 Bytes'
  const k = 1024
  const dm = decimals < 0 ? 0 : decimals
  const sizes = ['Bytes', 'KB', 'MB', 'GB', 'TB', 'PB', 'EB', 'ZB', 'YB']
  const i = Math.floor(Math.log(bytes) / Math.log(k))
  return `${parseFloat((bytes / Math.pow(k, i)).toFixed(dm))} ${sizes[i]}`
}

const formatDate = (isoStr: string | null) => {
  if (!isoStr) return '-'
  const date = new Date(isoStr)
  if (isNaN(date.getTime())) return '-'
  return date.toLocaleString('zh-CN')
}

const statusTagType = (status: string) => {
  const map: Record<string, string> = {
    pending: 'info', processing: 'warning', done: 'success', failed: 'danger',
  }
  return map[status] || 'info'
}

const statusLabel = (status: string) => {
  const map: Record<string, string> = {
    pending: '等待向量化', processing: '向量化中…', done: '已就绪', failed: '向量化失败',
  }
  return map[status] || status
}

onMounted(async () => {
  await fetchSystemInfo()
  await fetchDocuments()
  await fetchSearchMode()
  await fetchMultiQuery()
  await fetchAgenticRagMode()
  await fetchGraphRagConfig()
  await fetchGraphRagStats()
  await fetchGraphRagBuildStatus()
  if (graphRagBuildState.value.status === 'running') {
    startGraphRagPolling()
  }
  // 如果后端正在下载中，恢复前端轮询
  const statusRes = await fetch('http://localhost:8000/api/embedding/download/status')
  if (statusRes.ok) {
    const state = await statusRes.json()
    downloadState.value = state
    if (state.status === 'downloading') {
      startDownloadPolling()
    }
  }
})

onUnmounted(() => {
  stopDownloadPolling()
  stopGraphRagPolling()
})
</script>

<style scoped>
.knowledge-base-layout {
  height: 100vh;
  background-color: var(--bg-primary);
}
.el-container { height: 100%; }
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
  letter-spacing: -0.02em;
}
.el-main { padding: 24px 40px; }
.box-card {
  max-width: 1000px;
  margin: 0 auto;
  border-radius: var(--radius-lg);
  border: 1px solid var(--border-color);
  box-shadow: var(--shadow-sm);
}
.env-card {}
.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-weight: 600;
  font-size: 1.1rem;
}
.env-grid {
  display: flex;
  flex-direction: column;
  gap: 14px;
}
.env-item {
  display: flex;
  align-items: flex-start;
  gap: 12px;
}
.env-full { width: 100%; }
.env-label {
  min-width: 110px;
  font-size: 13px;
  font-weight: 600;
  color: var(--text-secondary);
  padding-top: 2px;
}
.env-value {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 8px;
}
.env-sub {
  font-size: 12px;
  color: var(--text-secondary);
}
.install-hint {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  color: var(--text-secondary);
  flex-wrap: wrap;
}
.download-progress-row {
  display: flex;
  align-items: center;
  gap: 10px;
  flex: 1;
  flex-wrap: wrap;
}
.download-progress-bar {
  width: 100%;
  max-width: 340px;
}
.download-meta {
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 120px;
}
.download-speed {
  font-size: 12px;
  color: var(--accent-primary);
  font-weight: 500;
}
.code-snippet {
  background: rgba(0,0,0,0.06);
  border-radius: 4px;
  padding: 2px 8px;
  font-family: monospace;
  font-size: 11px;
  cursor: pointer;
  user-select: all;
}
.file-name-cell { display: flex; align-items: center; gap: 8px; }
.file-icon { font-size: 18px; }
.icon-pdf   { color: #E3000F; }
.icon-text  { color: #2563EB; }
.icon-image { color: #16A34A; }
.icon-word  { color: #2B579A; }
.icon-excel { color: #217346; }
.icon-pptx  { color: #D04430; }
.icon-epub  { color: #7C3AED; }
.icon-default { color: #64748B; }
</style>
