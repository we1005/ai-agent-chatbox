<script setup lang="ts">
import type { HTMLAttributes } from 'vue'
import { SelectIcon, SelectTrigger, type SelectTriggerProps, useForwardProps } from 'reka-ui'
import { ChevronDown } from 'lucide-vue-next'
import { computed } from 'vue'
import { cn } from '@/lib/utils'

const props = defineProps<SelectTriggerProps & { class?: HTMLAttributes['class'] }>()
const delegated = computed(() => {
  const { class: _class, ...rest } = props
  return rest
})
const forwarded = useForwardProps(delegated)
</script>

<template>
  <SelectTrigger
    v-bind="forwarded"
    :class="cn(
      'flex h-9 w-full items-center justify-between rounded-[var(--radius)] border border-input bg-background px-3 py-2 text-sm font-medium text-foreground ring-offset-background placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50 transition-colors hover:border-primary/50 box-border',
      props.class
    )"
  >
    <slot />
    <SelectIcon as-child>
      <ChevronDown class="h-4 w-4 opacity-60 shrink-0" />
    </SelectIcon>
  </SelectTrigger>
</template>
