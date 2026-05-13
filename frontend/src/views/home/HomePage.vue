<script setup lang="ts">
import { onMounted, onUnmounted } from 'vue'
import NavBar from './sections/NavBar.vue'
import Hero from './sections/Hero.vue'
import Philosophy from './sections/Philosophy.vue'
import Features from './sections/Features.vue'
import Stats from './sections/Stats.vue'
import ArchPreview from './sections/ArchPreview.vue'
import TechStack from './sections/TechStack.vue'
import Footer from './sections/Footer.vue'
import { brand } from './brand'

// 进入 /home 时把 tab title 改成品牌名（离开时留给其他页自己改）
const prevTitle = document.title
onMounted(() => {
  document.title = `${brand.chinese} · ${brand.english} — ${brand.englishSub}`
  window.scrollTo({ top: 0 })
})
onUnmounted(() => {
  document.title = prevTitle
})
</script>

<template>
  <div class="home-root">
    <NavBar />
    <main>
      <Hero />
      <Philosophy />
      <Features />
      <Stats />
      <ArchPreview />
      <TechStack />
    </main>
    <Footer />
  </div>
</template>
