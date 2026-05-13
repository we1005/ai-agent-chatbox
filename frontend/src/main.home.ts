/**
 * /home 独立部署入口（形态 B · 仅落地页）。
 *
 * 目的：把 HomePage 切出来打成最小独立 bundle，部署到 Netlify 等静态托管时
 * 不需要也不暴露 chat / wiki / admin 等需要后端的页面。
 *
 * 与 main.ts 的差异：
 *   - 不引入 Element Plus / Pinia / chat store / Wiki / Admin 路由
 *   - vue-router 退化成单条 catch-all 路由：任何路径都渲染 HomePage
 *     （这样 NavBar/Hero 里残留的 router.push('/wiki') 等不会跳到 404）
 *   - 仍保留 @vueuse/motion + Tailwind + home.css，HomePage 视觉 100% 等同
 */
import { createApp } from 'vue'
import { createRouter, createWebHistory } from 'vue-router'
import { MotionPlugin } from '@vueuse/motion'

import './assets/tailwind.css'
import './style/home.css'

import HomePage from './views/home/HomePage.vue'

// catch-all 路由：所有 path 都渲染 HomePage。
// 主站才有的 /wiki、/knowledge 等内部跳转点击后只会"刷一下"页面，不会 404。
const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/:pathMatch(.*)*', name: 'home', component: HomePage },
  ],
})

const app = createApp(HomePage)
app.use(router)
app.use(MotionPlugin)
app.mount('#app')
