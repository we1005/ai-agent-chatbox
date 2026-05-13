<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { RefreshRight, CircleCheck, CircleClose, Connection } from '@element-plus/icons-vue'
import { Switch } from '@/components/ui/switch'

interface Health {
  redis: { ok: boolean; ping_ms: number | null; error: string | null }
  celery: { ok: boolean; workers: number; worker_names: string[]; error: string | null }
  flower: { ok: boolean; url: string; error: string | null }
}

const health = ref<Health | null>(null)
const healthLoading = ref(false)
const celeryEnabled = ref(false)
const switchBusy = ref(false)

const BACKEND = 'http://localhost:8000'

async function fetchHealth() {
  healthLoading.value = true
  try {
    const r = await fetch(`${BACKEND}/api/embedding/celery/health`)
    health.value = await r.json()
  } catch (e: any) {
    health.value = null
    ElMessage.error(`健康检查请求失败：${e?.message ?? e}`)
  } finally {
    healthLoading.value = false
  }
}

async function fetchCeleryStatus() {
  try {
    const r = await fetch(`${BACKEND}/api/embedding/celery`)
    if (r.ok) {
      const data = await r.json()
      celeryEnabled.value = data.enabled
    }
  } catch (e) {
    // silent — backend 未起时也能看到页
  }
}

async function toggleCelery(target: boolean) {
  if (switchBusy.value) return
  switchBusy.value = true
  const prev = celeryEnabled.value

  try {
    const r = await fetch(`${BACKEND}/api/embedding/celery`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ enabled: target }),
    })
    if (!r.ok) {
      const body = await r.json().catch(() => ({ detail: `HTTP ${r.status}` }))
      const detail = body.detail ?? body
      // 回滚开关视觉
      celeryEnabled.value = prev
      if (typeof detail === 'object' && detail.message) {
        ElMessageBox.alert(
          `${detail.hint || ''}\n\n健康检查详情：\n${JSON.stringify(detail.health, null, 2)}`,
          detail.message,
          { type: 'warning', confirmButtonText: '好的' }
        )
      } else {
        ElMessage.error(`切换失败：${JSON.stringify(detail)}`)
      }
    } else {
      const data = await r.json()
      celeryEnabled.value = data.enabled
      ElMessage.success(data.message)
    }
  } catch (e: any) {
    celeryEnabled.value = prev
    ElMessage.error(`网络错误：${e?.message ?? e}`)
  } finally {
    switchBusy.value = false
  }
}

function openFlower() {
  window.open('http://localhost:5555', '_blank')
}

// 30 秒自动刷新（仅 active tab）
let pollTimer: ReturnType<typeof setInterval> | null = null
onMounted(() => {
  fetchHealth()
  fetchCeleryStatus()
  pollTimer = setInterval(fetchHealth, 30_000)
})
onUnmounted(() => {
  if (pollTimer) clearInterval(pollTimer)
})

const allOK = computed(() =>
  health.value?.redis.ok && health.value?.celery.ok
)
</script>

<template>
  <div class="infra-page">
    <header class="page-head">
      <div>
        <h1>🔌 基础设施</h1>
        <p class="sub">Celery 异步向量化 · Redis 队列 · Flower 监控</p>
      </div>
      <button class="btn-refresh" :disabled="healthLoading" @click="fetchHealth">
        <el-icon :class="{ 'spin': healthLoading }"><RefreshRight /></el-icon>
        刷新
      </button>
    </header>

    <!-- 三张健康卡 -->
    <section class="health-grid">
      <div class="health-card" :class="{ ok: health?.redis.ok, fail: health && !health.redis.ok }">
        <div class="card-head">
          <div class="card-icon">R</div>
          <div>
            <div class="card-title">Redis</div>
            <div class="card-sub">localhost:6379 · broker db0 · backend db1</div>
          </div>
          <div class="status">
            <el-icon v-if="health?.redis.ok" class="dot ok"><CircleCheck /></el-icon>
            <el-icon v-else class="dot fail"><CircleClose /></el-icon>
          </div>
        </div>
        <div class="card-body">
          <template v-if="health?.redis.ok">
            <span class="mono">ping: {{ health.redis.ping_ms }}ms</span>
            <span class="hint">AOF 建议开启：bash backend/start-redis-with-aof.sh</span>
          </template>
          <template v-else>
            <span class="err">{{ health?.redis.error ?? '未检测' }}</span>
            <span class="hint">启动：brew services start redis</span>
          </template>
        </div>
      </div>

      <div class="health-card" :class="{ ok: health?.celery.ok, fail: health && !health.celery.ok }">
        <div class="card-head">
          <div class="card-icon">C</div>
          <div>
            <div class="card-title">Celery Worker</div>
            <div class="card-sub">xuanjian.vectorize · Docker 容器</div>
          </div>
          <div class="status">
            <el-icon v-if="health?.celery.ok" class="dot ok"><CircleCheck /></el-icon>
            <el-icon v-else class="dot fail"><CircleClose /></el-icon>
          </div>
        </div>
        <div class="card-body">
          <template v-if="health?.celery.ok">
            <span class="mono">workers: {{ health.celery.workers }}</span>
            <span class="hint" v-if="health.celery.worker_names.length">
              {{ health.celery.worker_names[0] }}
              <span v-if="health.celery.worker_names.length > 1">
                +{{ health.celery.worker_names.length - 1 }}
              </span>
            </span>
          </template>
          <template v-else>
            <span class="err">{{ health?.celery.error ?? '未检测' }}</span>
            <span class="hint">启动：cd backend && docker compose -f docker-compose.celery.yml up -d</span>
          </template>
        </div>
      </div>

      <div class="health-card" :class="{ ok: health?.flower.ok, fail: health && !health.flower.ok }">
        <div class="card-head">
          <div class="card-icon">🌸</div>
          <div>
            <div class="card-title">Flower</div>
            <div class="card-sub">监控 dashboard · :5555</div>
          </div>
          <div class="status">
            <el-icon v-if="health?.flower.ok" class="dot ok"><CircleCheck /></el-icon>
            <el-icon v-else class="dot fail"><CircleClose /></el-icon>
          </div>
        </div>
        <div class="card-body">
          <template v-if="health?.flower.ok">
            <span class="hint">admin / xuanjian</span>
            <button class="btn-flower" @click="openFlower">
              <el-icon><Connection /></el-icon>
              打开 Flower
            </button>
          </template>
          <template v-else>
            <span class="err">{{ health?.flower.error ?? '未检测' }}</span>
            <span class="hint">docker compose 启动后自动可用</span>
          </template>
        </div>
      </div>
    </section>

    <!-- 开关区 -->
    <section class="toggle-section" :class="{ disabled: !allOK }">
      <div class="toggle-row">
        <div>
          <div class="toggle-title">Celery 异步向量化</div>
          <div class="toggle-desc">
            开启后上传文档走 Redis 队列，Docker worker 按 concurrency=2 消费 —— 削峰填谷，
            backend 重启队列不丢。关闭则走原有 <code>asyncio.to_thread</code> 路径（零破坏）。
          </div>
          <div class="toggle-meta">
            <span class="chip">默认 OFF</span>
            <span class="chip">仅运行时开关</span>
            <span class="chip">config: embedding_config.json</span>
          </div>
        </div>
        <Switch
          :model-value="celeryEnabled"
          :disabled="switchBusy || (!celeryEnabled && !allOK)"
          @update:model-value="toggleCelery"
        />
      </div>
      <div v-if="!allOK && !celeryEnabled" class="warn-banner">
        ⚠️ Redis 或 Worker 未就绪，无法开启。请先完成上方基础设施检查。
      </div>
    </section>

    <!-- 架构说明 -->
    <section class="arch-section">
      <h3>📐 架构 · 削峰填谷不是"算力搬家"</h3>
      <pre class="arch-ascii">
upload → backend → task.delay(file_id) → Redis queue
                                              ↓
                                    Celery Worker (~100MB Docker)
                                    concurrency=2 ← 水龙头开度
                                              ↓
                              HTTP POST /api/internal/vectorize
                                              ↓
                            backend 的 _do_vectorize_sync()
                              BGE-M3 仅主进程加载一份</pre>
      <p class="note">
        Worker 容器 <strong>不加载</strong> BGE-M3；削峰阀门 = worker concurrency。
        详见 <code>analysis-for-backend/celery-module.md</code>。
      </p>
    </section>
  </div>
</template>

<style scoped>
.infra-page {
  max-width: 1080px;
  margin: 0 auto;
  padding: 28px 32px 60px;
}

.page-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 24px;
}
.page-head h1 {
  font-size: 22px;
  font-weight: 700;
  color: #111827;
  margin: 0;
}
.sub { color: #64748b; font-size: 13px; margin-top: 4px; }

.btn-refresh {
  display: inline-flex; align-items: center; gap: 6px;
  padding: 6px 14px; border-radius: 8px;
  border: 1px solid #e2e8f0; background: #fff;
  font-size: 13px; color: #475569; cursor: pointer;
  transition: all 0.15s;
}
.btn-refresh:hover { border-color: #94a3b8; color: #111827; }
.btn-refresh:disabled { opacity: 0.6; cursor: not-allowed; }
.spin { animation: spin 0.8s linear infinite; }
@keyframes spin { to { transform: rotate(360deg); } }

.health-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 14px;
  margin-bottom: 24px;
}
@media (max-width: 900px) {
  .health-grid { grid-template-columns: 1fr; }
}

.health-card {
  background: white;
  border: 1px solid #e2e8f0;
  border-radius: 12px;
  padding: 16px;
  transition: all 0.2s;
}
.health-card.ok { border-left: 3px solid #10b981; }
.health-card.fail { border-left: 3px solid #ef4444; }

.card-head { display: flex; align-items: center; gap: 10px; }
.card-icon {
  width: 36px; height: 36px;
  border-radius: 10px;
  background: #f1f5f9;
  display: grid; place-items: center;
  font-weight: 700;
  color: #1e293b;
  flex-shrink: 0;
}
.card-title { font-weight: 600; font-size: 14px; color: #0f172a; }
.card-sub { font-size: 11.5px; color: #94a3b8; margin-top: 2px; }
.status { margin-left: auto; }
.dot { font-size: 22px; }
.dot.ok { color: #10b981; }
.dot.fail { color: #ef4444; }

.card-body {
  margin-top: 12px;
  display: flex; flex-direction: column; gap: 4px;
  font-size: 12px;
}
.mono { font-family: 'SF Mono', Menlo, monospace; color: #0f172a; }
.err { color: #ef4444; font-size: 11.5px; word-break: break-all; }
.hint { color: #94a3b8; font-size: 11.5px; }

.btn-flower {
  display: inline-flex; align-items: center; gap: 4px;
  padding: 4px 10px; border-radius: 6px;
  border: 1px solid #e2e8f0; background: white;
  font-size: 12px; color: #475569; cursor: pointer;
  margin-top: 4px; align-self: flex-start;
}
.btn-flower:hover { border-color: #ec4899; color: #ec4899; }

.toggle-section {
  background: white;
  border: 1px solid #e2e8f0;
  border-radius: 12px;
  padding: 18px 22px;
  margin-bottom: 24px;
}
.toggle-section.disabled { opacity: 0.7; }

.toggle-row {
  display: flex; align-items: center; justify-content: space-between; gap: 20px;
}
.toggle-title { font-size: 15px; font-weight: 600; color: #0f172a; }
.toggle-desc {
  font-size: 13px; color: #475569; margin-top: 6px; line-height: 1.6;
  max-width: 680px;
}
.toggle-desc code {
  background: #f1f5f9; padding: 1px 6px; border-radius: 3px;
  font-family: 'SF Mono', Menlo, monospace; font-size: 11.5px;
}
.toggle-meta { display: flex; gap: 6px; margin-top: 10px; flex-wrap: wrap; }
.chip {
  font-size: 10px;
  padding: 2px 8px;
  border-radius: 10px;
  background: #f1f5f9;
  color: #64748b;
  font-family: 'SF Mono', Menlo, monospace;
}

.warn-banner {
  margin-top: 12px;
  padding: 10px 14px;
  background: #fffbeb;
  border: 1px solid #fde68a;
  border-radius: 8px;
  color: #92400e;
  font-size: 13px;
}

.arch-section {
  background: #0f172a;
  color: #e2e8f0;
  border-radius: 12px;
  padding: 20px 24px;
}
.arch-section h3 { font-size: 14px; font-weight: 600; margin: 0 0 10px; color: #f1f5f9; }
.arch-ascii {
  font-family: 'SF Mono', Menlo, monospace;
  font-size: 12px;
  line-height: 1.6;
  color: #94a3b8;
  margin: 8px 0 12px;
  white-space: pre;
  overflow-x: auto;
}
.note { font-size: 12.5px; color: #94a3b8; margin: 0; }
.note code {
  background: rgba(255,255,255,0.08);
  padding: 1px 6px;
  border-radius: 3px;
  font-family: 'SF Mono', monospace;
  font-size: 11px;
}
.note strong { color: #f1f5f9; }
</style>
