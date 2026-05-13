<template>
  <!--
    2026-04 · 外框从 el-container/aside/header 迁到 shadcn-vue 风格的 Tailwind flex 布局。
    子组件（Sidebar / ChatArea / InputBox）保持 Element Plus 原样不动，ConfigPanel 用新的
    shadcn-vue 版本。CSS vars（--bg-primary / --bg-secondary / --border-color / --radius-sm）
    来自 global :root 定义，保持既有视觉 token 不破坏。
  -->
  <!-- TooltipProvider 包一层，给 ConfigPanel 里的 Tooltip 用；delay=150ms -->
  <TooltipProvider :delay-duration="150">
    <div class="chat-layout-root flex h-screen bg-[var(--bg-primary)]" style="font-family: 'Noto Serif SC', serif;">
      <!-- Sidebar · 固定 260px -->
      <aside class="w-[260px] shrink-0 h-full overflow-hidden">
        <Sidebar />
      </aside>

      <!-- 主区 · flex 竖排 -->
      <div class="flex flex-col flex-1 h-full min-w-0">
        <!-- Header · 精简后只剩标题 + Manage Files；三个核心控件迁到 InputBox 工具栏 -->
        <header
          class="h-[72px] shrink-0 flex items-center justify-between px-8 bg-[var(--bg-secondary)] border-b border-[var(--border-color)] z-10"
        >
          <h3
            class="m-0 font-bold text-[2rem] text-[var(--text-primary)] tracking-tight"
            style="font-family: 'LXGW WenKai Screen', 'Inter', sans-serif;"
          >
            📖知识库问答
          </h3>
          <Button variant="outline" @click="$router.push('/knowledge')">
            <Files class="h-4 w-4" />
            Manage Files
          </Button>
        </header>

        <!-- 消息区 · 占据剩余高度 -->
        <main class="flex-1 min-h-0 flex flex-col bg-[var(--bg-primary)] overflow-hidden">
          <ChatArea />
        </main>

        <!-- Footer · 高度自适应 -->
        <footer class="shrink-0 bg-[var(--bg-primary)]">
          <InputBox />
        </footer>
      </div>
    </div>
  </TooltipProvider>
</template>

<script setup lang="ts">
import Sidebar from './Sidebar.vue'
import ChatArea from './ChatArea.vue'
import InputBox from './InputBox.vue'
import { TooltipProvider } from '@/components/ui/tooltip'
import { Button } from '@/components/ui/button'
import { Files } from '@element-plus/icons-vue'
</script>
