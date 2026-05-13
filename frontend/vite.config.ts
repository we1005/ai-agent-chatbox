import path from 'node:path'
import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import tailwindcss from '@tailwindcss/vite'

// https://vite.dev/config/
export default defineConfig({
  plugins: [
    vue(),
    // Tailwind v4 Vite 插件：自动扫描 .vue/.ts 里的 class 按需生成 CSS。
    // 注：本项目 src/assets/tailwind.css **不导入 Preflight**，避免把
    // Element Plus 依赖的浏览器默认样式 reset 掉（Preflight 会清零所有
    // h1/h2/button/ul/a 等元素的默认样式）。shadcn-vue 组件靠 utility class
    // 显式定义尺寸/颜色/边框，不依赖 Preflight 清零就能工作。见 tailwind.css 注释。
    tailwindcss(),
  ],
  resolve: {
    alias: {
      // shadcn-vue 的约定：@/components/ui/* + @/lib/utils
      '@': path.resolve(__dirname, './src'),
    },
  },
})
