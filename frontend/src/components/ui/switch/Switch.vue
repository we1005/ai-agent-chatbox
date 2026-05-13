<script setup lang="ts">
import type { HTMLAttributes } from 'vue'
import {
  SwitchRoot,
  type SwitchRootEmits,
  type SwitchRootProps,
  SwitchThumb,
  useForwardPropsEmits,
} from 'reka-ui'
import { computed } from 'vue'
import { cn } from '@/lib/utils'

const props = defineProps<SwitchRootProps & { class?: HTMLAttributes['class'] }>()
const emits = defineEmits<SwitchRootEmits>()

const delegatedProps = computed(() => {
  const { class: _class, ...rest } = props
  return rest
})

const forwarded = useForwardPropsEmits(delegatedProps, emits)
</script>

<template>
  <SwitchRoot
    v-bind="forwarded"
    :class="cn(
      // 1) 浏览器默认 button 样式重置（无 Preflight，原生 <button> 的 appearance/padding/border/font 都会干扰）
      'appearance-none p-0 m-0',
      // 2) 布局：用 justify-start/end 直接放 thumb，比 translate-x 可靠
      'peer inline-flex h-5 w-9 shrink-0 cursor-pointer items-center rounded-full border-2 border-transparent transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background disabled:cursor-not-allowed disabled:opacity-50 box-border',
      'data-[state=checked]:bg-primary data-[state=checked]:justify-end',
      'data-[state=unchecked]:bg-muted-foreground/40 data-[state=unchecked]:justify-start',
      props.class
    )"
  >
    <SwitchThumb
      class="pointer-events-none block h-4 w-4 rounded-full bg-background shadow-sm ring-0 border-0"
    />
  </SwitchRoot>
</template>
