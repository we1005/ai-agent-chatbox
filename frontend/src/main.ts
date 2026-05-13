import { createApp } from 'vue'
import { createPinia } from 'pinia'
import ElementPlus from 'element-plus'
import 'element-plus/dist/index.css'
import router from './router'
import './style.css'
// Tailwind v4 utilities（无 Preflight，对现有页面零影响；仅用于 /style-lab）
import './assets/tailwind.css'
// Vue Flow 默认样式 + theme override（仅在 .vue-flow 容器内生效，不污染 Element Plus）
import './style/vue-flow.css'
// /home 专属样式（仅在 .home-root 容器内生效）
import './style/home.css'
import { MotionPlugin } from '@vueuse/motion'
import App from './App.vue'

const pinia = createPinia()
const app = createApp(App)

app.use(pinia)
app.use(router)
app.use(ElementPlus)
app.use(MotionPlugin)
app.mount('#app')
