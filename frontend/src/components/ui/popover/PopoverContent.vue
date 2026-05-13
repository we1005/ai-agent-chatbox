<script setup lang="ts">
import type { HTMLAttributes } from 'vue'
import {
  PopoverContent, type PopoverContentEmits, type PopoverContentProps,
  PopoverPortal, useForwardPropsEmits,
} from 'reka-ui'
import { computed } from 'vue'
import { cn } from '@/lib/utils'

const props = withDefaults(
  defineProps<PopoverContentProps & { class?: HTMLAttributes['class'] }>(),
  { align: 'center', sideOffset: 6 },
)
const emits = defineEmits<PopoverContentEmits>()
const delegated = computed(() => {
  const { class: _class, ...rest } = props
  return rest
})
const forwarded = useForwardPropsEmits(delegated, emits)
</script>

<template>
  <PopoverPortal>
    <PopoverContent
      v-bind="forwarded"
      :class="cn(
        'z-50 w-72 rounded-[var(--radius)] border border-border bg-popover p-3 text-popover-foreground shadow-md outline-none',
        props.class
      )"
    >
      <slot />
    </PopoverContent>
  </PopoverPortal>
</template>
