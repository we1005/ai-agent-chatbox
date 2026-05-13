<script setup lang="ts">
import { useRouter } from 'vue-router'
import { Workflow, Bot, Brain, Network, ArrowUpRight } from 'lucide-vue-next'

const router = useRouter()

const features = [
  {
    to: '/wiki/classic-pipeline',
    title: 'Classic · 四路 RAG',
    subtitle: 'Classical · Multi-Query · Agentic · Graph',
    desc: '端点层意图识别 → 分流 → 4 路召回 → 装配 → LLM 流式，每路可在线切换，线性链路，性能可预测。',
    icon: Workflow,
    gradient: 'from-sky-500/40 via-indigo-500/30 to-violet-500/40',
    accent: 'text-sky-600',
  },
  {
    to: '/wiki/solo-graph',
    title: 'Solo · Agent 推理',
    subtitle: 'LangGraph ReAct Loop',
    desc: 'planner ⇄ tools 循环到收敛，5 个工具自主调度；recursion_limit=16 硬防线，失败软兜底。',
    icon: Bot,
    gradient: 'from-violet-500/40 via-fuchsia-500/30 to-rose-500/40',
    accent: 'text-violet-600',
  },
  {
    to: '/wiki/context-engine',
    title: 'Context Engine v2',
    subtitle: 'Seven-Layer Context · Condenser Pipeline',
    desc: 'Identity → Recent → Summary → Memory → Retrieval → Runtime → View，OpenHands 式递归压缩算法。',
    icon: Brain,
    gradient: 'from-fuchsia-500/40 via-rose-500/30 to-orange-500/40',
    accent: 'text-fuchsia-600',
  },
  {
    to: '/wiki/memory-lifecycle',
    title: 'Graph RAG × 双时间记忆',
    subtitle: 'LightRAG 5-Mode · Mem0 Bi-Temporal',
    desc: 'LightRAG 实体/社区五档查询 · Mem0 ADD/UPDATE/DELETE/NOOP judge · Zep 双时间 schema。',
    icon: Network,
    gradient: 'from-emerald-500/40 via-teal-500/30 to-sky-500/40',
    accent: 'text-emerald-600',
  },
]
</script>

<template>
  <section class="relative py-32 px-6 bg-gradient-to-b from-transparent to-[#f3f1ea]">
    <div class="max-w-6xl mx-auto">
      <div
        class="mb-16 max-w-2xl"
        v-motion
        :initial="{ opacity: 0, y: 30 }"
        :visible-once="{ opacity: 1, y: 0, transition: { duration: 600 } }"
      >
        <p class="font-caps text-[color:var(--home-accent)] mb-3">Capabilities · 四境</p>
        <h2 class="font-chinese-display text-4xl md:text-5xl leading-tight">
          一站贯通：检索、推理、长忆、图谱
        </h2>
        <p class="mt-4 font-chinese-body text-[17px] text-[color:var(--home-ink-soft)]">
          每一项能力皆有独立详解，可点击进入项目 Wiki 的对应模块。
        </p>
      </div>

      <div class="grid md:grid-cols-2 gap-6">
        <button
          v-for="(f, i) in features"
          :key="f.to"
          @click="router.push(f.to)"
          class="feature-card glass text-center p-10 relative overflow-hidden group"
          v-motion
          :initial="{ opacity: 0, y: 40 }"
          :visible-once="{ opacity: 1, y: 0, transition: { duration: 600, delay: i * 80 } }"
        >
          <!-- 背景彩色 glow -->
          <div
            class="absolute -top-24 -right-24 w-80 h-80 rounded-full opacity-40 blur-3xl bg-gradient-to-br pointer-events-none"
            :class="f.gradient"
          ></div>

          <!-- 右上角跳转箭头：绝对定位，不参与内容居中计算 -->
          <ArrowUpRight
            class="absolute top-5 right-5 w-5 h-5 text-[color:var(--home-ink-mute)] transition-all group-hover:text-[color:var(--home-accent)] group-hover:-translate-y-0.5 group-hover:translate-x-0.5"
          />

          <div class="relative flex flex-col items-center">
            <!-- 图标独占一行，居中放置 -->
            <span
              class="inline-flex items-center justify-center w-14 h-14 rounded-2xl bg-white shadow-md border border-white/60 mb-5"
              :class="f.accent"
            >
              <component :is="f.icon" class="w-7 h-7" />
            </span>
            <!-- 英文副标 -->
            <span class="font-caps text-[color:var(--home-ink-mute)] mb-3">{{ f.subtitle }}</span>
            <!-- 中文大标 -->
            <h3 class="font-chinese-display text-2xl md:text-3xl text-[color:var(--home-ink)] mb-4">
              {{ f.title }}
            </h3>
            <!-- 正文：居中后限宽以改善长句折行节奏 -->
            <p class="font-chinese-body text-[15px] text-[color:var(--home-ink-soft)] max-w-sm">
              {{ f.desc }}
            </p>
          </div>
        </button>
      </div>
    </div>
  </section>
</template>
