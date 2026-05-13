<script setup lang="ts">
import { useRouter } from 'vue-router'
import { ref, onMounted, onUnmounted } from 'vue'
import {
  Workflow, Bot, Brain, MemoryStick, Boxes, BarChart3, ArrowLeft, Sparkles,
  ArrowUpRight, GitBranch,
} from 'lucide-vue-next'

const router = useRouter()

const cards = [
  {
    to: '/wiki/architecture',
    title: '系统架构',
    english: 'Architecture',
    caption: '前端 ↔ 后端 ↔ Mongo / Qdrant / LightRAG / Mem0 / MCP 全景',
    icon: Boxes,
    hue: '215 90% 62%',   // slate-blue
    tagline: 'L1 ~ L4 全景层',
  },
  {
    to: '/wiki/classic-pipeline',
    title: 'Classic 聊天流水线',
    english: 'Classic Pipeline',
    caption: 'intent → memory router → KB 4 路 → assembler → LLM → 引用解析',
    icon: Workflow,
    hue: '200 92% 54%',   // sky
    tagline: '10 节点线性链路',
  },
  {
    to: '/wiki/solo-graph',
    title: 'Solo Agent',
    english: 'LangGraph ReAct',
    caption: 'classify_complexity → planner ⇄ tools 循环 · recursion_limit=16',
    icon: Bot,
    hue: '270 82% 58%',   // violet
    tagline: '7 节点 + U 型回边',
  },
  {
    to: '/wiki/context-engine',
    title: '长上下文引擎 v2',
    english: 'Context Engine',
    caption: '7 层上下文模型 + Condenser Pipeline（OpenHands 算法）',
    icon: Brain,
    hue: '320 82% 58%',   // fuchsia
    tagline: '12 节点 2 列对照',
  },
  {
    to: '/wiki/memory-lifecycle',
    title: '记忆生命周期',
    english: 'Memory Lifecycle',
    caption: 'reflect_and_write · Mem0 ADD/UPDATE/DELETE/NOOP · 双时间 schema',
    icon: MemoryStick,
    hue: '158 68% 46%',   // emerald
    tagline: '9 节点时间链',
  },
  {
    to: '/wiki/rag-strategies',
    title: 'RAG 策略矩阵',
    english: 'RAG Strategies',
    caption: '10 配置 · Graph RAG 5 档 · Agentic 4 档 · 优先级硬编码',
    icon: Sparkles,
    hue: '35 95% 54%',    // amber
    tagline: '5 主 × 5 子模式',
  },
  {
    to: '/wiki/bench-results',
    title: '评测结果',
    english: 'Bench Results',
    caption: 'CRUD-mini · RAGAS DeepSeek judge · 10 × 60 = 600 trial',
    icon: BarChart3,
    hue: '348 83% 56%',   // rose
    tagline: '雷达 · 柱状 · 折线',
  },
]

// 鼠标追随的高光：为当前 hover 的卡片更新 --mx / --my CSS 变量
function onMouseMove(e: MouseEvent) {
  const el = e.currentTarget as HTMLElement
  const rect = el.getBoundingClientRect()
  el.style.setProperty('--mx', `${((e.clientX - rect.left) / rect.width) * 100}%`)
  el.style.setProperty('--my', `${((e.clientY - rect.top) / rect.height) * 100}%`)
}

// 背景 blob 视差（缓慢随滚动漂移）
const scrollY = ref(0)
let raf = 0
function onScroll() {
  cancelAnimationFrame(raf)
  raf = requestAnimationFrame(() => { scrollY.value = window.scrollY })
}
onMounted(() => window.addEventListener('scroll', onScroll, { passive: true }))
onUnmounted(() => {
  cancelAnimationFrame(raf)
  window.removeEventListener('scroll', onScroll)
})
</script>

<template>
  <div class="wiki-root relative min-h-screen overflow-hidden">
    <!-- SVG 置换滤镜：给液态玻璃卡片一点"折射扭曲"的感觉 -->
    <svg class="svg-defs" aria-hidden="true" width="0" height="0">
      <filter id="wiki-liquid" x="-5%" y="-5%" width="110%" height="110%">
        <feTurbulence type="fractalNoise" baseFrequency="0.012 0.012" numOctaves="2" seed="3" result="noise"/>
        <feDisplacementMap in="SourceGraphic" in2="noise" scale="4" xChannelSelector="R" yChannelSelector="G"/>
      </filter>
    </svg>

    <!-- 环境背景：多层模糊彩色 blob，做视差漂浮 -->
    <div
      class="ambient"
      :style="{ transform: `translate3d(0, ${scrollY * 0.25}px, 0)` }"
    >
      <div class="blob b1"></div>
      <div class="blob b2"></div>
      <div class="blob b3"></div>
      <div class="blob b4"></div>
      <!-- 细格纹底色 -->
      <div class="grid-pattern"></div>
    </div>

    <!-- 主内容 -->
    <div class="relative z-10 max-w-6xl mx-auto px-6 pt-12 pb-24">
      <!-- Header -->
      <header
        v-motion
        :initial="{ opacity: 0, y: -16 }"
        :enter="{ opacity: 1, y: 0, transition: { duration: 500 } }"
      >
        <div class="flex items-center justify-between gap-3 mb-6 flex-wrap">
          <button
            class="inline-flex items-center gap-1.5 text-sm text-zinc-500 hover:text-zinc-900 transition px-3 py-1.5 rounded-full hover:bg-white/60 backdrop-blur"
            @click="router.push('/home')"
          >
            <ArrowLeft class="w-4 h-4" />
            返回首页
          </button>
          <button
            class="group inline-flex items-center gap-2 px-4 py-2 rounded-full bg-white/70 backdrop-blur-md border border-white/60 text-sm font-medium text-zinc-800 hover:bg-white shadow-sm hover:shadow-md transition-all"
            @click="router.push('/wiki-tree')"
          >
            <GitBranch class="w-4 h-4 text-[color:var(--wiki-accent)]" />
            <span>树状视图</span>
            <span class="text-xs text-zinc-400">· Tree View</span>
            <ArrowUpRight class="w-3.5 h-3.5 text-zinc-400 group-hover:text-zinc-900 group-hover:-translate-y-0.5 group-hover:translate-x-0.5 transition-all" />
          </button>
        </div>

        <p class="font-caps-wiki text-[color:var(--wiki-accent)] mb-3">Project Wiki · 技术手册</p>
        <h1 class="wiki-hero-title">
          架构一览无余，<br />
          动线一拖即见。
        </h1>
        <p class="mt-6 text-[17px] text-zinc-600 max-w-2xl leading-relaxed">
          用可拖拽节点图、流动的边、按角色配色的视觉语言，把 Classic Chat / Solo Agent /
          Context Engine v2 / 双时间记忆 / 10 种 RAG 策略 一次讲清楚。
          <span class="text-zinc-400"> 点击任一卡片进入子模块。</span>
        </p>
      </header>

      <!-- 卡片 grid -->
      <div class="mt-16 grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-5">
        <button
          v-for="(c, i) in cards"
          :key="c.to"
          @click="router.push(c.to)"
          @mousemove="onMouseMove"
          class="liquid-card group"
          :style="{ '--hue': c.hue } as any"
          v-motion
          :initial="{ opacity: 0, y: 30, scale: 0.96 }"
          :enter="{ opacity: 1, y: 0, scale: 1, transition: { duration: 550, delay: 120 + i * 70 } }"
        >
          <!-- 液态玻璃主体 -->
          <div class="liquid-body">
            <!-- 背景：accent 渐晕（用 hue 控制） -->
            <div class="bg-tint" aria-hidden="true"></div>
            <!-- 鼠标追随的高光 -->
            <div class="specular" aria-hidden="true"></div>
            <!-- 边缘高光（inset ring） -->
            <div class="edge-highlight" aria-hidden="true"></div>
          </div>

          <!-- 内容 -->
          <div class="liquid-content">
            <div class="flex items-start justify-between gap-3 mb-6">
              <div
                class="liquid-icon"
                :style="{
                  background: `linear-gradient(135deg, hsl(${c.hue} / 0.95), hsl(${c.hue} / 0.65))`,
                  boxShadow: `0 8px 24px -6px hsl(${c.hue} / 0.45), inset 0 1px 0 rgba(255,255,255,0.4)`
                } as any"
              >
                <component :is="c.icon" class="w-6 h-6 text-white" />
              </div>
              <ArrowUpRight class="w-5 h-5 text-zinc-400 group-hover:text-zinc-900 group-hover:-translate-y-0.5 group-hover:translate-x-0.5 transition-all" />
            </div>

            <p class="font-caps-wiki text-zinc-500 mb-1.5">{{ c.english }}</p>
            <h2 class="text-xl font-bold text-zinc-900 mb-2 tracking-tight">{{ c.title }}</h2>
            <p class="text-[13px] text-zinc-600 leading-snug mb-4 min-h-[2.6em]">{{ c.caption }}</p>

            <div class="flex items-center gap-2 pt-4 border-t border-zinc-900/5">
              <span
                class="inline-block w-1.5 h-1.5 rounded-full"
                :style="{ background: `hsl(${c.hue})` } as any"
              ></span>
              <span class="text-[11px] font-medium tracking-wider uppercase text-zinc-500">
                {{ c.tagline }}
              </span>
            </div>
          </div>
        </button>
      </div>

      <!-- Footer 题跋 -->
      <footer
        class="mt-20 text-center"
        v-motion
        :initial="{ opacity: 0 }"
        :enter="{ opacity: 1, transition: { duration: 800, delay: 900 } }"
      >
        <div class="inline-flex items-center gap-2 px-4 py-2 rounded-full bg-white/60 backdrop-blur-md border border-white/60">
          <Sparkles class="w-3.5 h-3.5 text-amber-500" />
          <span class="text-xs text-zinc-500">
            基于 Vue Flow · 数据驱动 · 改架构只改 <code class="text-zinc-700 font-mono">data/*.ts</code>
          </span>
        </div>
      </footer>
    </div>
  </div>
</template>

<style scoped>
/* ────────────────────────────────────────────────────────────
 * Wiki Home · 液态玻璃（Liquid Glass）· 仅限 .wiki-root 作用域
 * 参考：Apple visionOS / iOS 26 的 Liquid Glass material；
 * 技术栈：backdrop-filter + saturate + inset ring + specular
 * highlight + 鼠标追随高光 + SVG displacement（轻度折射）
 * ──────────────────────────────────────────────────────────── */

.wiki-root {
  --wiki-canvas: #f5f5f7;
  --wiki-accent: oklch(0.55 0.15 40);
  background: var(--wiki-canvas);
  font-family: 'Inter', 'Noto Serif SC', -apple-system, BlinkMacSystemFont, 'PingFang SC', sans-serif;
  color: #1d1d1f;
}

.svg-defs { position: absolute; width: 0; height: 0; }

/* ── Ambient 背景 ──────────────────────────────────── */
.ambient {
  position: fixed;
  inset: -10%;
  pointer-events: none;
  z-index: 0;
  will-change: transform;
}
.grid-pattern {
  position: absolute; inset: 0;
  background-image:
    linear-gradient(to right, rgba(0,0,0,0.04) 1px, transparent 1px),
    linear-gradient(to bottom, rgba(0,0,0,0.04) 1px, transparent 1px);
  background-size: 56px 56px;
  mask-image: radial-gradient(ellipse at center, #000 30%, transparent 75%);
  -webkit-mask-image: radial-gradient(ellipse at center, #000 30%, transparent 75%);
}
.blob {
  position: absolute;
  border-radius: 50%;
  filter: blur(80px);
  opacity: 0.55;
  animation: blob-drift 22s ease-in-out infinite alternate;
}
.blob.b1 { top: -4%; left: 8%;  width: 460px; height: 460px; background: radial-gradient(closest-side, hsl(215 92% 70% / 0.6), transparent); animation-delay: 0s; }
.blob.b2 { top: 18%; right: -6%; width: 520px; height: 520px; background: radial-gradient(closest-side, hsl(320 82% 70% / 0.55), transparent); animation-delay: -7s; }
.blob.b3 { bottom: -8%; left: 18%; width: 500px; height: 500px; background: radial-gradient(closest-side, hsl(35 92% 68% / 0.5), transparent); animation-delay: -14s; }
.blob.b4 { bottom: 6%; right: 16%; width: 420px; height: 420px; background: radial-gradient(closest-side, hsl(158 68% 60% / 0.45), transparent); animation-delay: -3s; }

@keyframes blob-drift {
  0%   { transform: translate(0, 0)      scale(1); }
  50%  { transform: translate(40px, -30px) scale(1.08); }
  100% { transform: translate(-30px, 20px) scale(0.95); }
}

/* ── Hero 标题 ──────────────────────────────────── */
.wiki-hero-title {
  font-family: 'Inter', sans-serif;
  font-weight: 800;
  font-size: clamp(40px, 6.2vw, 72px);
  line-height: 1.05;
  letter-spacing: -0.03em;
  color: #0a0a0a;
  background: linear-gradient(180deg, #0a0a0a 0%, #3a3a40 100%);
  -webkit-background-clip: text;
  background-clip: text;
  -webkit-text-fill-color: transparent;
}

.font-caps-wiki {
  font-family: 'Inter', sans-serif;
  font-weight: 500;
  letter-spacing: 0.28em;
  text-transform: uppercase;
  font-size: 11px;
}

/* ── Liquid Card ──────────────────────────────────── */
.liquid-card {
  position: relative;
  border-radius: 24px;
  padding: 0;
  cursor: pointer;
  border: 0;
  text-align: left;
  isolation: isolate;
  transition: transform 380ms cubic-bezier(0.2, 0.8, 0.2, 1);
  --mx: 50%;
  --my: 50%;
}

.liquid-card:hover {
  transform: translateY(-6px);
}

.liquid-body {
  position: absolute; inset: 0;
  border-radius: 24px;
  overflow: hidden;
  background: rgba(255, 255, 255, 0.55);
  -webkit-backdrop-filter: blur(24px) saturate(180%);
  backdrop-filter: blur(24px) saturate(180%);
  box-shadow:
    0 1px 1px rgba(255, 255, 255, 0.6) inset,
    0 -1px 1px rgba(255, 255, 255, 0.35) inset,
    0 10px 32px -12px rgba(20, 20, 30, 0.12),
    0 2px 6px rgba(20, 20, 30, 0.04);
  transition: box-shadow 380ms, background 380ms;
}

.liquid-card:hover .liquid-body {
  background: rgba(255, 255, 255, 0.72);
  box-shadow:
    0 1px 1px rgba(255, 255, 255, 0.7) inset,
    0 -1px 1px rgba(255, 255, 255, 0.4) inset,
    0 24px 48px -16px hsl(var(--hue) / 0.3),
    0 6px 14px rgba(20, 20, 30, 0.06);
}

/* 背景 accent 渐晕（按 hue 着色） */
.bg-tint {
  position: absolute; inset: 0;
  background:
    radial-gradient(80% 100% at 0% 0%, hsl(var(--hue) / 0.18), transparent 55%),
    radial-gradient(60% 80% at 100% 100%, hsl(var(--hue) / 0.10), transparent 60%);
  opacity: 0.8;
  transition: opacity 380ms;
}
.liquid-card:hover .bg-tint { opacity: 1; }

/* 鼠标追随的 specular（白色高光圆斑） */
.specular {
  position: absolute; inset: 0;
  background: radial-gradient(
    260px circle at var(--mx) var(--my),
    rgba(255, 255, 255, 0.55),
    rgba(255, 255, 255, 0) 55%
  );
  opacity: 0;
  transition: opacity 260ms;
  mix-blend-mode: overlay;
  pointer-events: none;
}
.liquid-card:hover .specular { opacity: 1; }

/* 边缘高光（内侧 1px ring，模拟玻璃侧面折射） */
.edge-highlight {
  position: absolute; inset: 0;
  border-radius: 24px;
  pointer-events: none;
  box-shadow:
    inset 0 0 0 1px rgba(255, 255, 255, 0.45),
    inset 0 0 0 2px hsl(var(--hue) / 0);
  transition: box-shadow 380ms;
}
.liquid-card:hover .edge-highlight {
  box-shadow:
    inset 0 0 0 1px rgba(255, 255, 255, 0.8),
    inset 0 0 0 2px hsl(var(--hue) / 0.28);
}

/* 内容层 */
.liquid-content {
  position: relative;
  z-index: 1;
  padding: 24px 22px 20px;
  min-height: 220px;
  display: flex;
  flex-direction: column;
}

.liquid-icon {
  width: 44px; height: 44px;
  border-radius: 14px;
  display: grid; place-items: center;
  transition: transform 320ms cubic-bezier(0.2, 0.8, 0.2, 1);
}
.liquid-card:hover .liquid-icon {
  transform: scale(1.06) rotate(-2deg);
}

/* ── prefers-reduced-motion ── */
@media (prefers-reduced-motion: reduce) {
  .blob, .liquid-card, .liquid-body, .liquid-icon, .edge-highlight, .specular, .bg-tint {
    animation: none !important;
    transition: none !important;
  }
}
</style>
