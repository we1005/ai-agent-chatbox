<script setup lang="ts">
import { useRouter } from 'vue-router'
import { Github } from 'lucide-vue-next'
import { brand } from '../brand'

const router = useRouter()
const year = new Date().getFullYear()
</script>

<template>
  <footer class="relative pt-24 pb-12 px-6 bg-[color:var(--home-ink)] text-white">
    <div class="max-w-6xl mx-auto">
      <!-- 古风题签 -->
      <div class="text-center">
        <p class="font-chinese-body text-3xl md:text-4xl leading-relaxed" style="letter-spacing: 0.08em;">
          博观而约取
          <span class="inline-block mx-4 align-middle w-10 h-px bg-white/30" />
          厚积而薄发
        </p>
        <p class="mt-4 font-caps text-white/50">— 苏轼 · 稼说送张琥</p>
      </div>

      <!-- 分栏 -->
      <div class="mt-20 grid md:grid-cols-4 gap-10 pb-10 border-b border-white/10">
        <div class="md:col-span-2">
          <div class="flex items-baseline gap-3 mb-3">
            <span class="font-chinese-display text-2xl">{{ brand.chinese }}</span>
            <span class="font-caps text-white/50">{{ brand.english }} · {{ brand.englishSub }}</span>
          </div>
          <p class="font-chinese-body text-sm text-white/60 max-w-md">
            {{ brand.tagline }}。融 RAG 四路召回、Agent 推理、七层上下文工程与双时间记忆于一体。
          </p>
        </div>

        <div>
          <p class="font-caps text-white/40 mb-3">Navigate</p>
          <ul class="space-y-2 text-sm">
            <li><button class="text-white/80 hover:text-white" @click="router.push('/')">开始对话</button></li>
            <li><button class="text-white/80 hover:text-white" @click="router.push('/wiki')">项目 Wiki</button></li>
            <li><button class="text-white/80 hover:text-white" @click="router.push('/knowledge')">知识库</button></li>
            <li><button class="text-white/80 hover:text-white" @click="router.push('/admin')">后台管理</button></li>
          </ul>
        </div>

        <div>
          <p class="font-caps text-white/40 mb-3">Links</p>
          <ul class="space-y-2 text-sm">
            <li>
              <a :href="brand.github" target="_blank" rel="noopener"
                 class="text-white/80 hover:text-white inline-flex items-center gap-1.5">
                <Github class="w-3.5 h-3.5" /> GitHub
              </a>
            </li>
            <li><button class="text-white/80 hover:text-white" @click="router.push('/wiki/bench-results')">评测结果</button></li>
            <li><button class="text-white/80 hover:text-white" @click="router.push('/wiki/context-engine')">Context Engine</button></li>
          </ul>
        </div>
      </div>

      <div class="mt-8 flex flex-wrap items-center justify-between gap-4 text-xs text-white/40 font-caps">
        <span>© {{ year }} {{ brand.english }} · All rights reserved</span>
        <span>Crafted with Vue 3 · Tailwind v4 · Vue Flow</span>
      </div>
    </div>
  </footer>
</template>
