/**
 * /home 独立部署专用 Vite 配置（形态 B）。
 *
 * 与 vite.config.ts 的差异：
 *   - entry HTML 改用 index-home.html（脚本加载 src/main.home.ts）
 *   - 输出目录 dist-home/，避免污染主站 build 产物
 *   - closeBundle 钩子把 dist-home/index-home.html 重命名为 index.html，
 *     让 Netlify 默认根路径就能加载
 *
 * 用法：
 *   npm run build:home
 *   netlify deploy --prod --dir=frontend/dist-home
 */
import path from 'node:path'
import fs from 'node:fs'
import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import tailwindcss from '@tailwindcss/vite'

export default defineConfig({
  plugins: [
    vue(),
    tailwindcss(),
    {
      name: 'rename-home-html',
      apply: 'build',
      closeBundle() {
        const from = path.resolve(__dirname, 'dist-home/index-home.html')
        const to = path.resolve(__dirname, 'dist-home/index.html')
        if (fs.existsSync(from)) {
          fs.renameSync(from, to)
          console.log('[rename-home-html] dist-home/index-home.html → index.html')
        }
      },
    },
  ],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
  build: {
    outDir: 'dist-home',
    emptyOutDir: true,
    rollupOptions: {
      input: path.resolve(__dirname, 'index-home.html'),
    },
  },
})
