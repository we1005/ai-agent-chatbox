<template>
  <div class="prompt-studio">
    <div class="page-header">
      <h1>Prompt 工作室</h1>
      <p class="subtitle">管理系统提示词模板、输出格式和上下文截断策略</p>
    </div>

    <div class="studio-layout">
      <!-- 左侧模板库 -->
      <div class="template-panel">
        <div class="panel-header">
          <span class="panel-title">模板库</span>
          <button class="add-tpl-btn" @click="createNewTemplate">+</button>
        </div>
        <div class="template-list">
          <div
            v-for="tpl in templates"
            :key="tpl.id"
            class="tpl-item"
            :class="{ active: selectedTemplate === tpl.id }"
            @click="loadTemplate(tpl.id)"
          >
            <span class="tpl-icon">{{ tpl.icon }}</span>
            <div class="tpl-info">
              <div class="tpl-name">{{ tpl.name }}</div>
              <div class="tpl-tags">
                <span class="tpl-tag" v-for="t in tpl.tags" :key="t">{{ t }}</span>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- 右侧编辑器 -->
      <div class="editor-panel">
        <!-- 模板元信息 -->
        <div class="editor-meta">
          <input class="tpl-name-input" v-model="editor.name" placeholder="模板名称..." />
          <div class="meta-actions">
            <button class="btn-ghost" @click="applyToAll">应用到所有模型</button>
            <button class="btn-primary" @click="saveTemplate">保存模板</button>
          </div>
        </div>

        <!-- 提示词编辑区 -->
        <div class="editor-section">
          <div class="section-label">
            System Prompt
            <span class="counter">{{ editor.systemPrompt.length }} 字 · 约 {{ estTokens }} tokens</span>
          </div>
          <textarea
            class="big-textarea"
            v-model="editor.systemPrompt"
            :rows="14"
            placeholder="在此编辑系统提示词...&#10;&#10;支持变量占位符：&#10;  {{date}}    → 当前日期&#10;  {{time}}    → 当前时间&#10;  {{model}}   → 当前模型名"
          ></textarea>
        </div>

        <!-- 输出格式设置 -->
        <div class="output-format-section">
          <div class="section-label">输出格式控制</div>
          <div class="format-grid">
            <!-- JSON Mode -->
            <div class="format-card" :class="{ active: editor.jsonMode }">
              <div class="format-top">
                <span class="format-icon">{ }</span>
                <div class="format-info">
                  <div class="format-name">JSON Mode</div>
                  <div class="format-desc">强制模型输出合法 JSON 字符串</div>
                </div>
                <label class="toggle">
                  <input type="checkbox" v-model="editor.jsonMode">
                  <span class="slider"></span>
                </label>
              </div>
              <div class="format-note" v-if="editor.jsonMode">
                ⚠ System Prompt 中必须包含 "json" 关键词，并提供期望的输出格式示例
              </div>
            </div>

            <!-- Partial Mode -->
            <div class="format-card" :class="{ active: editor.partialMode }">
              <div class="format-top">
                <span class="format-icon">↳</span>
                <div class="format-info">
                  <div class="format-name">Partial Mode（前缀续写）</div>
                  <div class="format-desc">预填 assistant 回复的开头，引导输出格式</div>
                </div>
                <label class="toggle">
                  <input type="checkbox" v-model="editor.partialMode">
                  <span class="slider"></span>
                </label>
              </div>
              <div v-if="editor.partialMode" class="partial-config">
                <div class="partial-row">
                  <label>前缀内容</label>
                  <input class="partial-input" v-model="editor.partialPrefix" placeholder="```python&#10;" />
                </div>
                <div class="partial-row">
                  <label>Stop 词（可选）</label>
                  <input class="partial-input" v-model="editor.partialStop" placeholder="```" />
                </div>
                <div class="partial-note">不可与 JSON Mode 同时使用</div>
              </div>
            </div>
          </div>
        </div>

        <!-- 上下文管理 -->
        <div class="context-section">
          <div class="section-label">上下文历史管理</div>
          <div class="context-cards">
            <div
              v-for="strategy in contextStrategies"
              :key="strategy.id"
              class="ctx-card"
              :class="{ selected: editor.contextStrategy === strategy.id }"
              @click="editor.contextStrategy = strategy.id"
            >
              <div class="ctx-icon">{{ strategy.icon }}</div>
              <div class="ctx-name">{{ strategy.name }}</div>
              <div class="ctx-desc">{{ strategy.desc }}</div>
            </div>
          </div>

          <div class="ctx-token-limit" v-if="editor.contextStrategy === 'token'">
            <label>Token 上限</label>
            <input type="range" class="range-slider"
              v-model.number="editor.contextTokenLimit"
              :min="1000" :max="32000" :step="500"
            />
            <span class="ctx-limit-value">{{ editor.contextTokenLimit.toLocaleString() }}</span>
            <span class="ctx-limit-note">超出时自动截断最早的消息（始终保留 System Prompt）</span>
          </div>
        </div>

        <!-- 预览 -->
        <div class="preview-section">
          <div class="section-label">渲染预览</div>
          <div class="preview-box">
            <div class="preview-label">System</div>
            <div class="preview-content">{{ renderedPrompt || '（空）' }}</div>
          </div>
        </div>

        <div class="save-tip" v-if="saved">✅ 模板已保存</div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'

const selectedTemplate = ref('general')
const saved = ref(false)

const templates = ref([
  { id: 'general', icon: '💬', name: '通用助手', tags: ['默认'] },
  { id: 'researcher', icon: '🔬', name: '行业研究分析师', tags: ['Kimi推荐', 'web-search'] },
  { id: 'coder', icon: '💻', name: '代码专家', tags: ['temperature=0', 'code_runner'] },
  { id: 'creative', icon: '✨', name: '创意写作', tags: ['temperature=1.5'] },
  { id: 'json_output', icon: '{ }', name: '严格 JSON 输出', tags: ['JSON Mode'] },
  { id: 'roleplay', icon: '🎭', name: '角色扮演框架', tags: ['Partial Mode'] },
])

const templateContents: Record<string, any> = {
  general: {
    name: '通用助手', systemPrompt: '你是一个乐于助人、思维清晰的 AI 助手。请根据用户的问题，给出准确、有条理的回答。\n\n当前日期：{{date}}',
    jsonMode: false, partialMode: false, partialPrefix: '', partialStop: '',
    contextStrategy: 'full', contextTokenLimit: 4000,
  },
  researcher: {
    name: '行业研究分析师',
    systemPrompt: `你是专业的企业行业研究 AI 助手，擅长信息搜索、数据分析和商业报告生成。

## 语言统一
所有输出内容必须与用户提问语言保持一致。

## 数据来源
严禁编造数据。每次提供信息时必须：
- 明确标注数据来源：发布机构、网页标题或文章名称
- 区分"已确认数据"与"行业估算"
- 找不到数据时，明确回应"暂未找到相关数据"

## 输出结构
1. 信息搜索阶段：明确搜索策略，记录所有来源
2. 数据分析阶段：描述性统计，洞察发现
3. 报告输出阶段：执行摘要，可视化建议，参考来源`,
    jsonMode: false, partialMode: false, partialPrefix: '', partialStop: '',
    contextStrategy: 'token', contextTokenLimit: 8000,
  },
  coder: {
    name: '代码专家',
    systemPrompt: '你是一位资深软件工程师，专注于编写高质量、可维护的代码。\n\n原则：\n- 代码简洁，避免过度工程化\n- 必须附上必要的注释\n- 提供测试用例\n- 指出潜在的性能问题',
    jsonMode: false, partialMode: false, partialPrefix: '', partialStop: '',
    contextStrategy: 'token', contextTokenLimit: 6000,
  },
  creative: {
    name: '创意写作',
    systemPrompt: '你是一位充满创意的写作助手，文笔优美，想象力丰富。请用生动、有感染力的语言帮助用户完成创意写作任务。',
    jsonMode: false, partialMode: false, partialPrefix: '', partialStop: '',
    contextStrategy: 'full', contextTokenLimit: 4000,
  },
  json_output: {
    name: '严格 JSON 输出',
    systemPrompt: '你是数据提取助手。请从用户输入中提取信息，并严格按照 json 格式输出，不要输出任何多余内容。\n\n输出格式示例：\n{\n  "result": "...",\n  "confidence": 0.95\n}',
    jsonMode: true, partialMode: false, partialPrefix: '', partialStop: '',
    contextStrategy: 'full', contextTokenLimit: 4000,
  },
  roleplay: {
    name: '角色扮演框架',
    systemPrompt: '你将扮演 [角色名]。\n\n角色描述：[在此填写角色详细背景、性格、说话风格...]\n\n请始终以该角色的口吻和视角回应，保持角色一致性。',
    jsonMode: false, partialMode: true, partialPrefix: '[角色名]：', partialStop: '',
    contextStrategy: 'full', contextTokenLimit: 4000,
  },
}

const editor = ref({ ...templateContents['general'] })

const loadTemplate = (id: string) => {
  selectedTemplate.value = id
  editor.value = { ...templateContents[id] }
}

const contextStrategies = [
  { id: 'full', icon: '📚', name: '全量传入', desc: '将所有历史消息传给模型，适合短对话' },
  { id: 'token', icon: '✂️', name: 'Token 截断', desc: '超出阈值时截断最早的消息，推荐用于长对话' },
  { id: 'rounds', icon: '🔢', name: '轮次限制', desc: '只保留最近 N 轮对话' },
]

const estTokens = computed(() => Math.round(editor.value.systemPrompt.length * 0.6))

const renderedPrompt = computed(() => {
  const now = new Date()
  return editor.value.systemPrompt
    .replace('{{date}}', now.toLocaleDateString('zh-CN'))
    .replace('{{time}}', now.toLocaleTimeString('zh-CN'))
    .replace('{{model}}', '(当前选择的模型)')
})

const createNewTemplate = () => {
  const id = 'custom_' + Date.now()
  templates.value.push({ id, icon: '📝', name: '新模板', tags: ['自定义'] })
  templateContents[id] = { ...templateContents['general'], name: '新模板' }
  loadTemplate(id)
}

const saveTemplate = () => {
  if (selectedTemplate.value) {
    templateContents[selectedTemplate.value] = { ...editor.value }
  }
  localStorage.setItem('prompt-studio', JSON.stringify(templateContents))
  saved.value = true
  setTimeout(() => { saved.value = false }, 2000)
}

const applyToAll = () => {
  alert('已将当前 System Prompt 应用为所有模型的默认提示词')
}
</script>

<style scoped>
.prompt-studio { padding: 32px; max-width: 1200px; }
.page-header { margin-bottom: 28px; }
.page-header h1 { font-size: 26px; font-weight: 800; color: #111827; margin: 0 0 4px; }
.subtitle { color: #6b7280; font-size: 14px; margin: 0; }

.studio-layout { display: grid; grid-template-columns: 200px 1fr; gap: 20px; }

/* ===== 模板列表 ===== */
.template-panel {
  background: white; border-radius: 14px; overflow: hidden;
  box-shadow: 0 1px 4px rgba(0,0,0,0.07); border: 1px solid #f1f5f9;
  height: fit-content; position: sticky; top: 20px;
}
.panel-header {
  display: flex; justify-content: space-between; align-items: center;
  padding: 14px 16px 8px;
  border-bottom: 1px solid #f1f5f9;
}
.panel-title { font-size: 11px; font-weight: 700; color: #9ca3af; text-transform: uppercase; letter-spacing: 0.05em; }
.add-tpl-btn {
  width: 22px; height: 22px; border-radius: 6px;
  border: 1px solid #e5e7eb; background: white; cursor: pointer;
  color: #6b7280; font-size: 14px; line-height: 1;
  display: flex; align-items: center; justify-content: center;
}
.add-tpl-btn:hover { background: #eff6ff; border-color: #93c5fd; color: #2563eb; }

.template-list { padding: 8px; }
.tpl-item {
  display: flex; align-items: flex-start; gap: 8px;
  padding: 10px 10px; border-radius: 8px; cursor: pointer;
  transition: all 0.15s; border-left: 2px solid transparent;
}
.tpl-item:hover { background: #f8fafc; }
.tpl-item.active { background: #eff6ff; border-left-color: #2563eb; }
.tpl-icon { font-size: 16px; flex-shrink: 0; }
.tpl-name { font-size: 13px; font-weight: 600; color: #374151; margin-bottom: 4px; }
.tpl-item.active .tpl-name { color: #1d4ed8; }
.tpl-tags { display: flex; gap: 3px; flex-wrap: wrap; }
.tpl-tag { font-size: 9px; background: #f1f5f9; color: #64748b; padding: 1px 5px; border-radius: 3px; font-weight: 600; }

/* ===== 编辑器 ===== */
.editor-panel {
  background: white; border-radius: 14px; padding: 28px;
  box-shadow: 0 1px 4px rgba(0,0,0,0.07); border: 1px solid #f1f5f9;
}
.editor-meta {
  display: flex; justify-content: space-between; align-items: center;
  margin-bottom: 24px; gap: 16px;
}
.tpl-name-input {
  flex: 1; font-size: 18px; font-weight: 800; color: #111827;
  border: none; outline: none; background: transparent;
  border-bottom: 2px solid #f1f5f9;
  padding-bottom: 4px; transition: border-color 0.15s;
}
.tpl-name-input:focus { border-bottom-color: #2563eb; }
.meta-actions { display: flex; gap: 10px; }

.editor-section { margin-bottom: 24px; }
.section-label {
  font-size: 12px; font-weight: 700; color: #6b7280;
  text-transform: uppercase; letter-spacing: 0.06em;
  margin-bottom: 10px;
  display: flex; justify-content: space-between; align-items: center;
}
.counter { font-size: 11px; color: #9ca3af; font-weight: 500; text-transform: none; letter-spacing: 0; }

.big-textarea {
  width: 100%; box-sizing: border-box;
  border: 1px solid #e5e7eb; border-radius: 10px;
  padding: 14px 16px; font-size: 13px; color: #374151;
  font-family: 'JetBrains Mono', 'Fira Code', 'Cascadia Code', monospace;
  line-height: 1.7; resize: vertical; outline: none;
  transition: border-color 0.15s; background: #fafafa;
}
.big-textarea:focus { border-color: #2563eb; background: white; }

/* ===== 输出格式 ===== */
.output-format-section { margin-bottom: 24px; }
.format-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }
.format-card {
  border: 1px solid #f1f5f9; border-radius: 10px; padding: 14px;
  transition: all 0.15s;
}
.format-card.active { border-color: #93c5fd; background: #eff6ff; }
.format-top { display: flex; align-items: center; gap: 10px; margin-bottom: 6px; }
.format-icon { font-size: 20px; font-family: monospace; font-weight: 700; color: #2563eb; flex-shrink: 0; width: 28px; }
.format-info { flex: 1; }
.format-name { font-size: 13px; font-weight: 700; color: #374151; }
.format-desc { font-size: 12px; color: #9ca3af; }
.format-note { font-size: 12px; color: #d97706; background: #fffbeb; padding: 6px 10px; border-radius: 6px; margin-top: 8px; }

.partial-config { margin-top: 10px; }
.partial-row { display: flex; align-items: center; gap: 10px; margin-bottom: 8px; }
.partial-row label { font-size: 12px; color: #6b7280; width: 80px; flex-shrink: 0; }
.partial-input {
  flex: 1; border: 1px solid #e5e7eb; border-radius: 7px;
  padding: 5px 10px; font-size: 12px; outline: none; font-family: monospace;
}
.partial-input:focus { border-color: #2563eb; }
.partial-note { font-size: 11px; color: #9ca3af; }

/* ===== 上下文管理 ===== */
.context-section { margin-bottom: 24px; }
.context-cards { display: grid; grid-template-columns: repeat(3, 1fr); gap: 10px; margin-bottom: 14px; }
.ctx-card {
  border: 2px solid #f1f5f9; border-radius: 10px; padding: 12px;
  cursor: pointer; transition: all 0.15s; text-align: center;
}
.ctx-card:hover { border-color: #93c5fd; }
.ctx-card.selected { border-color: #2563eb; background: #eff6ff; }
.ctx-icon { font-size: 22px; margin-bottom: 6px; }
.ctx-name { font-size: 13px; font-weight: 600; color: #374151; margin-bottom: 3px; }
.ctx-desc { font-size: 11px; color: #9ca3af; line-height: 1.4; }

.ctx-token-limit { display: flex; align-items: center; gap: 12px; }
.ctx-token-limit label { font-size: 13px; font-weight: 600; color: #374151; white-space: nowrap; }
.range-slider {
  flex: 1; -webkit-appearance: none; appearance: none;
  height: 4px; background: #e2e8f0; border-radius: 4px; outline: none;
}
.range-slider::-webkit-slider-thumb {
  -webkit-appearance: none; width: 16px; height: 16px;
  border-radius: 50%; background: #2563eb; cursor: pointer;
}
.ctx-limit-value { font-size: 14px; font-weight: 700; color: #2563eb; white-space: nowrap; min-width: 60px; }
.ctx-limit-note { font-size: 11px; color: #9ca3af; }

/* ===== 预览 ===== */
.preview-section { margin-bottom: 20px; }
.preview-box {
  background: #1e293b; border-radius: 10px; padding: 16px;
  font-family: monospace; font-size: 12px; line-height: 1.6;
}
.preview-label { font-size: 10px; font-weight: 700; color: #64748b; text-transform: uppercase; letter-spacing: 0.1em; margin-bottom: 8px; }
.preview-content { color: #94a3b8; white-space: pre-wrap; word-break: break-word; }

/* 开关 */
.toggle { position: relative; display: inline-block; width: 40px; height: 22px; flex-shrink: 0; }
.toggle input { opacity: 0; width: 0; height: 0; }
.toggle .slider {
  position: absolute; cursor: pointer; top: 0; left: 0; right: 0; bottom: 0;
  background: #e2e8f0; border-radius: 22px; transition: 0.3s;
}
.toggle .slider:before {
  content: ''; position: absolute; height: 16px; width: 16px; left: 3px; bottom: 3px;
  background: white; border-radius: 50%; transition: 0.3s; box-shadow: 0 1px 3px rgba(0,0,0,0.2);
}
.toggle input:checked + .slider { background: #2563eb; }
.toggle input:checked + .slider:before { transform: translateX(18px); }

.save-tip { background: #d1fae5; border: 1px solid #6ee7b7; border-radius: 10px; padding: 10px 16px; color: #065f46; font-size: 13px; font-weight: 600; }

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
</style>
