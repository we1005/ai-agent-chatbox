<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue'

interface Stat {
  value: number
  suffix?: string
  decimals?: number
  label: string
  caption: string
}

const stats: Stat[] = [
  { value: 60, label: 'Bench Queries', caption: 'CRUD-RAG mini · RAGAS judged' },
  { value: 10, label: 'RAG Configs', caption: '4 classic · 5 graph · 1 off' },
  { value: 7, label: 'Context Layers', caption: 'Identity → View · OpenHands' },
  { value: 4, label: 'LLMs', caption: 'DeepSeek · Kimi · Doubao · Ark' },
  { value: 5, label: 'Agent Tools', caption: 'KB · Web · Weather · Think · Catalog' },
  { value: 0.970, decimals: 3, label: 'Peak Recall@K', caption: 'graph_mix · 2026-04-23' },
]

const displayed = ref<number[]>(stats.map(() => 0))
const sectionRef = ref<HTMLElement | null>(null)
let observer: IntersectionObserver | null = null

function animateCount() {
  const duration = 1400
  const start = performance.now()
  const targets = stats.map(s => s.value)

  function tick(t: number) {
    const p = Math.min(1, (t - start) / duration)
    // easeOutCubic
    const e = 1 - Math.pow(1 - p, 3)
    displayed.value = targets.map(v => v * e)
    if (p < 1) requestAnimationFrame(tick)
    else displayed.value = targets.slice()
  }
  requestAnimationFrame(tick)
}

onMounted(() => {
  if (!sectionRef.value) return
  observer = new IntersectionObserver(entries => {
    for (const e of entries) {
      if (e.isIntersecting) {
        animateCount()
        observer?.disconnect()
        break
      }
    }
  }, { threshold: 0.3 })
  observer.observe(sectionRef.value)
})
onUnmounted(() => observer?.disconnect())

function fmt(i: number) {
  const s = stats[i]
  const v = displayed.value[i]
  return s.decimals ? v.toFixed(s.decimals) : Math.round(v).toString()
}
</script>

<template>
  <section
    ref="sectionRef"
    class="relative py-28 px-6 bg-[color:var(--home-ink)] text-white overflow-hidden"
  >
    <!-- 底纹：淡竖线 -->
    <div
      class="absolute inset-0 opacity-[0.06] pointer-events-none"
      style="background-image: linear-gradient(90deg, #fff 1px, transparent 1px); background-size: 80px 100%;"
    />

    <div class="relative max-w-6xl mx-auto">
      <div class="mb-16">
        <p class="font-caps text-white/50 mb-3">Numbers · 可度量</p>
        <h2 class="font-chinese-display text-4xl md:text-5xl leading-tight">
          不只是 demo · 是<span class="text-[color:var(--home-accent-soft)]">被评测</span>的系统
        </h2>
      </div>

      <div class="grid grid-cols-2 md:grid-cols-3 gap-10 md:gap-14">
        <div v-for="(s, i) in stats" :key="s.label">
          <div class="font-english-display tabular text-5xl md:text-6xl text-white">
            {{ fmt(i) }}<span v-if="s.suffix" class="text-white/60">{{ s.suffix }}</span>
          </div>
          <div class="mt-3 font-caps text-white/70">{{ s.label }}</div>
          <div class="mt-1 text-sm text-white/50">{{ s.caption }}</div>
        </div>
      </div>
    </div>
  </section>
</template>
