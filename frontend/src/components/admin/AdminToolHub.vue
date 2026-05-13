<template>
  <div class="tool-hub">
    <div class="page-header">
      <h1>工具中心</h1>
      <p class="subtitle">管理 Kimi 官方工具、联网搜索提供商和自定义函数工具</p>
    </div>

    <!-- 联网搜索提供商 -->
    <div class="card section-card">
      <div class="card-header">
        <div>
          <div class="card-title">联网搜索提供商</div>
          <div class="card-desc">选择用于联网搜索的后端服务。Kimi 原生搜索质量更高；SerpApi 支持所有模型。</div>
        </div>
      </div>
      <div class="provider-grid">
        <div
          v-for="p in searchProviders"
          :key="p.id"
          class="provider-card"
          :class="{ selected: searchProvider === p.id }"
          @click="searchProvider = p.id"
        >
          <div class="provider-icon">{{ p.icon }}</div>
          <div class="provider-info">
            <div class="provider-name">{{ p.name }}</div>
            <div class="provider-desc">{{ p.desc }}</div>
            <div class="provider-tags">
              <span class="ptag" v-for="t in p.tags" :key="t" :class="t.type">{{ t.label }}</span>
            </div>
          </div>
          <div class="provider-check" v-if="searchProvider === p.id">✓</div>
        </div>
      </div>
    </div>

    <!-- Kimi 官方工具 -->
    <div class="card section-card">
      <div class="card-header">
        <div>
          <div class="card-title">Kimi 官方工具</div>
          <div class="card-desc">以下工具由 Moonshot 平台提供，仅对 Kimi 系列模型生效。启用后 Kimi 会根据上下文自动决定是否调用。</div>
        </div>
        <div class="badge-group">
          <span class="info-badge blue">kimi-k2-0905</span>
          <span class="info-badge purple">kimi-k2.5</span>
        </div>
      </div>

      <div class="tools-grid">
        <div class="tool-card" v-for="tool in kimiTools" :key="tool.id">
          <div class="tool-top">
            <span class="tool-emoji">{{ tool.icon }}</span>
            <div class="tool-meta">
              <div class="tool-name">{{ tool.name }}</div>
              <code class="tool-code">{{ tool.id }}</code>
            </div>
            <label class="toggle" :class="{ locked: tool.locked }">
              <input type="checkbox" v-model="tool.enabled" :disabled="tool.locked">
              <span class="slider"></span>
            </label>
          </div>
          <div class="tool-desc">{{ tool.desc }}</div>
          <div class="tool-footer">
            <span class="tool-tag" :class="tool.tagType">{{ tool.tag }}</span>
            <span class="tool-cost" v-if="tool.cost">{{ tool.cost }}</span>
          </div>
        </div>
      </div>
    </div>

    <!-- 自定义工具 -->
    <div class="card section-card">
      <div class="card-header">
        <div>
          <div class="card-title">自定义函数工具</div>
          <div class="card-desc">注册自定义 tool_calls 函数，所有支持 Function Calling 的模型均可使用</div>
        </div>
        <button class="btn-primary" @click="showAddTool = true">+ 添加工具</button>
      </div>

      <div class="custom-tools-list" v-if="customTools.length">
        <div class="ct-item" v-for="(ct, i) in customTools" :key="i">
          <div class="ct-icon">🔩</div>
          <div class="ct-info">
            <div class="ct-name">{{ ct.name }}</div>
            <div class="ct-desc">{{ ct.description }}</div>
          </div>
          <span class="ct-enabled" :class="ct.enabled ? 'on' : 'off'">{{ ct.enabled ? '启用' : '禁用' }}</span>
          <label class="toggle">
            <input type="checkbox" v-model="ct.enabled">
            <span class="slider"></span>
          </label>
          <button class="ct-del" @click="customTools.splice(i, 1)">×</button>
        </div>
      </div>
      <div class="empty-custom" v-else>
        <span>暂无自定义工具，点击"添加工具"注册函数</span>
      </div>

      <!-- 添加工具表单 -->
      <div class="add-tool-form" v-if="showAddTool">
        <h4>添加自定义工具</h4>
        <div class="form-row">
          <label>工具名称</label>
          <input v-model="newTool.name" placeholder="calculator" class="form-input"/>
        </div>
        <div class="form-row">
          <label>描述</label>
          <input v-model="newTool.description" placeholder="计算数学表达式" class="form-input"/>
        </div>
        <div class="form-row">
          <label>参数 Schema（JSON）</label>
          <textarea v-model="newTool.schema" class="form-textarea" rows="4" placeholder='{"expression": {"type": "string", "description": "数学表达式"}}'></textarea>
        </div>
        <div class="form-actions">
          <button class="btn-ghost" @click="showAddTool = false">取消</button>
          <button class="btn-primary" @click="addCustomTool">确认添加</button>
        </div>
      </div>
    </div>

    <!-- 保存 -->
    <div class="bottom-bar">
      <div class="save-hint">工具配置会影响所有新发起的对话请求</div>
      <button class="btn-primary large" @click="saveTools">保存工具配置</button>
      <span class="saved-tip" v-if="saved">✅ 已保存</span>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'

const searchProvider = ref('kimi_native')
const saved = ref(false)
const showAddTool = ref(false)

const searchProviders = ref([
  {
    id: 'kimi_native',
    icon: '🌐',
    name: 'Kimi 原生 $web_search',
    desc: 'Kimi 内置搜索引擎，模型自主执行搜索和阅读，结果质量最高。仅支持 Kimi 系列模型。',
    tags: [{ label: '推荐', type: 'recommend' }, { label: '¥0.03/次', type: 'cost' }, { label: '仅 Kimi', type: 'limit' }],
  },
  {
    id: 'serpapi',
    icon: '🔍',
    name: 'SerpApi（当前）',
    desc: '第三方 Google 搜索 API，结果以摘要形式注入 System Prompt，支持所有模型。',
    tags: [{ label: '全模型兼容', type: 'compat' }, { label: '需独立 Key', type: 'warning' }],
  },
  {
    id: 'disabled',
    icon: '🚫',
    name: '关闭联网搜索',
    desc: '禁用所有联网搜索功能，仅使用本地知识库和模型内置知识。',
    tags: [{ label: '离线模式', type: 'neutral' }],
  },
])

const kimiTools = ref([
  { id: '$web_search', icon: '🔍', name: '联网搜索', desc: '实时联网获取并阅读网页内容，由 Kimi 内部执行', tag: '收费', tagType: 'paid', cost: '¥0.03/次', enabled: true, locked: false },
  { id: 'date', icon: '📅', name: '日期时间', desc: '获取当前日期和时间，处理时间相关的查询', tag: '免费', tagType: 'free', cost: '', enabled: true, locked: false },
  { id: 'rethink', icon: '🧠', name: '深度重思', desc: 'AI 对问题进行更深层次的思考和整理，适合复杂推理任务', tag: '免费', tagType: 'free', cost: '', enabled: false, locked: false },
  { id: 'memory', icon: '💾', name: '持久化记忆', desc: '跨对话存储用户偏好和历史信息，实现个性化记忆', tag: '实验性', tagType: 'experimental', cost: '', enabled: false, locked: false },
  { id: 'code_runner', icon: '💻', name: 'Python 代码执行', desc: '在沙盒环境中执行 Python 代码，适合数据分析和计算场景', tag: '免费', tagType: 'free', cost: '', enabled: false, locked: false },
  { id: 'excel', icon: '📊', name: 'Excel/CSV 分析', desc: '解析并分析 Excel 和 CSV 文件数据', tag: '免费', tagType: 'free', cost: '', enabled: false, locked: false },
  { id: 'fetch', icon: '🌐', name: 'URL 内容抓取', desc: '抓取指定 URL 的网页内容并转为 Markdown 格式', tag: '免费', tagType: 'free', cost: '', enabled: false, locked: false },
  { id: 'quickjs', icon: '⚡', name: 'JS 沙盒执行', desc: '使用 QuickJS 安全执行 JavaScript 代码', tag: '免费', tagType: 'free', cost: '', enabled: false, locked: false },
  { id: 'convert', icon: '🔄', name: '单位换算', desc: '长度、质量、温度、货币等多种单位的换算', tag: '免费', tagType: 'free', cost: '', enabled: true, locked: false },
  { id: 'base64', icon: '🔐', name: 'Base64 编解码', desc: 'Base64 编码与解码工具', tag: '免费', tagType: 'free', cost: '', enabled: false, locked: false },
])

const customTools = ref<any[]>([])

const newTool = ref({ name: '', description: '', schema: '' })

const addCustomTool = () => {
  if (!newTool.value.name) return
  customTools.value.push({ ...newTool.value, enabled: true })
  newTool.value = { name: '', description: '', schema: '' }
  showAddTool.value = false
}

const saveTools = () => {
  const config = {
    searchProvider: searchProvider.value,
    kimiTools: kimiTools.value.map(t => ({ id: t.id, enabled: t.enabled })),
    customTools: customTools.value,
  }
  localStorage.setItem('tool-hub-config', JSON.stringify(config))
  saved.value = true
  setTimeout(() => { saved.value = false }, 2000)
}

// 加载存储
const stored = localStorage.getItem('tool-hub-config')
if (stored) {
  try {
    const c = JSON.parse(stored)
    searchProvider.value = c.searchProvider || 'kimi_native'
    if (c.kimiTools) {
      c.kimiTools.forEach((t: any) => {
        const match = kimiTools.value.find(k => k.id === t.id)
        if (match) match.enabled = t.enabled
      })
    }
    customTools.value = c.customTools || []
  } catch {}
}
</script>

<style scoped>
.tool-hub { padding: 32px; max-width: 1100px; }
.page-header { margin-bottom: 28px; }
.page-header h1 { font-size: 26px; font-weight: 800; color: #111827; margin: 0 0 4px; }
.subtitle { color: #6b7280; font-size: 14px; margin: 0; }

.card {
  background: white; border-radius: 14px; padding: 24px;
  box-shadow: 0 1px 4px rgba(0,0,0,0.07); border: 1px solid #f1f5f9;
}
.section-card { margin-bottom: 20px; }
.card-header { display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 20px; }
.card-title { font-size: 15px; font-weight: 700; color: #111827; margin-bottom: 4px; }
.card-desc { font-size: 13px; color: #6b7280; max-width: 600px; line-height: 1.5; }
.badge-group { display: flex; gap: 8px; flex-shrink: 0; }
.info-badge { font-size: 11px; padding: 3px 10px; border-radius: 20px; font-weight: 600; }
.info-badge.blue { background: #dbeafe; color: #1d4ed8; }
.info-badge.purple { background: #f3e8ff; color: #7c3aed; }

/* ===== 搜索提供商 ===== */
.provider-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 14px; }
.provider-card {
  border: 2px solid #f1f5f9; border-radius: 12px; padding: 16px;
  cursor: pointer; transition: all 0.15s; position: relative;
  display: flex; align-items: flex-start; gap: 12px;
}
.provider-card:hover { border-color: #93c5fd; background: #f8fafc; }
.provider-card.selected { border-color: #2563eb; background: #eff6ff; }
.provider-icon { font-size: 24px; flex-shrink: 0; }
.provider-name { font-size: 14px; font-weight: 700; color: #111827; margin-bottom: 4px; }
.provider-desc { font-size: 12px; color: #6b7280; line-height: 1.5; margin-bottom: 8px; }
.provider-tags { display: flex; gap: 6px; flex-wrap: wrap; }
.ptag { font-size: 10px; padding: 2px 7px; border-radius: 4px; font-weight: 600; }
.ptag.recommend { background: #d1fae5; color: #059669; }
.ptag.cost { background: #fef3c7; color: #d97706; }
.ptag.limit { background: #e0e7ff; color: #4338ca; }
.ptag.compat { background: #dbeafe; color: #1d4ed8; }
.ptag.warning { background: #fee2e2; color: #dc2626; }
.ptag.neutral { background: #f1f5f9; color: #64748b; }
.provider-check {
  position: absolute; top: 12px; right: 12px;
  width: 22px; height: 22px; background: #2563eb; color: white;
  border-radius: 50%; display: flex; align-items: center; justify-content: center;
  font-size: 12px; font-weight: 700;
}

/* ===== 工具网格 ===== */
.tools-grid { display: grid; grid-template-columns: repeat(2, 1fr); gap: 12px; }
.tool-card {
  border: 1px solid #f1f5f9; border-radius: 12px; padding: 14px;
  transition: all 0.15s;
}
.tool-card:hover { border-color: #e2e8f0; box-shadow: 0 2px 8px rgba(0,0,0,0.06); }
.tool-top { display: flex; align-items: center; gap: 10px; margin-bottom: 8px; }
.tool-emoji { font-size: 20px; flex-shrink: 0; }
.tool-meta { flex: 1; min-width: 0; }
.tool-name { font-size: 13px; font-weight: 700; color: #374151; }
.tool-code { font-size: 10px; color: #6b7280; background: #f1f5f9; padding: 1px 5px; border-radius: 3px; display: inline-block; margin-top: 2px; }
.tool-desc { font-size: 12px; color: #6b7280; line-height: 1.5; margin-bottom: 10px; }
.tool-footer { display: flex; justify-content: space-between; align-items: center; }
.tool-tag { font-size: 10px; padding: 2px 7px; border-radius: 4px; font-weight: 600; }
.tool-tag.free { background: #d1fae5; color: #059669; }
.tool-tag.paid { background: #fef3c7; color: #d97706; }
.tool-tag.experimental { background: #f3e8ff; color: #7c3aed; }
.tool-cost { font-size: 11px; color: #9ca3af; }

/* ===== 自定义工具 ===== */
.custom-tools-list { display: flex; flex-direction: column; gap: 8px; margin-bottom: 16px; }
.ct-item {
  display: flex; align-items: center; gap: 12px;
  padding: 12px; border: 1px solid #f1f5f9; border-radius: 10px;
}
.ct-icon { font-size: 18px; }
.ct-info { flex: 1; }
.ct-name { font-size: 13px; font-weight: 600; color: #374151; }
.ct-desc { font-size: 12px; color: #9ca3af; }
.ct-enabled { font-size: 11px; padding: 2px 7px; border-radius: 4px; font-weight: 600; }
.ct-enabled.on { background: #d1fae5; color: #059669; }
.ct-enabled.off { background: #f1f5f9; color: #9ca3af; }
.ct-del {
  width: 24px; height: 24px; border-radius: 50%; border: none;
  background: #fee2e2; color: #dc2626; cursor: pointer;
  font-size: 14px; display: flex; align-items: center; justify-content: center;
}

.empty-custom {
  padding: 24px; text-align: center; color: #9ca3af; font-size: 13px;
  border: 2px dashed #f1f5f9; border-radius: 10px;
}

.add-tool-form {
  margin-top: 16px; padding: 20px; background: #f8fafc;
  border-radius: 12px; border: 1px solid #e5e7eb;
}
.add-tool-form h4 { font-size: 14px; font-weight: 700; color: #374151; margin: 0 0 16px; }
.form-row { display: flex; flex-direction: column; gap: 4px; margin-bottom: 12px; }
.form-row label { font-size: 12px; font-weight: 600; color: #6b7280; }
.form-input, .form-textarea {
  border: 1px solid #e5e7eb; border-radius: 8px; padding: 8px 12px;
  font-size: 13px; color: #374151; outline: none; transition: border-color 0.15s;
  font-family: inherit;
}
.form-input:focus, .form-textarea:focus { border-color: #2563eb; }
.form-textarea { resize: vertical; }
.form-actions { display: flex; gap: 10px; justify-content: flex-end; margin-top: 8px; }

/* ===== 开关组件 ===== */
.toggle { position: relative; display: inline-block; width: 40px; height: 22px; flex-shrink: 0; }
.toggle input { opacity: 0; width: 0; height: 0; }
.toggle .slider {
  position: absolute; cursor: pointer; top: 0; left: 0; right: 0; bottom: 0;
  background: #e2e8f0; border-radius: 22px; transition: 0.3s;
}
.toggle .slider:before {
  content: ''; position: absolute;
  height: 16px; width: 16px; left: 3px; bottom: 3px;
  background: white; border-radius: 50%; transition: 0.3s;
  box-shadow: 0 1px 3px rgba(0,0,0,0.2);
}
.toggle input:checked + .slider { background: #2563eb; }
.toggle input:checked + .slider:before { transform: translateX(18px); }
.toggle.locked { opacity: 0.4; pointer-events: none; }

/* ===== 底部操作栏 ===== */
.bottom-bar {
  display: flex; align-items: center; gap: 16px;
  padding: 16px 0;
}
.save-hint { flex: 1; font-size: 13px; color: #9ca3af; }
.saved-tip { font-size: 13px; color: #059669; font-weight: 600; }

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
.btn-primary.large { padding: 10px 28px; font-size: 14px; }
</style>
