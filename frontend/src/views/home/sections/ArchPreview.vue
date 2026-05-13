<script setup lang="ts">
import { useRouter } from 'vue-router'
import { ArrowRight } from 'lucide-vue-next'

const router = useRouter()

// 简化的"架构图"：静态 SVG 示意，点进去看完整 /wiki/architecture
const layers = [
  { name: '前端', items: ['ChatLayout', 'KnowledgeBase', 'MemoryAudit', 'Wiki'] },
  { name: '后端', items: ['FastAPI', 'chat_service', 'solo/graph', 'memory_service'] },
  { name: '存储', items: ['MongoDB', 'Qdrant', 'LightRAG', 'Mem0'] },
  { name: '模型与外部', items: ['DeepSeek', 'Kimi', 'Doubao', '高德 MCP'] },
]
</script>

<template>
  <section class="relative py-32 px-6">
    <div class="max-w-6xl mx-auto grid md:grid-cols-[1fr_1.3fr] gap-16 items-center">
      <div
        v-motion
        :initial="{ opacity: 0, x: -30 }"
        :visible-once="{ opacity: 1, x: 0, transition: { duration: 700 } }"
      >
        <p class="font-caps text-[color:var(--home-accent)] mb-3">Architecture · 观其全</p>
        <h2 class="font-chinese-display text-4xl md:text-5xl leading-tight mb-6">
          从前端到模型，<br />一图俱览。
        </h2>
        <p class="font-chinese-body text-[17px] text-[color:var(--home-ink-soft)] mb-8">
          四层结构：前端组件 · 后端服务 · 本地持久化 · 外部模型与 MCP。
          完整架构以可拖拽节点图呈现，每节点可点击查看关联代码与设计文档。
        </p>
        <button
          class="group inline-flex items-center gap-2 px-6 py-3 rounded-full bg-[color:var(--home-ink)] text-white text-[15px] font-medium hover:bg-[color:var(--home-accent)] transition-colors"
          @click="router.push('/wiki/architecture')"
        >
          进入完整可视化
          <ArrowRight class="w-4 h-4 transition-transform group-hover:translate-x-0.5" />
        </button>
      </div>

      <div
        class="glass p-8 md:p-10"
        v-motion
        :initial="{ opacity: 0, y: 30 }"
        :visible-once="{ opacity: 1, y: 0, transition: { duration: 700, delay: 150 } }"
      >
        <div class="space-y-5">
          <div
            v-for="(layer, i) in layers"
            :key="layer.name"
            class="flex items-center gap-5"
          >
            <div class="font-caps w-16 text-right text-[color:var(--home-ink-mute)]">
              L{{ i + 1 }}
            </div>
            <div class="font-chinese-display text-lg text-[color:var(--home-ink)] w-16">
              {{ layer.name }}
            </div>
            <div class="flex-1 flex flex-wrap gap-2">
              <span
                v-for="item in layer.items"
                :key="item"
                class="px-3 py-1 rounded-full bg-white/80 border border-[color:var(--home-line)] text-xs text-[color:var(--home-ink-soft)] font-medium"
              >
                {{ item }}
              </span>
            </div>
          </div>
        </div>

        <div class="mt-8 pt-6 border-t border-[color:var(--home-line)] flex items-center justify-between text-xs text-[color:var(--home-ink-mute)] font-caps">
          <span>Click to explore</span>
          <span class="flex items-center gap-1">
            <span class="w-1.5 h-1.5 rounded-full bg-[color:var(--home-accent)] animate-pulse" />
            interactive
          </span>
        </div>
      </div>
    </div>
  </section>
</template>
