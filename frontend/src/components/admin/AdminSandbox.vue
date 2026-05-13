<template>
  <div class="sandbox">
    <div class="page-header">
      <h1>调试沙盒</h1>
      <p class="subtitle">在发布前测试 Prompt 和参数组合的效果，支持多模型并发对比</p>
    </div>

    <div class="sandbox-layout">
      <!-- 左侧配置区 -->
      <div class="config-col">
        <!-- 模型选择 -->
        <div class="card config-card">
          <div class="config-title">测试配置</div>

          <div class="form-item">
            <label>主模型</label>
            <select class="form-select" v-model="primaryModel">
              <option v-for="m in modelOptions" :key="m.id" :value="m.id">{{ m.label }}</option>
            </select>
          </div>

          <div class="form-item">
            <label>Temperature</label>
            <div class="slider-row">
              <input type="range" class="range-slider" v-model.number="tempVal" :min="0" :max="2" :step="0.1" />
              <span class="slider-val">{{ tempVal }}</span>
            </div>
          </div>

          <div class="form-item">
            <label>Max Tokens</label>
            <input type="number" class="form-input-sm" v-model.number="maxTokensVal" :min="256" :max="32768" />
          </div>

          <div class="form-item">
            <label>System Prompt</label>
            <textarea class="config-textarea" v-model="systemPrompt" rows="5"
              placeholder="输入 System Prompt..."></textarea>
          </div>

          <div class="divider"></div>

          <div class="compare-section">
            <div class="compare-header">
              <span>对比模型</span>
              <button class="add-compare-btn" @click="addCompareModel" v-if="compareModels.length < 2">+</button>
            </div>
            <div class="compare-list">
              <div class="compare-item" v-for="(cm, i) in compareModels" :key="i">
                <select class="form-select sm" v-model="cm.model">
                  <option v-for="m in modelOptions" :key="m.id" :value="m.id">{{ m.label }}</option>
                </select>
                <button class="remove-btn" @click="compareModels.splice(i, 1)">×</button>
              </div>
              <div class="empty-compare" v-if="!compareModels.length">点击 + 添加对比模型</div>
            </div>
          </div>
        </div>

        <!-- Token 预估 -->
        <div class="card est-card">
          <div class="config-title">Token 预估</div>
          <div class="est-row">
            <span>System Prompt</span>
            <span class="est-val">≈ {{ Math.round(systemPrompt.length * 0.6) }} tokens</span>
          </div>
          <div class="est-row">
            <span>User Message</span>
            <span class="est-val">≈ {{ Math.round(userMessage.length * 0.6) }} tokens</span>
          </div>
          <div class="est-row total">
            <span>预计输入总量</span>
            <span class="est-val">≈ {{ Math.round((systemPrompt.length + userMessage.length) * 0.6) }} tokens</span>
          </div>
          <div class="est-cost">
            预计费用 ≈ ¥ {{ estimatedCost }}
          </div>
        </div>
      </div>

      <!-- 右侧输入输出区 -->
      <div class="io-col">
        <!-- 用户输入 -->
        <div class="card input-card">
          <div class="config-title">测试消息</div>
          <textarea
            class="user-textarea"
            v-model="userMessage"
            rows="5"
            placeholder="输入测试用的用户消息..."
          ></textarea>
          <div class="input-actions">
            <div class="quick-prompts">
              <span class="qp-label">快速测试：</span>
              <button class="qp-btn" v-for="qp in quickPrompts" :key="qp" @click="userMessage = qp">{{ qp }}</button>
            </div>
            <button class="run-btn" @click="runTest" :disabled="isRunning">
              <span v-if="!isRunning">▶ 发送测试</span>
              <span v-else class="running-indicator">⟳ 生成中...</span>
            </button>
          </div>
        </div>

        <!-- 输出区域（主模型） -->
        <div class="output-grid" :class="{ 'with-compare': compareModels.length > 0 }">
          <!-- 主模型输出 -->
          <div class="output-card" :class="{ active: responses[0]?.content }">
            <div class="output-header">
              <span class="output-model" :style="{ color: getModelColor(primaryModel) }">
                {{ getModelLabel(primaryModel) }}
              </span>
              <div class="output-meta" v-if="responses[0]">
                <span class="meta-chip">{{ responses[0].time }}s</span>
                <span class="meta-chip">{{ responses[0].tokens }} tokens</span>
                <span class="meta-chip cost">¥ {{ responses[0].cost }}</span>
              </div>
            </div>
            <div class="output-body">
              <div v-if="responses[0]?.reasoning" class="reasoning-block">
                <div class="rb-header">💭 思考过程</div>
                <div class="rb-content">{{ responses[0].reasoning }}</div>
              </div>
              <div class="output-text" v-if="responses[0]?.content">
                {{ responses[0].content }}
              </div>
              <div class="output-placeholder" v-else-if="!isRunning">
                <span>点击"发送测试"查看输出</span>
              </div>
              <div class="output-loading" v-else-if="isRunning && !responses[0]?.content">
                <span class="dot-pulse">●</span>
                <span class="dot-pulse" style="animation-delay:0.2s">●</span>
                <span class="dot-pulse" style="animation-delay:0.4s">●</span>
              </div>
            </div>
          </div>

          <!-- 对比模型输出 -->
          <div
            v-for="(cm, i) in compareModels"
            :key="i"
            class="output-card compare"
            :class="{ active: responses[i+1]?.content }"
          >
            <div class="output-header">
              <span class="output-model" :style="{ color: getModelColor(cm.model) }">
                {{ getModelLabel(cm.model) }}
                <span class="compare-badge">对比</span>
              </span>
              <div class="output-meta" v-if="responses[i+1]">
                <span class="meta-chip">{{ responses[i+1].time }}s</span>
                <span class="meta-chip">{{ responses[i+1].tokens }} tokens</span>
                <span class="meta-chip cost">¥ {{ responses[i+1].cost }}</span>
              </div>
            </div>
            <div class="output-body">
              <div class="output-text" v-if="responses[i+1]?.content">{{ responses[i+1].content }}</div>
              <div class="output-placeholder" v-else-if="!isRunning"><span>等待对比输出...</span></div>
              <div class="output-loading" v-else>
                <span class="dot-pulse">●</span>
                <span class="dot-pulse" style="animation-delay:0.2s">●</span>
                <span class="dot-pulse" style="animation-delay:0.4s">●</span>
              </div>
            </div>
          </div>
        </div>

        <!-- 历史记录 -->
        <div class="card history-card" v-if="testHistory.length">
          <div class="config-title">测试历史</div>
          <div class="history-list">
            <div class="history-item" v-for="(h, i) in testHistory.slice(0, 5)" :key="i" @click="loadHistory(h)">
              <span class="h-model" :style="{ color: getModelColor(h.model) }">{{ getModelLabel(h.model) }}</span>
              <span class="h-msg">{{ h.message.slice(0, 40) }}{{ h.message.length > 40 ? '...' : '' }}</span>
              <span class="h-time">{{ h.time }}</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'

const primaryModel = ref('kimi-k2-0905-preview')
const tempVal = ref(1.0)
const maxTokensVal = ref(4096)
const systemPrompt = ref('你是一个乐于助人的 AI 助手。')
const userMessage = ref('')
const isRunning = ref(false)
const compareModels = ref<{ model: string }[]>([])
const responses = ref<any[]>([])
const testHistory = ref<any[]>([])

const modelOptions = [
  { id: 'kimi-k2-0905-preview', label: 'Kimi K2 (0905)', color: '#10b981' },
  { id: 'deepseek-chat', label: 'DeepSeek-V3.2', color: '#2563eb' },
  { id: 'kimi-k2.5', label: 'Kimi K2.5', color: '#8b5cf6' },
  { id: 'kimi-k2-thinking', label: 'Kimi Thinking', color: '#f59e0b' },
]

const quickPrompts = [
  '解释量子纠缠',
  '用 Python 写快速排序',
  '今天天气如何？',
  '写一首关于秋天的诗',
]

const getModelColor = (id: string) => modelOptions.find(m => m.id === id)?.color || '#374151'
const getModelLabel = (id: string) => modelOptions.find(m => m.id === id)?.label || id

const estimatedCost = computed(() => {
  const tokens = (systemPrompt.value.length + userMessage.value.length) * 0.6
  return ((tokens / 1_000_000) * 3.0).toFixed(4)
})

const addCompareModel = () => {
  if (compareModels.value.length >= 2) return
  const other = modelOptions.find(m => m.id !== primaryModel.value)
  compareModels.value.push({ model: other?.id || 'deepseek-chat' })
}

const runTest = async () => {
  if (!userMessage.value.trim()) return
  isRunning.value = true
  responses.value = []

  const allModels = [primaryModel.value, ...compareModels.value.map(c => c.model)]
  responses.value = allModels.map(() => ({ content: '', reasoning: '', time: 0, tokens: 0, cost: '0.000' }))

  // 模拟实际 API 调用（demo 模式）
  const mockResponse = (modelId: string, idx: number) => {
    return new Promise<void>((resolve) => {
      const delay = 800 + Math.random() * 1200
      const isDeepSeek = modelId.includes('deepseek')
      const isThinking = modelId.includes('thinking') || modelId.includes('k2.5')

      setTimeout(() => {
        if (isThinking) {
          responses.value[idx].reasoning = '让我分析一下这个问题...\n首先，需要理解用户的真实意图...\n经过深度思考，我认为最佳方案是...'
        }
        const sampleOutputs = [
          `这是对"${userMessage.value.slice(0, 20)}..."的回答。\n\n根据您的问题，我从以下几个角度来分析：\n\n1. **核心概念**：...\n2. **实际应用**：...\n3. **注意事项**：...\n\n总结来说，这个问题涉及到多个层面...`,
          `您好！关于"${userMessage.value.slice(0, 15)}..."：\n\n这是一个很好的问题。从技术层面看，我们需要考虑：\n- 基础理论\n- 实践方法\n- 最佳实践\n\n具体来说...`,
        ]
        responses.value[idx].content = sampleOutputs[idx % 2]
        responses.value[idx].time = (delay / 1000).toFixed(1)
        responses.value[idx].tokens = Math.floor(300 + Math.random() * 500)
        responses.value[idx].cost = ((responses.value[idx].tokens / 1_000_000) * 3).toFixed(4)
        resolve()
      }, delay)
    })
  }

  try {
    await Promise.all(allModels.map((m, i) => mockResponse(m, i)))
    testHistory.value.unshift({
      model: primaryModel.value,
      message: userMessage.value,
      time: new Date().toLocaleTimeString('zh-CN'),
    })
  } finally {
    isRunning.value = false
  }
}

const loadHistory = (h: any) => {
  userMessage.value = h.message
  primaryModel.value = h.model
  responses.value = []
}
</script>

<style scoped>
.sandbox { padding: 32px; max-width: 1300px; }
.page-header { margin-bottom: 28px; }
.page-header h1 { font-size: 26px; font-weight: 800; color: #111827; margin: 0 0 4px; }
.subtitle { color: #6b7280; font-size: 14px; margin: 0; }

.sandbox-layout { display: grid; grid-template-columns: 280px 1fr; gap: 20px; align-items: start; }

.card {
  background: white; border-radius: 14px; padding: 20px;
  box-shadow: 0 1px 4px rgba(0,0,0,0.07); border: 1px solid #f1f5f9;
}
.config-col { display: flex; flex-direction: column; gap: 16px; position: sticky; top: 20px; }
.io-col { display: flex; flex-direction: column; gap: 16px; }
.config-title { font-size: 13px; font-weight: 700; color: #374151; margin-bottom: 16px; }

/* ===== 配置区 ===== */
.form-item { display: flex; flex-direction: column; gap: 5px; margin-bottom: 14px; }
.form-item label { font-size: 12px; font-weight: 600; color: #6b7280; }

.form-select {
  border: 1px solid #e5e7eb; border-radius: 8px; padding: 7px 10px;
  font-size: 13px; color: #374151; outline: none; cursor: pointer;
  background: white;
}
.form-select:focus { border-color: #2563eb; }
.form-select.sm { flex: 1; }

.slider-row { display: flex; align-items: center; gap: 10px; }
.range-slider {
  flex: 1; -webkit-appearance: none; appearance: none;
  height: 4px; background: #e2e8f0; border-radius: 4px; outline: none;
}
.range-slider::-webkit-slider-thumb {
  -webkit-appearance: none; width: 16px; height: 16px;
  border-radius: 50%; background: #2563eb; cursor: pointer;
}
.slider-val { font-size: 13px; font-weight: 700; color: #2563eb; min-width: 28px; }

.form-input-sm {
  border: 1px solid #e5e7eb; border-radius: 8px; padding: 7px 10px;
  font-size: 13px; outline: none;
}
.form-input-sm:focus { border-color: #2563eb; }

.config-textarea {
  border: 1px solid #e5e7eb; border-radius: 8px; padding: 10px;
  font-size: 12px; color: #374151; font-family: inherit; line-height: 1.6;
  resize: vertical; outline: none; width: 100%; box-sizing: border-box;
}
.config-textarea:focus { border-color: #2563eb; }

.divider { height: 1px; background: #f1f5f9; margin: 4px 0 14px; }

.compare-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px; font-size: 12px; font-weight: 600; color: #6b7280; }
.add-compare-btn {
  width: 22px; height: 22px; border-radius: 6px;
  border: 1px solid #e5e7eb; background: white; cursor: pointer;
  color: #6b7280; font-size: 14px;
}
.add-compare-btn:hover { background: #eff6ff; border-color: #93c5fd; color: #2563eb; }

.compare-list { display: flex; flex-direction: column; gap: 8px; }
.compare-item { display: flex; gap: 8px; align-items: center; }
.remove-btn {
  width: 24px; height: 24px; border-radius: 50%; border: none;
  background: #fee2e2; color: #dc2626; cursor: pointer; font-size: 14px;
  display: flex; align-items: center; justify-content: center; flex-shrink: 0;
}
.empty-compare { font-size: 12px; color: #9ca3af; text-align: center; padding: 8px; }

/* ===== Token 预估 ===== */
.est-card { font-size: 13px; }
.est-row { display: flex; justify-content: space-between; padding: 6px 0; border-bottom: 1px solid #f9fafb; color: #6b7280; }
.est-row.total { border-bottom: none; font-weight: 700; color: #374151; padding-top: 10px; }
.est-val { font-weight: 600; }
.est-cost { margin-top: 10px; padding: 8px 12px; background: #fffbeb; border-radius: 8px; font-size: 12px; color: #92400e; font-weight: 600; }

/* ===== 输入区 ===== */
.user-textarea {
  width: 100%; box-sizing: border-box;
  border: 1px solid #e5e7eb; border-radius: 10px;
  padding: 12px 14px; font-size: 14px; color: #374151;
  font-family: inherit; line-height: 1.6; resize: vertical; outline: none;
  transition: border-color 0.15s;
  margin-bottom: 12px;
}
.user-textarea:focus { border-color: #2563eb; }

.input-actions { display: flex; justify-content: space-between; align-items: center; gap: 12px; }
.quick-prompts { display: flex; align-items: center; gap: 6px; flex-wrap: wrap; }
.qp-label { font-size: 11px; color: #9ca3af; }
.qp-btn {
  font-size: 11px; padding: 3px 9px; border-radius: 6px;
  border: 1px solid #e5e7eb; background: white; cursor: pointer; color: #6b7280;
  transition: all 0.15s;
}
.qp-btn:hover { background: #eff6ff; border-color: #93c5fd; color: #2563eb; }

.run-btn {
  padding: 10px 28px; border-radius: 10px; border: none;
  background: linear-gradient(135deg, #2563eb, #7c3aed);
  color: white; font-size: 14px; font-weight: 700;
  cursor: pointer; transition: all 0.2s; white-space: nowrap;
  box-shadow: 0 4px 12px rgba(37,99,235,0.35);
}
.run-btn:hover:not(:disabled) { transform: translateY(-1px); box-shadow: 0 6px 16px rgba(37,99,235,0.45); }
.run-btn:disabled { opacity: 0.6; cursor: not-allowed; }
.running-indicator { animation: pulse 1s ease infinite; }
@keyframes pulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.5; } }

/* ===== 输出区 ===== */
.output-grid { display: grid; grid-template-columns: 1fr; gap: 16px; }
.output-grid.with-compare { grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); }

.output-card {
  background: white; border-radius: 14px; border: 2px solid #f1f5f9;
  overflow: hidden; transition: border-color 0.2s;
}
.output-card.active { border-color: #dbeafe; }
.output-card.compare.active { border-color: #d1fae5; }

.output-header {
  display: flex; justify-content: space-between; align-items: center;
  padding: 12px 16px; background: #f8fafc; border-bottom: 1px solid #f1f5f9;
}
.output-model { font-size: 13px; font-weight: 700; display: flex; align-items: center; gap: 6px; }
.compare-badge { font-size: 10px; background: #d1fae5; color: #059669; padding: 1px 6px; border-radius: 4px; }
.output-meta { display: flex; gap: 6px; }
.meta-chip { font-size: 11px; background: #f1f5f9; color: #64748b; padding: 2px 8px; border-radius: 4px; font-weight: 600; }
.meta-chip.cost { background: #fef3c7; color: #d97706; }

.output-body { padding: 16px; min-height: 200px; }
.reasoning-block { background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px; padding: 10px 12px; margin-bottom: 12px; }
.rb-header { font-size: 11px; font-weight: 700; color: #9ca3af; margin-bottom: 6px; }
.rb-content { font-size: 12px; color: #64748b; line-height: 1.6; white-space: pre-wrap; }
.output-text { font-size: 14px; color: #374151; line-height: 1.7; white-space: pre-wrap; }
.output-placeholder { height: 160px; display: flex; align-items: center; justify-content: center; color: #9ca3af; font-size: 13px; }
.output-loading { height: 160px; display: flex; align-items: center; justify-content: center; gap: 8px; }
.dot-pulse { color: #2563eb; font-size: 16px; animation: dotPulse 1.2s ease infinite; }
@keyframes dotPulse { 0%, 80%, 100% { opacity: 0; transform: scale(0.6); } 40% { opacity: 1; transform: scale(1); } }

/* ===== 历史记录 ===== */
.history-list { display: flex; flex-direction: column; gap: 6px; }
.history-item {
  display: flex; align-items: center; gap: 10px; padding: 8px 10px;
  border-radius: 8px; cursor: pointer; transition: background 0.15s;
  font-size: 12px;
}
.history-item:hover { background: #f8fafc; }
.h-model { font-weight: 700; flex-shrink: 0; width: 100px; }
.h-msg { flex: 1; color: #6b7280; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.h-time { color: #9ca3af; flex-shrink: 0; }
</style>
