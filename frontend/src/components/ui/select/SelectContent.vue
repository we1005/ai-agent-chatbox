<script setup lang="ts">
import type { HTMLAttributes } from 'vue'
import {
  SelectContent, type SelectContentEmits, type SelectContentProps,
  SelectPortal, SelectViewport,
  useForwardPropsEmits,
} from 'reka-ui'
import { computed } from 'vue'
import { cn } from '@/lib/utils'

const props = withDefaults(
  defineProps<SelectContentProps & { class?: HTMLAttributes['class'] }>(),
  { position: 'popper' },
)
const emits = defineEmits<SelectContentEmits>()

const delegated = computed(() => {
  const { class: _class, ...rest } = props
  return rest
})
const forwarded = useForwardPropsEmits(delegated, emits)
</script>

<template>
  <SelectPortal>
    <SelectContent
      v-bind="forwarded"
      :class="cn(
        'relative z-50 min-w-[8rem] overflow-hidden rounded-[var(--radius)] border border-border bg-popover text-popover-foreground shadow-md',
        position === 'popper' && 'data-[side=bottom]:translate-y-1 data-[side=top]:-translate-y-1',
        props.class
      )"
    >
      <SelectViewport
        :class="cn('p-1', position === 'popper' && 'h-[var(--reka-select-trigger-height)] w-full min-w-[var(--reka-select-trigger-width)]')"
      >
        <slot />
      </SelectViewport>
    </SelectContent>
  </SelectPortal>
</template>
