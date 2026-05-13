<script setup lang="ts">
import { computed } from 'vue'
import { Handle, Position } from '@vue-flow/core'
import * as Lucide from 'lucide-vue-next'
import { getTheme, roleLabel } from '../lib/role-theme'
import type { RoleNodeData } from '../types'

const props = defineProps<{
  data: RoleNodeData
  selected?: boolean
}>()

const theme = computed(() => getTheme(props.data.role))

// data.icon 可以是字符串（lucide 名）或 Component
const IconComp = computed(() => {
  const i = props.data.icon
  if (!i) return theme.value.icon
  if (typeof i === 'string') {
    return (Lucide as Record<string, any>)[i] ?? theme.value.icon
  }
  return i
})
</script>

<template>
  <div
    class="role-node group rounded-xl border-2 bg-white shadow-md transition-all px-3 py-2 min-w-[140px] max-w-[200px]"
    :class="[
      theme.border,
      selected ? 'ring-2 ring-offset-2 ring-primary scale-[1.03]' : 'hover:shadow-lg hover:-translate-y-0.5',
    ]"
  >
    <Handle type="target" :position="Position.Left" class="!bg-zinc-400 !border-white !w-2 !h-2" />
    <!-- 辅助 handles：顶部/底部，用于 loop 等非线性连接（见 solo-graph 的 recursion 回边） -->
    <Handle id="top" type="target" :position="Position.Top" class="!bg-zinc-400 !border-white !w-2 !h-2 !opacity-0" />
    <Handle id="bottom" type="source" :position="Position.Bottom" class="!bg-zinc-400 !border-white !w-2 !h-2 !opacity-0" />

    <div class="flex items-center gap-2">
      <span
        class="inline-flex items-center justify-center w-7 h-7 rounded-lg text-white shadow-sm"
        :class="theme.bg"
      >
        <component :is="IconComp" class="w-4 h-4" />
      </span>
      <div class="flex flex-col min-w-0 flex-1">
        <span
          class="text-[10px] uppercase tracking-wider px-1.5 py-0.5 rounded self-start font-semibold"
          :class="theme.badge"
        >
          {{ roleLabel[data.role] ?? data.role }}
        </span>
        <span class="text-sm font-semibold text-zinc-900 truncate mt-0.5">{{ data.label }}</span>
      </div>
    </div>

    <Handle type="source" :position="Position.Right" class="!bg-zinc-400 !border-white !w-2 !h-2" />
  </div>
</template>

<style scoped>
.role-node {
  cursor: grab;
}
.role-node:active {
  cursor: grabbing;
}
</style>
