<script setup lang="ts">
// simpleicons.org 的 slug。CDN 返回纯色 SVG（默认黑），我们用 CSS filter 统一成深墨色。
// 不入仓、不阻塞首屏；加载失败时显示文字备用。
const items = [
  { slug: 'vuedotjs',    name: 'Vue 3' },
  { slug: 'typescript',  name: 'TypeScript' },
  { slug: 'fastapi',     name: 'FastAPI' },
  { slug: 'python',      name: 'Python' },
  { slug: 'mongodb',     name: 'MongoDB' },
  { slug: 'qdrant',      name: 'Qdrant' },
  { slug: 'langchain',   name: 'LangChain' },
  { slug: 'tailwindcss', name: 'Tailwind v4' },
  { slug: 'openai',      name: 'OpenAI-compat SDK' },
  { slug: 'vite',        name: 'Vite' },
  { slug: 'pinia',       name: 'Pinia' },
  { slug: 'pnpm',        name: 'npm' },
]

const doubled = [...items, ...items] // marquee loop 要两倍长度无缝衔接
</script>

<template>
  <section class="py-24 border-t border-[color:var(--home-line)] bg-white/50">
    <div class="max-w-6xl mx-auto px-6 mb-10 flex items-baseline justify-between">
      <div>
        <p class="font-caps text-[color:var(--home-ink-mute)] mb-2">Built With</p>
        <h3 class="font-chinese-display text-2xl md:text-3xl">百家所长 · 择善而用</h3>
      </div>
      <span class="font-caps text-[color:var(--home-ink-mute)] hidden md:block">
        {{ items.length }} frameworks · 1 codebase
      </span>
    </div>

    <div class="marquee-mask overflow-hidden">
      <div class="marquee-track px-8 items-center">
        <div
          v-for="(it, i) in doubled"
          :key="i"
          class="flex items-center gap-3 px-4 py-3 rounded-xl bg-white/80 border border-[color:var(--home-line)] shrink-0 min-w-[160px]"
        >
          <img
            :src="`https://cdn.simpleicons.org/${it.slug}/14141a`"
            :alt="it.name"
            class="w-5 h-5 opacity-80"
            loading="lazy"
            onerror="this.style.display='none'"
          />
          <span class="text-sm font-medium text-[color:var(--home-ink)]">{{ it.name }}</span>
        </div>
      </div>
    </div>
  </section>
</template>
