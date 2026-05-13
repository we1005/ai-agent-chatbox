<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import { Github, MessagesSquare, Compass } from 'lucide-vue-next'
import { brand } from '../brand'

const router = useRouter()
const scrolled = ref(false)

function onScroll() {
  scrolled.value = window.scrollY > 24
}
onMounted(() => {
  window.addEventListener('scroll', onScroll, { passive: true })
  onScroll()
})
onUnmounted(() => window.removeEventListener('scroll', onScroll))
</script>

<template>
  <nav
    class="glass-navbar fixed top-0 left-0 right-0 z-50 transition-all"
    :class="scrolled ? 'py-3' : 'py-5'"
  >
    <div class="max-w-6xl mx-auto px-6 flex items-center justify-between">
      <!-- Wordmark -->
      <button
        class="flex items-baseline gap-2 group"
        @click="router.push('/home')"
      >
        <span class="font-chinese-display text-xl tracking-widest group-hover:text-[color:var(--home-accent)] transition-colors">
          {{ brand.chinese }}
        </span>
        <span class="font-caps text-[color:var(--home-ink-mute)]">
          {{ brand.english }}
        </span>
      </button>

      <!-- Right actions -->
      <div class="flex items-center gap-1">
        <button
          class="px-3 py-2 rounded-full font-caps text-[color:var(--home-ink-soft)] hover:bg-white/60 flex items-center gap-1.5 transition-colors"
          @click="router.push('/wiki')"
        >
          <Compass class="w-3.5 h-3.5" />
          Wiki
        </button>
        <a
          :href="brand.github"
          target="_blank"
          rel="noopener"
          class="px-3 py-2 rounded-full font-caps text-[color:var(--home-ink-soft)] hover:bg-white/60 flex items-center gap-1.5 transition-colors"
        >
          <Github class="w-3.5 h-3.5" />
          GitHub
        </a>
        <button
          class="ml-1 px-4 py-2 rounded-full bg-[color:var(--home-ink)] text-white text-sm font-medium hover:bg-[color:var(--home-accent)] transition-colors flex items-center gap-1.5"
          @click="router.push('/')"
        >
          <MessagesSquare class="w-4 h-4" />
          进入对话
        </button>
      </div>
    </div>
  </nav>
</template>
