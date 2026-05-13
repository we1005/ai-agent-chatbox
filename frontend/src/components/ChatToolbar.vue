<template>
  <!--
    2026-04 · 从 ConfigPanel.vue 抽出三个核心控件（Model / Solo / 设置），
    供 InputBox 在消息框底部嵌入显示（ChatGPT 式工具栏）。
    业务逻辑（Solo before-change 确认 / model watch / Embedding 轮询 / badge 计数）
    与 ConfigPanel 完全等价，UI 改成紧凑 pill 排版。
  -->
  <div class="flex items-center gap-1.5 flex-wrap">
    <!-- 模型选择 · 纯图标按钮（hover 出 Tooltip 显示当前模型 + 提示） -->
    <Tooltip>
      <TooltipTrigger as-child>
        <div>
          <Select :model-value="currentModel" @update:model-value="handleModelChange">
            <SelectTrigger
              class="icon-btn p-0 [&>svg.lucide-chevron-down]:hidden"
              aria-label="切换模型"
            >
              <Cpu class="h-4 w-4" />
              <SelectValue class="sr-only" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="kimi-k2-0905-preview">Kimi (K2 0905 Preview)</SelectItem>
              <SelectItem value="deepseek-chat">DeepSeek-V3.2</SelectItem>
              <SelectItem value="qwen3.5-flash">Qwen 3.5 Flash（阿里云百炼）</SelectItem>
            </SelectContent>
          </Select>
        </div>
      </TooltipTrigger>
      <TooltipContent side="top">
        <div class="flex flex-col gap-0.5">
          <span class="font-semibold">切换模型</span>
          <span class="text-[10px] opacity-80">当前：{{ currentModelLabel }}</span>
        </div>
      </TooltipContent>
    </Tooltip>

    <!-- Solo · 纯图标按钮（点击直接切 · 开启时图标变色） -->
    <Tooltip>
      <TooltipTrigger as-child>
        <button
          type="button"
          @click="handleSoloBeforeChange(!store.enableSolo)"
          :class="[
            'icon-btn',
            store.enableSolo
              ? '!border-primary !text-primary !bg-primary/10 shadow-[0_0_0_1px_var(--color-primary)_inset]'
              : ''
          ]"
          :aria-pressed="store.enableSolo"
          aria-label="Solo 模式"
        >
          <MagicStick class="h-4 w-4" />
        </button>
      </TooltipTrigger>
      <TooltipContent side="top">
        <div class="flex flex-col gap-0.5 max-w-[240px]">
          <span class="font-semibold">Solo · {{ store.enableSolo ? '已开启' : '未开启' }}</span>
          <span class="text-[10px] opacity-80 leading-snug">
            Agent 自主决定检索 / 联网 / 工具 / 思考；开启后下方"设置"由 Agent 接管。
          </span>
        </div>
      </TooltipContent>
    </Tooltip>

    <!-- 设置 · 纯图标按钮 + Popover；右上角小红点显示 enabledCount。
         注：CLAUDE.md 明确 Popover + Tooltip 同 as-child 会破坏点击；这里改用原生 title 兜底。 -->
    <Popover>
      <PopoverTrigger as-child>
        <button
          type="button"
          :disabled="store.enableSolo"
          :title="store.enableSolo
            ? '设置已被 Solo 接管'
            : (enabledCount > 0 ? `对话选项（${enabledCount} 项已开启）` : '对话选项')"
          :class="[
            'icon-btn relative',
            store.enableSolo ? 'opacity-55 cursor-not-allowed' : ''
          ]"
          aria-label="对话选项"
        >
          <Lock v-if="store.enableSolo" class="h-4 w-4" />
          <Setting v-else class="h-4 w-4" />
          <span
            v-if="!store.enableSolo && enabledCount > 0"
            class="absolute -top-0.5 -right-0.5 min-w-[16px] h-4 px-1 rounded-full bg-primary text-white text-[10px] font-semibold leading-4 text-center"
          >{{ enabledCount }}</span>
        </button>
      </PopoverTrigger>

      <!-- side="top" 因为 InputBox 在视口底部，要往上弹 -->
      <PopoverContent class="w-[320px] p-2" align="start" side="top" :side-offset="8">
        <div class="text-xs text-[var(--text-secondary)] tracking-wide uppercase mb-2 px-1">
          对话选项
        </div>

        <!-- KB -->
        <div
          :class="[
            'flex items-center justify-between gap-3 p-2 rounded-[var(--radius)] transition-colors',
            !store.embeddingReady ? 'opacity-55' : 'hover:bg-[var(--bg-tertiary)]'
          ]"
        >
          <div class="flex flex-col gap-0.5 min-w-0 flex-1 pr-3">
            <div class="text-sm font-semibold text-[var(--text-primary)]">Knowledge Base</div>
            <div class="text-xs text-[var(--text-secondary)] leading-snug">
              {{ store.embeddingReady
                ? (useKnowledgeBase ? '已开启：每轮检索知识库' : '已关闭：不走 RAG')
                : '不可用：Embedding 未加载' }}
            </div>
          </div>
          <Switch
            :model-value="useKnowledgeBase"
            :disabled="!store.embeddingReady"
            @update:model-value="(v: boolean) => (useKnowledgeBase = v)"
          />
        </div>

        <div class="border-t border-dashed border-[var(--border-color)] my-1 mx-1" />

        <!-- Web -->
        <div class="flex items-center justify-between gap-3 p-2 rounded-[var(--radius)] hover:bg-[var(--bg-tertiary)] transition-colors">
          <div class="flex flex-col gap-0.5 min-w-0 flex-1 pr-3">
            <div class="text-sm font-semibold text-[var(--text-primary)]">Web Search</div>
            <div class="text-xs text-[var(--text-secondary)] leading-snug">
              {{ useWebSearch ? '已开启：SerpApi 联网' : '已关闭' }}
            </div>
          </div>
          <Switch :model-value="useWebSearch" @update:model-value="(v: boolean) => (useWebSearch = v)" />
        </div>

        <div class="border-t border-dashed border-[var(--border-color)] my-1 mx-1" />

        <!-- Deep Think -->
        <div
          :class="[
            'flex items-center justify-between gap-3 p-2 rounded-[var(--radius)] transition-colors',
            !isDeepSeekModel ? 'opacity-55' : 'hover:bg-[var(--bg-tertiary)]'
          ]"
        >
          <div class="flex flex-col gap-0.5 min-w-0 flex-1 pr-3">
            <div class="text-sm font-semibold text-[var(--text-primary)]">Deep Think</div>
            <div class="text-xs text-[var(--text-secondary)] leading-snug">
              {{ !isDeepSeekModel
                ? '不可用：当前模型非 DeepSeek'
                : (enableThinking ? '已开启：思考链流式输出' : '已关闭') }}
            </div>
          </div>
          <Switch
            :model-value="enableThinking"
            :disabled="!isDeepSeekModel"
            @update:model-value="(v: boolean) => (enableThinking = v)"
          />
        </div>
      </PopoverContent>
    </Popover>
  </div>
</template>

<script setup lang="ts">
import { computed, watch, onMounted, onUnmounted } from 'vue'
import { useChatStore } from '../store/chat'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Cpu, Setting, MagicStick, Lock } from '@element-plus/icons-vue'

import { Switch } from '@/components/ui/switch'
import { Select, SelectTrigger, SelectContent, SelectItem, SelectValue } from '@/components/ui/select'
import { Tooltip, TooltipTrigger, TooltipContent } from '@/components/ui/tooltip'
import { Popover, PopoverTrigger, PopoverContent } from '@/components/ui/popover'

const MODEL_LABELS: Record<string, string> = {
  'kimi-k2-0905-preview': 'Kimi (K2 0905 Preview)',
  'deepseek-chat': 'DeepSeek-V3.2',
  'qwen3.5-flash': 'Qwen 3.5 Flash（阿里云百炼）',
}
const currentModelLabel = computed(() => MODEL_LABELS[store.currentModel] ?? store.currentModel)

const store = useChatStore()

let embeddingPollTimer: ReturnType<typeof setInterval> | null = null

onMounted(() => {
  store.fetchEmbeddingStatus()
  embeddingPollTimer = setInterval(() => store.fetchEmbeddingStatus(), 8000)
})

onUnmounted(() => {
  if (embeddingPollTimer) {
    clearInterval(embeddingPollTimer)
    embeddingPollTimer = null
  }
})

const currentModel = computed({
  get: () => store.currentModel,
  set: (val) => store.setModel(val),
})
const handleModelChange = (val: any) => {
  if (typeof val === 'string') store.setModel(val)
}

const useKnowledgeBase = computed({
  get: () => store.useKnowledgeBase,
  set: (val: boolean) => store.setUseKnowledgeBase(val),
})
const useWebSearch = computed({
  get: () => store.useWebSearch,
  set: (val: boolean) => store.setUseWebSearch(val),
})
const isDeepSeekModel = computed(() => store.currentModel.startsWith('deepseek'))
const enableThinking = computed({
  get: () => store.enableThinking,
  set: (val: boolean) => { store.enableThinking = val },
})

/** Solo before-change：等同 ConfigPanel 原逻辑 */
const handleSoloBeforeChange = async (val: boolean | string) => {
  const turningOn = val === true
  if (!turningOn) {
    store.setEnableSolo(false)
    return
  }
  if (!store.embeddingReady) {
    try {
      await ElMessageBox.confirm(
        'Embedding 模型尚未加载，Solo 模式下的「知识库语义检索」工具将不可用；' +
          '天气、联网搜索、知识库目录查询等其它工具仍可正常使用。是否继续开启？',
        'RAG 不可用',
        { confirmButtonText: '继续开启', cancelButtonText: '取消', type: 'warning' }
      )
    } catch {
      return
    }
  }
  const { modelSwitched } = store.setEnableSolo(true)
  if (modelSwitched) {
    ElMessage.info({
      message: 'Solo 模式已自动切换到 DeepSeek（对 function calling 更稳定）。你仍可手动改回其它模型。',
      duration: 4000,
    })
  }
}

/** 切到非 DeepSeek 模型时强制关闭 Deep Think */
watch(() => store.currentModel, (m) => {
  if (!m.startsWith('deepseek')) store.enableThinking = false
})

const enabledCount = computed(() => {
  let n = 0
  if (store.embeddingReady && useKnowledgeBase.value) n += 1
  if (useWebSearch.value) n += 1
  if (isDeepSeekModel.value && enableThinking.value) n += 1
  return n
})
</script>

<style scoped>
/* 36×36 圆形纯图标按钮，hover 浅底，与 Apple/ChatGPT 工具栏风格一致 */
.icon-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 36px;
  height: 36px;
  border-radius: 9999px;
  border: 1px solid var(--border-color);
  background: var(--bg-primary);
  color: var(--text-secondary);
  transition: all 160ms cubic-bezier(0.2, 0.8, 0.2, 1);
  cursor: pointer;
  box-sizing: border-box;
}
.icon-btn:not(:disabled):hover {
  border-color: var(--color-primary);
  color: var(--color-primary);
  background: var(--bg-tertiary);
}
.icon-btn:focus-visible {
  outline: none;
  box-shadow: 0 0 0 2px var(--color-primary);
}
</style>
