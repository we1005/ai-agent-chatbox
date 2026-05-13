<script setup lang="ts">
import type { HTMLAttributes } from 'vue'
import {
  TooltipContent, type TooltipContentEmits, type TooltipContentProps,
  TooltipPortal, useForwardPropsEmits,
} from 'reka-ui'
import { computed } from 'vue'
import { cn } from '@/lib/utils'

const props = withDefaults(
  defineProps<TooltipContentProps & { class?: HTMLAttributes['class'] }>(),
  { sideOffset: 4 },
)
const emits = defineEmits<TooltipContentEmits>()
const delegated = computed(() => {
  const { class: _class, ...rest } = props
  return rest
})
const forwarded = useForwardPropsEmits(delegated, emits)
</script>

<template>
  <TooltipPortal>
    <TooltipContent
      v-bind="forwarded"
      :class="cn(
        'z-50 overflow-hidden rounded-md bg-foreground text-background px-3 py-1.5 text-xs shadow-md max-w-xs',
        props.class
      )"
    >
      <slot />
    </TooltipContent>
  </TooltipPortal>
</template>
