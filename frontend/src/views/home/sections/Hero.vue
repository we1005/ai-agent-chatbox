<script setup lang="ts">
import { onMounted, ref, onUnmounted, computed } from 'vue'
import { useRouter } from 'vue-router'
import { ArrowRight, Sparkles } from 'lucide-vue-next'
import { brand } from '../brand'

const router = useRouter()

// 手写轻量 parallax：监听 scrollY，节流通过 rAF
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

const bgTransform = computed(() => `translate3d(0, ${scrollY.value * 0.3}px, 0)`)
const hanziTransform = computed(() => `translate3d(0, ${-scrollY.value * 0.5}px, 0)`)
</script>

<template>
  <section class="relative min-h-screen flex items-center overflow-hidden">
    <!-- 背景：Apple 发布页式渐变 + SVG 水墨纹理，纯矢量，永不错位 -->
    <div
      class="absolute inset-0 will-change-transform"
      :style="{ transform: bgTransform }"
    >
      <!-- 主渐变：米白 → 暖米 → 青灰（呼应朱砂/墨/绢纸） -->
      <div
        class="absolute inset-0"
        style="background:
          radial-gradient(1100px 750px at 18% 12%, rgba(180, 54, 26, 0.08), transparent 60%),
          radial-gradient(900px 600px at 88% 78%, rgba(80, 86, 120, 0.10), transparent 60%),
          radial-gradient(1400px 900px at 50% 110%, rgba(20, 20, 26, 0.12), transparent 55%),
          linear-gradient(180deg, #f6f4ee 0%, #fafaf7 55%, #eeece4 100%);"
      />
      <!-- 水墨飞白 SVG（抽象墨痕，单次加载、无网络依赖） -->
      <svg
        class="absolute inset-0 w-full h-full opacity-[0.09] mix-blend-multiply"
        viewBox="0 0 1600 900"
        preserveAspectRatio="xMidYMid slice"
        aria-hidden="true"
      >
        <defs>
          <filter id="ink-blur"><feGaussianBlur stdDeviation="6" /></filter>
        </defs>
        <g filter="url(#ink-blur)" fill="#14141a">
          <path d="M-50 620 C 200 540, 380 680, 620 600 S 1000 520, 1250 640 1700 600 1700 700 L1700 900 -50 900 Z" />
          <path d="M120 180 C 260 220, 410 140, 560 230 S 850 170, 960 260" stroke="#14141a" stroke-width="14" stroke-linecap="round" fill="none" opacity="0.55"/>
          <circle cx="1180" cy="240" r="80" opacity="0.4" />
          <path d="M1350 350 q 40 -90 110 -10" stroke="#14141a" stroke-width="10" stroke-linecap="round" fill="none" opacity="0.5"/>
        </g>
      </svg>
      <!-- 顶部/底部渐隐 -->
      <div class="absolute inset-0 bg-gradient-to-b from-[color:var(--home-canvas)]/0 via-transparent to-[color:var(--home-canvas)]" />
    </div>

    <!-- 装饰浮动汉字（大，极低透明度） -->
    <div class="absolute inset-0 pointer-events-none" :style="{ transform: hanziTransform }">
      <span class="hanzi-floating text-[22vw]" style="top: 8%; left: -2%; animation-delay: 0s">知</span>
      <span class="hanzi-floating text-[28vw]" style="top: 30%; right: -6%; animation-delay: 1.5s">鉴</span>
      <span class="hanzi-floating text-[18vw]" style="bottom: 4%; left: 38%; animation-delay: 3s">忆</span>
    </div>

    <!-- 内容 -->
    <div class="relative z-10 w-full max-w-6xl mx-auto px-6 pt-32 pb-20">
      <p class="font-caps text-[color:var(--home-ink-mute)] home-reveal">
        {{ brand.taglineEn }}
      </p>

      <h1 class="mt-8 font-chinese-display leading-[0.95] home-reveal home-reveal-delay-1" style="font-size: clamp(90px, 18vw, 240px);">
        {{ brand.chinese }}
      </h1>

      <div class="mt-2 flex items-baseline gap-4 flex-wrap home-reveal home-reveal-delay-2">
        <span class="font-english-display text-[color:var(--home-ink)]" style="font-size: clamp(48px, 8vw, 104px);">
          {{ brand.english }}
        </span>
        <span class="font-caps text-[color:var(--home-ink-mute)]">
          {{ brand.englishSub }}
        </span>
      </div>

      <p class="mt-8 max-w-2xl font-chinese-body text-xl md:text-2xl text-[color:var(--home-ink-soft)] home-reveal home-reveal-delay-2">
        {{ brand.tagline }}。<br />
        融 RAG 四路召回、LangGraph Agent、七层上下文工程与双时间记忆于一体。
      </p>

      <div class="mt-10 flex items-center gap-3 flex-wrap home-reveal home-reveal-delay-3">
        <button
          class="group px-6 py-3 rounded-full bg-[color:var(--home-ink)] text-white font-medium text-[15px] hover:bg-[color:var(--home-accent)] transition-colors flex items-center gap-2"
          @click="router.push('/')"
        >
          <Sparkles class="w-4 h-4" />
          开始对话
          <ArrowRight class="w-4 h-4 transition-transform group-hover:translate-x-0.5" />
        </button>
        <button
          class="px-6 py-3 rounded-full bg-white/70 backdrop-blur border border-[color:var(--home-line)] font-medium text-[15px] text-[color:var(--home-ink)] hover:bg-white transition-colors flex items-center gap-2"
          @click="router.push('/wiki')"
        >
          探索架构
          <ArrowRight class="w-4 h-4" />
        </button>
      </div>
    </div>

    <!-- 滚动提示 -->
    <div class="absolute bottom-8 left-1/2 -translate-x-1/2 font-caps text-[color:var(--home-ink-mute)] flex flex-col items-center gap-2 home-reveal home-reveal-delay-3">
      <span>Scroll</span>
      <span class="block w-px h-10 bg-gradient-to-b from-[color:var(--home-ink-mute)] to-transparent" />
    </div>
  </section>
</template>
