<script setup lang="ts">
import { brand } from '../brand'
</script>

<template>
  <section class="relative py-32 px-6 overflow-hidden">
    <div class="max-w-6xl mx-auto grid md:grid-cols-[1.15fr_1fr] gap-16 items-center">
      <!-- 左：题跋式引言 -->
      <div
        v-motion
        :initial="{ opacity: 0, y: 40 }"
        :visible-once="{ opacity: 1, y: 0, transition: { duration: 700 } }"
      >
        <p class="font-caps text-[color:var(--home-accent)] mb-4">Philosophy · 何以鉴</p>
        <h2 class="font-chinese-display text-4xl md:text-5xl leading-tight text-[color:var(--home-ink)]">
          知识不应沉默于索引，<br />
          而该在<span class="text-[color:var(--home-accent)]">对话</span>中被<span class="text-[color:var(--home-accent)]">映照</span>。
        </h2>
        <p class="mt-8 font-chinese-body text-[17px] text-[color:var(--home-ink-soft)] max-w-xl">
          大模型丰沃而易忘其所自；检索精准而少通其情理。{{ brand.chinese }}取「玄」之幽深以容知识黑盒，<br />
          藉「鉴」之映照以勘验思辨——令每一次询问皆可溯源、每一次回答皆能反思。
        </p>

        <div class="mt-10 flex items-center gap-6">
          <div class="seal">
            <span>博</span><span>观</span><span>约</span><span>取</span>
          </div>
          <div class="font-chinese-body text-sm text-[color:var(--home-ink-mute)]">
            博观而约取 · 厚积而薄发
          </div>
        </div>
      </div>

      <!-- 右：SVG 山水意象 + 毛玻璃数据卡叠放 -->
      <div
        class="relative"
        v-motion
        :initial="{ opacity: 0, scale: 0.96 }"
        :visible-once="{ opacity: 1, scale: 1, transition: { duration: 800, delay: 150 } }"
      >
        <!-- 主视觉：纯 SVG 山水 · 不依赖任何外部图 -->
        <div
          class="rounded-3xl overflow-hidden shadow-2xl aspect-[4/5] relative"
          style="background:
            radial-gradient(120% 80% at 30% 10%, rgba(180, 54, 26, 0.18), transparent 60%),
            linear-gradient(180deg, #f8f5ee 0%, #e8e3d4 55%, #c9c1ab 100%);"
        >
          <svg
            class="absolute inset-0 w-full h-full"
            viewBox="0 0 400 500"
            preserveAspectRatio="xMidYMid slice"
            aria-hidden="true"
          >
            <defs>
              <filter id="ink-wash"><feGaussianBlur stdDeviation="1.2" /></filter>
              <linearGradient id="mountain-g" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0" stop-color="#2e2e38" stop-opacity="0.85" />
                <stop offset="1" stop-color="#2e2e38" stop-opacity="0.45" />
              </linearGradient>
            </defs>
            <!-- 三重远山：远 → 近，颜色逐层加深 -->
            <g filter="url(#ink-wash)">
              <path d="M0 280 L 50 230 L 100 260 L 160 200 L 220 245 L 290 215 L 360 245 L 400 225 L 400 500 L 0 500 Z" fill="url(#mountain-g)" opacity="0.35"/>
              <path d="M0 340 L 70 290 L 140 320 L 210 280 L 280 310 L 360 285 L 400 305 L 400 500 L 0 500 Z" fill="url(#mountain-g)" opacity="0.55"/>
              <path d="M0 400 L 60 360 L 130 385 L 200 350 L 270 380 L 340 355 L 400 375 L 400 500 L 0 500 Z" fill="#14141a" opacity="0.82"/>
            </g>
            <!-- 太阳 / 月 -->
            <circle cx="295" cy="130" r="38" fill="#b4361a" opacity="0.78" />
            <!-- 水面倒影线 -->
            <g stroke="#14141a" stroke-linecap="round" opacity="0.25">
              <line x1="40" y1="440" x2="100" y2="440" stroke-width="1.5"/>
              <line x1="150" y1="455" x2="240" y2="455" stroke-width="1.2"/>
              <line x1="60" y1="470" x2="190" y2="470" stroke-width="1"/>
              <line x1="220" y1="480" x2="360" y2="480" stroke-width="1"/>
            </g>
            <!-- 书法感印章在右下 -->
            <g transform="translate(330 432) rotate(-4)">
              <rect x="0" y="0" width="38" height="38" fill="#b4361a" rx="3"/>
              <text x="19" y="17" text-anchor="middle" fill="#fff" font-family="LXGW WenKai Screen, STKaiti, serif" font-size="11" font-weight="700">映照</text>
              <text x="19" y="30" text-anchor="middle" fill="#fff" font-family="LXGW WenKai Screen, STKaiti, serif" font-size="11" font-weight="700">万象</text>
            </g>
          </svg>
        </div>

        <!-- 浮在图上的玻璃数据卡 -->
        <div class="glass absolute -bottom-8 -left-8 right-12 p-6">
          <p class="font-caps text-[color:var(--home-ink-mute)] mb-3">At a Glance</p>
          <div class="grid grid-cols-3 gap-4">
            <div>
              <div class="font-english-display text-3xl text-[color:var(--home-ink)]">7</div>
              <div class="text-xs text-[color:var(--home-ink-soft)] mt-1">层上下文</div>
            </div>
            <div>
              <div class="font-english-display text-3xl text-[color:var(--home-ink)]">10</div>
              <div class="text-xs text-[color:var(--home-ink-soft)] mt-1">RAG 配置</div>
            </div>
            <div>
              <div class="font-english-display text-3xl text-[color:var(--home-accent)]">0.97</div>
              <div class="text-xs text-[color:var(--home-ink-soft)] mt-1">Recall@K</div>
            </div>
          </div>
        </div>
      </div>
    </div>
  </section>
</template>
