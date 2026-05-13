<template>
  <div class="flex items-center gap-4">
    <!-- 模型选择 · shadcn Select -->
    <div class="w-[220px]">
      <Select :model-value="currentModel" @update:model-value="handleModelChange">
        <SelectTrigger class="w-full">
          <div class="flex items-center gap-2 min-w-0">
            <Cpu class="h-4 w-4 shrink-0 opacity-70" />
            <SelectValue placeholder="Select Model" />
          </div>
        </SelectTrigger>
        <SelectContent>
          <SelectItem value="kimi-k2-0905-preview">Kimi (K2 0905 Preview)</SelectItem>
          <SelectItem value="deepseek-chat">DeepSeek-V3.2</SelectItem>
          <SelectItem value="qwen3.5-flash">Qwen 3.5 Flash（阿里云百炼）</SelectItem>
        </SelectContent>
      </Select>
    </div>

    <!-- Solo 开关 · Switch + 标签容器（Tooltip 只包 label，不包 Switch，避免事件耦合）-->
    <div
      :class="[
        'flex items-center gap-2 px-3 py-1.5 rounded-[var(--radius)] border font-semibold text-sm select-none transition-colors',
        store.enableSolo
          ? 'border-primary text-primary bg-primary/5 shadow-[0_0_0_1px_var(--color-primary)_inset]'
          : 'border-[var(--border-color)] text-[var(--text-primary)] bg-[var(--bg-primary)] hover:border-primary/50'
      ]"
    >
      <Tooltip>
        <TooltipTrigger as-child>
          <span class="flex items-center gap-1.5 cursor-help">
            <MagicStick class="h-4 w-4" />
            <span class="tracking-wider">Solo</span>
          </span>
        </TooltipTrigger>
        <TooltipContent side="bottom">
          Solo 模式：由 Agent 自主决定是否检索知识库 / 联网 / 调用工具 / 深度思考；开启后上方的手动开关将由 Agent 接管。
        </TooltipContent>
      </Tooltip>
      <Switch
        :model-value="store.enableSolo"
        @update:model-value="handleSoloBeforeChange"
      />
    </div>

    <!-- 三开关折叠进"设置"下拉；Solo 打开时整体禁用
         注意：Popover 和 Tooltip 不能共用一个 as-child（嵌套 as-child 会让事件无法到达真实 DOM）；
         设置按钮自身含"设置"文字和 Badge 角标已够表意，外层不再套 Tooltip。-->
    <Popover>
      <PopoverTrigger as-child>
        <button
          type="button"
          :disabled="store.enableSolo"
          :class="[
            'inline-flex items-center gap-2 h-9 px-4 rounded-[var(--radius)] border text-sm font-semibold transition-colors relative box-border',
            store.enableSolo
              ? 'border-[var(--border-color)] bg-[var(--bg-primary)] text-[var(--text-secondary)] opacity-55 cursor-not-allowed'
              : 'border-[var(--border-color)] bg-[var(--bg-primary)] text-[var(--text-primary)] hover:bg-[var(--bg-tertiary)] hover:border-primary/50 hover:text-primary cursor-pointer'
          ]"
        >
          <Lock v-if="store.enableSolo" class="h-4 w-4" />
          <Setting v-else class="h-4 w-4" />
          <span>设置</span>
          <Badge
            v-if="!store.enableSolo && enabledCount > 0"
            variant="default"
            class="ml-1"
          >
            {{ enabledCount }}
          </Badge>
        </button>
      </PopoverTrigger>

      <PopoverContent class="w-[320px] p-2" align="end" :side-offset="8">
        <div class="text-xs text-[var(--text-secondary)] tracking-wide uppercase mb-2 px-1">
          对话选项
        </div>

        <!-- 注：Popover 内的每一行不再用 Tooltip 包裹（Tooltip+Switch 同容器会让 Switch 点击被
             TooltipTrigger 截住）。row-desc 小字已经写清楚状态，信息等价。-->

        <!-- Knowledge Base -->
        <div
          :class="[
            'flex items-center justify-between gap-3 p-2 rounded-[var(--radius)] transition-colors',
            !store.embeddingReady
              ? 'opacity-55'
              : 'hover:bg-[var(--bg-tertiary)]'
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

        <!-- Web Search -->
        <div class="flex items-center justify-between gap-3 p-2 rounded-[var(--radius)] hover:bg-[var(--bg-tertiary)] transition-colors">
          <div class="flex flex-col gap-0.5 min-w-0 flex-1 pr-3">
            <div class="text-sm font-semibold text-[var(--text-primary)]">Web Search</div>
            <div class="text-xs text-[var(--text-secondary)] leading-snug">
              {{ useWebSearch ? '已开启：SerpApi 联网' : '已关闭' }}
            </div>
          </div>
          <Switch
            :model-value="useWebSearch"
            @update:model-value="(v: boolean) => (useWebSearch = v)"
          />
        </div>

        <div class="border-t border-dashed border-[var(--border-color)] my-1 mx-1" />

        <!-- Deep Think -->
        <div
          :class="[
            'flex items-center justify-between gap-3 p-2 rounded-[var(--radius)] transition-colors',
            !isDeepSeekModel
              ? 'opacity-55'
              : 'hover:bg-[var(--bg-tertiary)]'
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

    <!-- Manage Files -->
    <Button variant="outline" @click="goToKnowledgeBase">
      <Files class="h-4 w-4" />
      Manage Files
    </Button>
  </div>
</template>

<script setup lang="ts">
/**
 * 2026-04 · ConfigPanel 从 Element Plus 迁到 shadcn-vue。
 * 保留所有业务逻辑：模型切换、Solo :before-change 拦截 + 自动切 DeepSeek、
 * Deep Think 仅 DeepSeek 可用、Embedding 轮询、enabledCount badge。
 * UI 元素对应关系：
 *   el-select     → Select / SelectTrigger / SelectContent / SelectItem / SelectValue
 *   el-switch     → Switch（reka-ui 的 SwitchRoot）
 *   el-popover    → Popover（reka-ui，内容放 PopoverContent）
 *   el-tooltip    → Tooltip + TooltipContent（provider 在 ChatLayout 顶层包一次）
 *   el-button     → Button（variant="outline"）
 *   el-badge      → Badge
 *   el-icon       → 保留 @element-plus/icons-vue 图标（不换，减少改动）
 */
import { computed, watch, onMounted, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import { useChatStore } from '../store/chat'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Files, Cpu, Setting, MagicStick, Lock } from '@element-plus/icons-vue'

import { Button } from '@/components/ui/button'
import { Switch } from '@/components/ui/switch'
import { Select, SelectTrigger, SelectContent, SelectItem, SelectValue } from '@/components/ui/select'
import { Tooltip, TooltipTrigger, TooltipContent } from '@/components/ui/tooltip'
import { Popover, PopoverTrigger, PopoverContent } from '@/components/ui/popover'
import { Badge } from '@/components/ui/badge'

const store = useChatStore()
const router = useRouter()

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
  set: (val) => store.setModel(val)
})

// shadcn Select 的 update:model-value 给我们 string|number|Array；窄化一下
const handleModelChange = (val: any) => {
  if (typeof val === 'string') store.setModel(val)
}

const useKnowledgeBase = computed({
  get: () => store.useKnowledgeBase,
  set: (val: boolean) => store.setUseKnowledgeBase(val)
})

const useWebSearch = computed({
  get: () => store.useWebSearch,
  set: (val: boolean) => store.setUseWebSearch(val)
})

const isDeepSeekModel = computed(() => store.currentModel.startsWith('deepseek'))

const enableThinking = computed({
  get: () => store.enableThinking,
  set: (val: boolean) => { store.enableThinking = val }
})

/**
 * Solo 开关拦截（等价于原 el-switch 的 :before-change）：
 *  - 关闭 → 直接通过
 *  - 打开 → 若 Embedding 未就绪先弹确认；接受则切到 DeepSeek，提示 toast
 * reka-ui 的 Switch 不支持 before-change，改用手动处理：根据目标值先询问再 set store。
 */
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
        {
          confirmButtonText: '继续开启',
          cancelButtonText: '取消',
          type: 'warning',
        }
      )
    } catch {
      // 用户点"取消"或关闭弹窗：不开启
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

watch(() => store.currentModel, (newModel) => {
  if (!newModel.startsWith('deepseek')) {
    store.enableThinking = false
  }
})

const goToKnowledgeBase = () => {
  router.push('/knowledge')
}

/** 设置下拉里"当前已开启数量" badge */
const enabledCount = computed(() => {
  let n = 0
  if (store.embeddingReady && useKnowledgeBase.value) n += 1
  if (useWebSearch.value) n += 1
  if (isDeepSeekModel.value && enableThinking.value) n += 1
  return n
})
</script>
