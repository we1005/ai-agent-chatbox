<template>
  <div class="model-config">
    <div class="page-header">
      <h1>模型配置</h1>
      <p class="subtitle">为每个模型独立配置生成参数、思考模式和系统提示词</p>
    </div>

    <div class="config-layout">
      <!-- 左侧模型列表 -->
      <div class="model-list-panel">
        <div class="panel-title">可用模型</div>
        <div
          v-for="m in models"
          :key="m.id"
          class="model-list-item"
          :class="{ active: selectedModel === m.id }"
          @click="selectedModel = m.id"
        >
          <div class="model-list-main">
            <span class="model-list-name">{{ m.displayName }}</span>
            <div class="model-tags">
              <span class="tag" v-for="tag in m.tags" :key="tag" :class="tag.toLowerCase()">{{ tag }}</span>
            </div>
          </div>
          <div class="model-ctx">{{ m.context }}</div>
        </div>
      </div>

      <!-- 右侧配置面板 -->
      <div class="config-panel-right" v-if="current">
        <div class="config-panel-header">
          <div>
            <h2>{{ current.displayName }}</h2>
            <code class="model-id-code">{{ current.id }}</code>
          </div>
          <div class="header-actions">
            <button class="btn-ghost" @click="resetDefaults">重置默认值</button>
            <button class="btn-primary" @click="saveConfig">保存设置</button>
          </div>
        </div>

        <!-- 约束提示 -->
        <div class="constraint-notice" v-if="current.hasConstraints">
          <span class="notice-icon">⚠️</span>
          <span>{{ current.constraintNote }}</span>
        </div>

        <!-- 思考模式 -->
        <div class="section-block">
          <div class="section-title">思考模式（Thinking Mode）</div>
          <div class="param-row switch-row">
            <div class="param-info">
              <div class="param-name">启用深度思考</div>
              <div class="param-desc">{{ current.thinkingDesc }}</div>
            </div>
            <div class="switch-wrapper">
              <label class="toggle" :class="{ disabled: !current.thinkingEditable }">
                <input type="checkbox" v-model="form.thinking" :disabled="!current.thinkingEditable">
                <span class="slider"></span>
              </label>
              <span class="toggle-label" :class="{ disabled: !current.thinkingEditable }">
                {{ !current.thinkingEditable ? (current.id.includes('thinking') ? '强制开启' : '不支持') : (form.thinking ? '开启' : '关闭') }}
              </span>
            </div>
          </div>
        </div>

        <!-- 生成参数 -->
        <div class="section-block">
          <div class="section-title">生成参数</div>

          <!-- Temperature -->
          <div class="param-row" :class="{ 'param-disabled': !current.tempEditable }">
            <div class="param-info">
              <div class="param-name">Temperature <span class="param-badge" v-if="!current.tempEditable">固定值</span></div>
              <div class="param-desc">控制输出的随机性和创造力</div>
              <div v-if="current.tempEditable" class="preset-chips">
                <span v-for="p in tempPresets" :key="p.label" class="preset-chip" @click="form.temperature = p.value">
                  {{ p.label }} <em>{{ p.value }}</em>
                </span>
              </div>
            </div>
            <div class="param-control">
              <div class="slider-number-group">
                <input type="range" class="range-slider"
                  v-model.number="form.temperature"
                  :min="0" :max="2" :step="0.05"
                  :disabled="!current.tempEditable"
                />
                <input type="number" class="num-input"
                  v-model.number="form.temperature"
                  :min="0" :max="2" :step="0.05"
                  :disabled="!current.tempEditable"
                />
              </div>
              <div v-if="!current.tempEditable" class="disabled-note">{{ current.tempNote }}</div>
            </div>
          </div>

          <!-- Top P -->
          <div class="param-row" :class="{ 'param-disabled': !current.topPEditable }">
            <div class="param-info">
              <div class="param-name">Top P <span class="param-badge" v-if="!current.topPEditable">固定值</span></div>
              <div class="param-desc">核采样概率，与 Temperature 选其一使用</div>
            </div>
            <div class="param-control">
              <div class="slider-number-group">
                <input type="range" class="range-slider"
                  v-model.number="form.topP"
                  :min="0" :max="1" :step="0.05"
                  :disabled="!current.topPEditable"
                />
                <input type="number" class="num-input"
                  v-model.number="form.topP"
                  :min="0" :max="1" :step="0.05"
                  :disabled="!current.topPEditable"
                />
              </div>
              <div v-if="!current.topPEditable" class="disabled-note">{{ current.topPNote }}</div>
            </div>
          </div>

          <!-- Max Tokens -->
          <div class="param-row">
            <div class="param-info">
              <div class="param-name">Max Tokens</div>
              <div class="param-desc">最大输出 token 数 / 最大：{{ current.maxTokensLimit.toLocaleString() }}</div>
            </div>
            <div class="param-control">
              <div class="slider-number-group">
                <input type="range" class="range-slider"
                  v-model.number="form.maxTokens"
                  :min="256" :max="current.maxTokensLimit" :step="256"
                />
                <input type="number" class="num-input wide"
                  v-model.number="form.maxTokens"
                  :min="256" :max="current.maxTokensLimit"
                />
              </div>
            </div>
          </div>

          <!-- Presence Penalty -->
          <div class="param-row" :class="{ 'param-disabled': !current.penaltyEditable }">
            <div class="param-info">
              <div class="param-name">Presence Penalty <span class="param-badge" v-if="!current.penaltyEditable">固定值</span></div>
              <div class="param-desc">惩罚已出现过的 token，增加话题多样性</div>
            </div>
            <div class="param-control">
              <div class="slider-number-group">
                <input type="range" class="range-slider"
                  v-model.number="form.presencePenalty"
                  :min="-2" :max="2" :step="0.1"
                  :disabled="!current.penaltyEditable"
                />
                <input type="number" class="num-input"
                  v-model.number="form.presencePenalty"
                  :min="-2" :max="2" :step="0.1"
                  :disabled="!current.penaltyEditable"
                />
              </div>
            </div>
          </div>

          <!-- Frequency Penalty -->
          <div class="param-row" :class="{ 'param-disabled': !current.penaltyEditable }">
            <div class="param-info">
              <div class="param-name">Frequency Penalty <span class="param-badge" v-if="!current.penaltyEditable">固定值</span></div>
              <div class="param-desc">惩罚频繁出现的 token，减少重复</div>
            </div>
            <div class="param-control">
              <div class="slider-number-group">
                <input type="range" class="range-slider"
                  v-model.number="form.frequencyPenalty"
                  :min="-2" :max="2" :step="0.1"
                  :disabled="!current.penaltyEditable"
                />
                <input type="number" class="num-input"
                  v-model.number="form.frequencyPenalty"
                  :min="-2" :max="2" :step="0.1"
                  :disabled="!current.penaltyEditable"
                />
              </div>
            </div>
          </div>
        </div>

        <!-- System Prompt -->
        <div class="section-block">
          <div class="section-title">
            全局系统提示词
            <span class="char-count">{{ form.systemPrompt.length }} 字 / 约 {{ Math.round(form.systemPrompt.length * 0.6) }} tokens</span>
          </div>
          <textarea
            class="prompt-textarea"
            v-model="form.systemPrompt"
            placeholder="输入该模型的全局 system prompt，对所有对话生效...&#10;&#10;支持变量：{{date}} {{time}}"
            rows="8"
          ></textarea>
          <div class="prompt-hint">💡 此处设置的提示词是全局默认值，聊天界面的 Prompt 工作室可在此基础上叠加</div>
        </div>

        <!-- 存储提示 -->
        <div class="save-notice" v-if="saved">
          <span>✅ 配置已保存</span>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch } from 'vue'

const selectedModel = ref('deepseek-chat')
const saved = ref(false)

const models = ref([
  {
    id: 'deepseek-chat',
    displayName: 'DeepSeek-V3.2',
    tags: ['128K', 'JSON', 'Prefix'],
    context: '128K ctx',
    hasConstraints: false,
    constraintNote: '',
    thinkingDesc: '通过 extra_body 启用，模型名不变',
    thinkingEditable: true,
    tempEditable: true,
    tempNote: '',
    topPEditable: true,
    topPNote: '',
    penaltyEditable: true,
    maxTokensLimit: 8192,
    defaults: { thinking: false, temperature: 1.0, topP: 1.0, maxTokens: 4096, presencePenalty: 0.0, frequencyPenalty: 0.0, systemPrompt: '' },
  },
  {
    id: 'kimi-k2-0905-preview',
    displayName: 'Kimi K2 (0905)',
    tags: ['256K', 'Tools', 'NEW'],
    context: '256K ctx',
    hasConstraints: false,
    constraintNote: '',
    thinkingDesc: '需切换至 kimi-k2-thinking 模型',
    thinkingEditable: false,
    tempEditable: true,
    tempNote: '',
    topPEditable: true,
    topPNote: '',
    penaltyEditable: true,
    maxTokensLimit: 65536,
    defaults: { thinking: false, temperature: 0.6, topP: 1.0, maxTokens: 8192, presencePenalty: 0.0, frequencyPenalty: 0.0, systemPrompt: '' },
  },
  {
    id: 'kimi-k2.5',
    displayName: 'Kimi K2.5',
    tags: ['256K', 'Vision', 'NEW'],
    context: '256K ctx',
    hasConstraints: true,
    constraintNote: 'kimi-k2.5 的 temperature、top_p、presence_penalty、frequency_penalty 均为固定值，自行设置会导致 API 报错！',
    thinkingDesc: '默认启用，可通过参数关闭（与 DeepSeek 相反）',
    thinkingEditable: true,
    tempEditable: false,
    tempNote: '固定：thinking=on 时 1.0，thinking=off 时 0.6',
    topPEditable: false,
    topPNote: '固定值：0.95',
    penaltyEditable: false,
    maxTokensLimit: 65536,
    defaults: { thinking: true, temperature: 1.0, topP: 0.95, maxTokens: 32768, presencePenalty: 0.0, frequencyPenalty: 0.0, systemPrompt: '' },
  },
  {
    id: 'kimi-k2-thinking',
    displayName: 'Kimi K2 Thinking',
    tags: ['256K', 'Think'],
    context: '256K ctx',
    hasConstraints: true,
    constraintNote: '该模型强制启用思考模式，无法关闭。适合需要深度推理的场景。',
    thinkingDesc: '强制启用，无法关闭',
    thinkingEditable: false,
    tempEditable: true,
    tempNote: '',
    topPEditable: true,
    topPNote: '',
    penaltyEditable: true,
    maxTokensLimit: 65536,
    defaults: { thinking: true, temperature: 1.0, topP: 1.0, maxTokens: 32768, presencePenalty: 0.0, frequencyPenalty: 0.0, systemPrompt: '' },
  },
])

const current = computed(() => models.value.find(m => m.id === selectedModel.value))

const forms = ref<Record<string, any>>({})

models.value.forEach(m => {
  forms.value[m.id] = { ...m.defaults }
})

const form = computed(() => forms.value[selectedModel.value])

const tempPresets = [
  { label: '代码/数学', value: 0.0 },
  { label: '数据分析', value: 1.0 },
  { label: '通用对话', value: 1.3 },
  { label: '翻译', value: 1.3 },
  { label: '创意写作', value: 1.5 },
]

const resetDefaults = () => {
  if (!current.value) return
  forms.value[selectedModel.value] = { ...current.value.defaults }
}

const saveConfig = () => {
  localStorage.setItem(`model-config-${selectedModel.value}`, JSON.stringify(form.value))
  saved.value = true
  setTimeout(() => { saved.value = false }, 2000)
}

// 加载已存储的配置
models.value.forEach(m => {
  const stored = localStorage.getItem(`model-config-${m.id}`)
  if (stored) {
    try { forms.value[m.id] = { ...m.defaults, ...JSON.parse(stored) } } catch {}
  }
})
</script>

<style scoped>
.model-config { padding: 32px; }
.page-header { margin-bottom: 28px; }
.page-header h1 { font-size: 26px; font-weight: 800; color: #111827; margin: 0 0 4px; }
.subtitle { color: #6b7280; font-size: 14px; margin: 0; }

.config-layout { display: grid; grid-template-columns: 220px 1fr; gap: 20px; align-items: start; }

/* ===== 模型列表 ===== */
.model-list-panel {
  background: white; border-radius: 14px;
  box-shadow: 0 1px 4px rgba(0,0,0,0.07);
  border: 1px solid #f1f5f9;
  overflow: hidden;
}
.panel-title {
  font-size: 11px; font-weight: 700; color: #9ca3af;
  text-transform: uppercase; letter-spacing: 0.05em;
  padding: 14px 16px 8px;
}
.model-list-item {
  padding: 12px 16px; cursor: pointer;
  border-left: 3px solid transparent;
  transition: all 0.15s;
}
.model-list-item:hover { background: #f8fafc; }
.model-list-item.active { background: #eff6ff; border-left-color: #2563eb; }
.model-list-name { font-size: 13px; font-weight: 600; color: #374151; display: block; margin-bottom: 5px; }
.model-list-item.active .model-list-name { color: #1d4ed8; }
.model-tags { display: flex; gap: 4px; flex-wrap: wrap; }
.tag { font-size: 10px; padding: 1px 6px; border-radius: 4px; font-weight: 600; background: #f1f5f9; color: #64748b; }
.tag.vision { background: #fdf4ff; color: #9333ea; }
.tag.new { background: #fef3c7; color: #d97706; }
.tag.think { background: #eff6ff; color: #2563eb; }
.tag.tools { background: #d1fae5; color: #059669; }
.model-ctx { font-size: 11px; color: #9ca3af; margin-top: 4px; }

/* ===== 右侧配置 ===== */
.config-panel-right {
  background: white; border-radius: 14px; padding: 28px;
  box-shadow: 0 1px 4px rgba(0,0,0,0.07); border: 1px solid #f1f5f9;
}
.config-panel-header {
  display: flex; justify-content: space-between; align-items: flex-start;
  margin-bottom: 20px;
}
.config-panel-header h2 { font-size: 20px; font-weight: 800; color: #111827; margin: 0 0 4px; }
.model-id-code { font-size: 12px; color: #6b7280; background: #f1f5f9; padding: 2px 8px; border-radius: 4px; }
.header-actions { display: flex; gap: 10px; }

.btn-ghost {
  padding: 8px 16px; border-radius: 8px; border: 1px solid #e5e7eb;
  background: white; color: #374151; font-size: 13px; font-weight: 600;
  cursor: pointer; transition: all 0.15s;
}
.btn-ghost:hover { border-color: #2563eb; color: #2563eb; }
.btn-primary {
  padding: 8px 20px; border-radius: 8px; border: none;
  background: #2563eb; color: white; font-size: 13px; font-weight: 600;
  cursor: pointer; transition: all 0.15s;
}
.btn-primary:hover { background: #1d4ed8; }

.constraint-notice {
  background: #fffbeb; border: 1px solid #fde68a; border-radius: 10px;
  padding: 12px 16px; margin-bottom: 20px;
  display: flex; gap: 8px; align-items: flex-start;
  font-size: 13px; color: #92400e; line-height: 1.5;
}
.notice-icon { flex-shrink: 0; }

/* ===== 参数区块 ===== */
.section-block { margin-bottom: 28px; }
.section-title {
  font-size: 12px; font-weight: 700; color: #6b7280;
  text-transform: uppercase; letter-spacing: 0.06em;
  margin-bottom: 14px;
  display: flex; align-items: center; justify-content: space-between;
}
.char-count { font-size: 11px; color: #9ca3af; font-weight: 500; text-transform: none; letter-spacing: 0; }

.param-row {
  display: grid; grid-template-columns: 1fr 280px;
  gap: 20px; align-items: start;
  padding: 14px 0; border-bottom: 1px solid #f9fafb;
}
.param-row:last-child { border-bottom: none; }
.param-row.param-disabled { opacity: 0.5; }
.param-row.switch-row { align-items: center; }

.param-name { font-size: 14px; font-weight: 600; color: #374151; margin-bottom: 3px; }
.param-badge { font-size: 10px; background: #fee2e2; color: #dc2626; padding: 1px 6px; border-radius: 4px; margin-left: 6px; font-weight: 700; }
.param-desc { font-size: 12px; color: #9ca3af; line-height: 1.4; }
.disabled-note { font-size: 11px; color: #d97706; margin-top: 6px; }

.preset-chips { display: flex; gap: 6px; flex-wrap: wrap; margin-top: 8px; }
.preset-chip {
  font-size: 11px; padding: 3px 8px; border-radius: 6px;
  background: #f1f5f9; border: 1px solid #e2e8f0;
  cursor: pointer; color: #374151; transition: all 0.15s;
}
.preset-chip:hover { background: #dbeafe; border-color: #93c5fd; color: #1d4ed8; }
.preset-chip em { font-style: normal; font-weight: 700; color: #2563eb; margin-left: 4px; }

.slider-number-group { display: flex; align-items: center; gap: 10px; }
.range-slider {
  flex: 1; -webkit-appearance: none; appearance: none;
  height: 4px; background: #e2e8f0; border-radius: 4px; outline: none;
}
.range-slider::-webkit-slider-thumb {
  -webkit-appearance: none; width: 16px; height: 16px;
  border-radius: 50%; background: #2563eb; cursor: pointer;
  box-shadow: 0 1px 4px rgba(37,99,235,0.4);
  transition: transform 0.1s;
}
.range-slider::-webkit-slider-thumb:hover { transform: scale(1.2); }
.range-slider:disabled { opacity: 0.4; cursor: not-allowed; }

.num-input {
  width: 68px; padding: 5px 8px; border: 1px solid #e5e7eb;
  border-radius: 7px; font-size: 13px; font-weight: 600; color: #374151;
  text-align: center; outline: none; transition: border-color 0.15s;
}
.num-input:focus { border-color: #2563eb; }
.num-input:disabled { background: #f9fafb; cursor: not-allowed; }
.num-input.wide { width: 88px; }

/* ===== 开关 ===== */
.switch-wrapper { display: flex; align-items: center; gap: 10px; justify-content: flex-end; }
.toggle { position: relative; display: inline-block; width: 44px; height: 24px; }
.toggle input { opacity: 0; width: 0; height: 0; }
.toggle .slider {
  position: absolute; cursor: pointer; top: 0; left: 0; right: 0; bottom: 0;
  background: #e2e8f0; border-radius: 24px; transition: 0.3s;
}
.toggle .slider:before {
  content: ''; position: absolute;
  height: 18px; width: 18px; left: 3px; bottom: 3px;
  background: white; border-radius: 50%; transition: 0.3s;
  box-shadow: 0 1px 3px rgba(0,0,0,0.2);
}
.toggle input:checked + .slider { background: #2563eb; }
.toggle input:checked + .slider:before { transform: translateX(20px); }
.toggle.disabled { opacity: 0.4; cursor: not-allowed; }
.toggle-label { font-size: 13px; color: #374151; font-weight: 500; }
.toggle-label.disabled { color: #9ca3af; }

/* ===== System Prompt ===== */
.prompt-textarea {
  width: 100%; box-sizing: border-box;
  border: 1px solid #e5e7eb; border-radius: 10px;
  padding: 12px 14px; font-size: 13px; color: #374151;
  font-family: 'Inter', monospace; line-height: 1.6; resize: vertical;
  outline: none; transition: border-color 0.15s;
}
.prompt-textarea:focus { border-color: #2563eb; }
.prompt-hint { font-size: 12px; color: #6b7280; margin-top: 8px; }

/* ===== 保存提示 ===== */
.save-notice {
  background: #d1fae5; border: 1px solid #6ee7b7;
  border-radius: 10px; padding: 10px 16px;
  color: #065f46; font-size: 13px; font-weight: 600;
  margin-top: 20px;
}
</style>
