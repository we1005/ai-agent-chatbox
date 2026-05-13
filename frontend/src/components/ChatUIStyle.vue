<!--
  ChatUIStyle —— 1:1 复刻 ChatGPT 桌面端布局的全页面 mock。
  路由 /chat-ui-style；与 /style-lab 的区别：
    - /style-lab 展示九节组件库（palette / typography / buttons / cards / …）
    - /chat-ui-style 展示**完整页面布局**（侧栏 + 顶栏 + 对话区 + 输入栏），
      目的是验证 ChatGPT 视觉语言套到本项目数据后的整体效果

  参考图：chatgpt界面图.jpg
  设计 token：frontend/DESIGN-chatgpt.md（全部走 --color-gpt-* 命名空间）
  实现约束（不变）：无 Element Plus 依赖、Tailwind v4 无 Preflight、scoped 样式
-->

<template>
  <div class="h-screen flex font-sans antialiased bg-gpt-canvas text-gpt-text-primary overflow-hidden">

    <!-- ━━━━━━━━━━━━━━━━━━━ 左侧栏 ━━━━━━━━━━━━━━━━━━━ -->
    <aside class="w-[260px] shrink-0 h-full flex flex-col bg-gpt-sidebar border-r border-gpt-border">
      <!-- 顶部：操作按钮（mac 窗口红绿灯对齐位置预留） -->
      <div class="flex items-center gap-1 px-3 py-3">
        <button class="p-2 rounded-lg hover:bg-gpt-hover transition text-gpt-text-secondary" title="折叠侧栏">
          <svg class="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="3" width="18" height="18" rx="2"/><path d="M9 3v18"/></svg>
        </button>
        <button class="p-2 rounded-lg hover:bg-gpt-hover transition text-gpt-text-secondary ml-auto" title="New chat">
          <svg class="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 20h9M16.5 3.5a2.121 2.121 0 013 3L7 19l-4 1 1-4L16.5 3.5z"/></svg>
        </button>
      </div>

      <!-- 搜索框 -->
      <div class="px-3 pb-2">
        <div class="flex items-center gap-2 px-3 py-2 rounded-lg bg-gpt-canvas border border-gpt-border">
          <svg class="w-4 h-4 text-gpt-text-tertiary shrink-0" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="11" cy="11" r="8"/><path d="M21 21l-4.35-4.35"/></svg>
          <input type="text" placeholder="Search" class="flex-1 bg-transparent outline-none text-[14px] text-gpt-text-primary placeholder-gpt-text-tertiary" />
        </div>
      </div>

      <!-- 主导航：ChatGPT / GPTs -->
      <nav class="px-3 pt-1 pb-3 space-y-0.5">
        <NavItem active>
          <template #icon>
            <div class="w-6 h-6 rounded-full bg-gpt-text-primary flex items-center justify-center">
              <svg class="w-3 h-3 text-white" viewBox="0 0 24 24" fill="currentColor"><path d="M12 0a12 12 0 100 24 12 12 0 000-24zm0 4.5a7.5 7.5 0 110 15 7.5 7.5 0 010-15z"/></svg>
            </div>
          </template>
          Knowledge Base
        </NavItem>
        <NavItem>
          <template #icon>
            <svg class="w-5 h-5 text-gpt-text-secondary" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><path d="M21 16V8a2 2 0 00-1-1.73l-7-4a2 2 0 00-2 0l-7 4A2 2 0 003 8v8a2 2 0 001 1.73l7 4a2 2 0 002 0l7-4A2 2 0 0021 16z"/><path d="M3.27 6.96L12 12.01l8.73-5.05M12 22.08V12"/></svg>
          </template>
          GPTs
        </NavItem>
      </nav>

      <!-- Projects -->
      <div class="px-3 pb-2">
        <div class="px-3 py-1.5 text-[12px] font-medium text-gpt-text-tertiary">Projects</div>
        <div class="space-y-0.5">
          <NavItem>
            <template #icon>
              <svg class="w-4 h-4 text-gpt-text-secondary" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><path d="M3 7a2 2 0 012-2h4l2 2h8a2 2 0 012 2v9a2 2 0 01-2 2H5a2 2 0 01-2-2V7z"/></svg>
            </template>
            New project
          </NavItem>
          <NavItem>
            <template #icon>
              <svg class="w-4 h-4 text-gpt-text-secondary" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><path d="M22 10v6M2 10l10-5 10 5-10 5z"/><path d="M6 12v5c3 3 9 3 12 0v-5"/></svg>
            </template>
            本项目 AI 学习
          </NavItem>
        </div>
      </div>

      <!-- Recents（可滚动） -->
      <div class="flex-1 min-h-0 overflow-y-auto px-3 pb-2">
        <div class="px-3 py-1.5 text-[12px] font-medium text-gpt-text-tertiary">Recents</div>
        <div class="space-y-0.5">
          <ConvItem active>Mac 上运行 Embedding 模型</ConvItem>
          <ConvItem>BGE-M3 sparse 编码原理</ConvItem>
          <ConvItem>政治学相关的书有哪些？</ConvItem>
          <ConvItem>LangGraph StateGraph 配置</ConvItem>
          <ConvItem>Solo 模式和 classic 区别</ConvItem>
          <ConvItem>beanie 2.x 抛弃 motor 怎么办</ConvItem>
          <ConvItem>Qdrant hybrid 参数调优</ConvItem>
          <ConvItem>mongod 8.2 vs 8.0 FCV</ConvItem>
          <ConvItem>DeepSeek 思考模式集成</ConvItem>
          <ConvItem>LangSmith 可观测性方案</ConvItem>
          <ConvItem>Multi-Query 和 Rewrite 互斥</ConvItem>
          <ConvItem>今天北京天气</ConvItem>
        </div>
      </div>

      <!-- 底部：用户 -->
      <div class="border-t border-gpt-border p-3">
        <button class="w-full flex items-center gap-3 px-2 py-1.5 rounded-lg hover:bg-gpt-hover transition-colors">
          <div class="w-8 h-8 rounded-full bg-gradient-to-br from-violet-400 to-fuchsia-500 flex items-center justify-center text-white text-[12px] font-semibold shrink-0">LM</div>
          <span class="text-[14px] font-medium text-gpt-text-primary">li mark</span>
        </button>
      </div>
    </aside>

    <!-- ━━━━━━━━━━━━━━━━━━━ 主区域 ━━━━━━━━━━━━━━━━━━━ -->
    <main class="flex-1 h-full flex flex-col min-w-0 bg-gpt-canvas">

      <!-- 顶栏 -->
      <header class="flex items-center justify-between px-4 py-3 shrink-0">
        <!-- 左：模型选择器 -->
        <button class="flex items-center gap-1 px-3 py-1.5 rounded-lg hover:bg-gpt-hover transition-colors">
          <span class="text-[18px] font-semibold text-gpt-text-primary">Knowledge Base</span>
          <span class="text-[18px] font-normal text-gpt-text-tertiary ml-1">Auto</span>
          <svg class="w-4 h-4 text-gpt-text-tertiary ml-0.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="6 9 12 15 18 9"/></svg>
        </button>
        <!-- 右：分享 + 菜单 -->
        <div class="flex items-center gap-1">
          <button class="p-2 rounded-lg hover:bg-gpt-hover transition-colors text-gpt-text-secondary" title="Share">
            <svg class="w-5 h-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><path d="M4 12v7a2 2 0 002 2h12a2 2 0 002-2v-7M16 6l-4-4-4 4M12 2v13"/></svg>
          </button>
          <button class="p-2 rounded-lg hover:bg-gpt-hover transition-colors text-gpt-text-secondary" title="More">
            <svg class="w-5 h-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><rect x="4" y="10" width="16" height="4" rx="1"/></svg>
          </button>
        </div>
      </header>

      <!-- 对话区（可滚动） -->
      <div class="flex-1 overflow-y-auto">
        <div class="max-w-[780px] mx-auto px-8 py-4 space-y-8">

          <!-- 用户消息：小气泡右对齐 -->
          <div class="flex justify-end">
            <div class="max-w-[75%] px-4 py-2.5 rounded-[18px] bg-gpt-user-bubble text-[16px] leading-[1.75] text-gpt-text-primary">
              在 Mac 上尽快把本地 embedding 跑起来有什么推荐方案？
            </div>
          </div>

          <!-- AI 消息：无气泡直排 -->
          <article class="text-[16px] leading-[1.75] text-gpt-text-primary space-y-4">
            <p>下面几条按你 Mac 上尽快本地跑起来排：</p>

            <ul class="space-y-2 pl-6 list-disc marker:text-gpt-text-tertiary">
              <li><strong class="font-semibold">最省事</strong>：Ollama</li>
              <li><strong class="font-semibold">最适合自己写代码</strong>：Sentence Transformers</li>
              <li><strong class="font-semibold">最适合 GGUF / 本地量化生态</strong>：llama.cpp</li>
            </ul>

            <p>你可以直接照这个最短路径走：</p>

            <!-- 代码块（内联 <pre>，确保换行被保留） -->
            <div class="rounded-xl overflow-hidden border border-gpt-border bg-[#F9F9F9]">
              <div class="flex items-center justify-between px-4 py-2 border-b border-gpt-border">
                <span class="text-[13px] font-medium text-gpt-text-primary">Bash</span>
                <button class="flex items-center gap-1 text-[13px] text-gpt-text-secondary hover:text-gpt-text-primary transition-colors">
                  <svg class="w-3.5 h-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><rect x="9" y="9" width="13" height="13" rx="2"/><path d="M5 15H4a2 2 0 01-2-2V4a2 2 0 012-2h9a2 2 0 012 2v1"/></svg>
                  Copy
                </button>
              </div>
<pre class="px-4 py-3 text-[14px] leading-[1.6] font-mono overflow-x-auto text-gpt-text-primary">brew install --cask ollama
ollama pull nomic-embed-text
ollama serve</pre>
            </div>

            <p>然后调用：</p>

            <div class="rounded-xl overflow-hidden border border-gpt-border bg-[#F9F9F9]">
              <div class="flex items-center justify-between px-4 py-2 border-b border-gpt-border">
                <span class="text-[13px] font-medium text-gpt-text-primary">Bash</span>
                <button class="flex items-center gap-1 text-[13px] text-gpt-text-secondary hover:text-gpt-text-primary transition-colors">
                  <svg class="w-3.5 h-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><rect x="9" y="9" width="13" height="13" rx="2"/><path d="M5 15H4a2 2 0 01-2-2V4a2 2 0 012-2h9a2 2 0 012 2v1"/></svg>
                  Copy
                </button>
              </div>
<pre class="px-4 py-3 text-[14px] leading-[1.6] font-mono overflow-x-auto text-gpt-text-primary">curl http://localhost:11434/api/embeddings -d '{
  "model": "nomic-embed-text",
  "prompt": "这是一个测试句子"
}'</pre>
            </div>

            <p>如果你愿意，我下一条可以直接给你一份"<strong class="font-semibold">mac 本地 embedding + Chroma/FAISS 搭知识库</strong>"的完整可运行脚本。</p>

            <!-- 消息尾部动作 -->
            <div class="flex items-center gap-1 pt-2 text-gpt-text-tertiary">
              <MsgAction title="Copy">
                <svg class="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><rect x="9" y="9" width="13" height="13" rx="2"/><path d="M5 15H4a2 2 0 01-2-2V4a2 2 0 012-2h9a2 2 0 012 2v1"/></svg>
              </MsgAction>
              <MsgAction title="Read aloud">
                <svg class="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><polygon points="11 5 6 9 2 9 2 15 6 15 11 19 11 5"/><path d="M15.54 8.46a5 5 0 010 7.07M19.07 4.93a10 10 0 010 14.14"/></svg>
              </MsgAction>
              <MsgAction title="Good response">
                <svg class="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><path d="M7 11V21H4a1 1 0 01-1-1v-8a1 1 0 011-1h3zM7 11l4-7a2 2 0 013 1v4h4a2 2 0 012 2l-2 7a2 2 0 01-2 1H7"/></svg>
              </MsgAction>
              <MsgAction title="Bad response">
                <svg class="w-4 h-4 rotate-180" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><path d="M7 11V21H4a1 1 0 01-1-1v-8a1 1 0 011-1h3zM7 11l4-7a2 2 0 013 1v4h4a2 2 0 012 2l-2 7a2 2 0 01-2 1H7"/></svg>
              </MsgAction>
              <MsgAction title="More">
                <svg class="w-4 h-4" viewBox="0 0 24 24" fill="currentColor"><circle cx="5" cy="12" r="1.5"/><circle cx="12" cy="12" r="1.5"/><circle cx="19" cy="12" r="1.5"/></svg>
              </MsgAction>
              <!-- Sources -->
              <div class="flex items-center gap-1 ml-4 text-[13px]">
                <span class="inline-flex items-center -space-x-1">
                  <span class="w-5 h-5 rounded-full bg-amber-100 border border-gpt-canvas flex items-center justify-center text-[10px]">🍎</span>
                  <span class="w-5 h-5 rounded-full bg-emerald-100 border border-gpt-canvas flex items-center justify-center text-[10px]">🐙</span>
                  <span class="w-5 h-5 rounded-full bg-sky-100 border border-gpt-canvas flex items-center justify-center text-[10px]">📄</span>
                </span>
                <span class="ml-1">Sources</span>
              </div>
            </div>
          </article>

        </div>
      </div>

      <!-- 底部输入栏 -->
      <div class="shrink-0 px-4 pb-6 pt-2 bg-gpt-canvas">
        <div class="max-w-[780px] mx-auto">
          <div class="flex items-center gap-1 px-2 py-2 rounded-[26px] bg-gpt-canvas border border-gpt-border shadow-[0_2px_8px_rgba(0,0,0,0.04)] focus-within:border-gpt-text-primary transition-colors">
            <!-- 左侧：+ 🌐 ✏️ A Auto -->
            <IconSlot title="Attach">
              <svg class="w-5 h-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><path d="M12 5v14M5 12h14"/></svg>
            </IconSlot>
            <IconSlot title="Web search">
              <svg class="w-5 h-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><circle cx="12" cy="12" r="10"/><path d="M2 12h20M12 2a15.3 15.3 0 014 10 15.3 15.3 0 01-4 10 15.3 15.3 0 01-4-10 15.3 15.3 0 014-10z"/></svg>
            </IconSlot>
            <IconSlot title="Canvas">
              <svg class="w-5 h-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><path d="M11 4H4a2 2 0 00-2 2v14a2 2 0 002 2h14a2 2 0 002-2v-7"/><path d="M18.5 2.5a2.121 2.121 0 013 3L12 15l-4 1 1-4 9.5-9.5z"/></svg>
            </IconSlot>
            <IconSlot title="Format">
              <svg class="w-5 h-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><path d="M4 7V4h16v3M9 20h6M12 4v16"/></svg>
            </IconSlot>
            <button class="flex items-center gap-1 px-2 py-1 rounded-lg hover:bg-gpt-hover text-[14px] text-gpt-text-primary transition-colors">
              Auto
              <svg class="w-3.5 h-3.5 text-gpt-text-tertiary" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="6 9 12 15 18 9"/></svg>
            </button>

            <!-- 中间输入 -->
            <input
              type="text"
              placeholder="Ask anything"
              class="flex-1 bg-transparent outline-none text-[16px] text-gpt-text-primary placeholder-gpt-text-tertiary px-2 py-1"
            />

            <!-- 右侧：声音 + 实心圆按钮 -->
            <IconSlot title="Waveform">
              <svg class="w-5 h-5" viewBox="0 0 24 24" fill="currentColor"><circle cx="12" cy="12" r="6" fill="none" stroke="currentColor" stroke-width="1.8"/></svg>
            </IconSlot>
            <IconSlot title="Voice">
              <svg class="w-5 h-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><path d="M12 1a3 3 0 00-3 3v8a3 3 0 006 0V4a3 3 0 00-3-3z"/><path d="M19 10v2a7 7 0 01-14 0v-2M12 19v4M8 23h8"/></svg>
            </IconSlot>
          </div>
          <div class="mt-2 text-center text-[12px] text-gpt-text-tertiary">
            本页仅为 UI 样式预览（路由 <span class="font-mono">/chat-ui-style</span>），与主项目对话功能独立。
          </div>
        </div>
      </div>

    </main>
  </div>
</template>

<script setup lang="ts">
import { h } from 'vue'

// ── 小组件 ──

// 主侧栏导航项（ChatGPT / GPTs / New project）
const NavItem = (props: { active?: boolean }, { slots, attrs }: any) =>
  h('button', {
    ...attrs,
    class: [
      'w-full flex items-center gap-2.5 px-3 py-2 rounded-lg text-[14px] transition-colors',
      props.active
        ? 'bg-gpt-hover text-gpt-text-primary font-medium'
        : 'text-gpt-text-primary hover:bg-gpt-hover',
      attrs.class,
    ],
  }, [
    slots.icon ? h('span', { class: 'shrink-0' }, slots.icon()) : null,
    h('span', { class: 'flex-1 text-left truncate' }, slots.default?.()),
  ])

// 会话列表项（Recents）
const ConvItem = (props: { active?: boolean }, { slots, attrs }: any) =>
  h('button', {
    ...attrs,
    class: [
      'w-full text-left px-3 py-2 rounded-lg text-[14px] truncate transition-colors',
      props.active
        ? 'bg-gpt-hover text-gpt-text-primary font-medium'
        : 'text-gpt-text-primary hover:bg-gpt-hover',
      attrs.class,
    ],
  }, slots.default?.())

// 消息尾部动作图标
const MsgAction = (_p: any, { slots, attrs }: any) =>
  h('button', {
    ...attrs,
    class: [
      'p-1.5 rounded-md hover:bg-gpt-hover hover:text-gpt-text-primary transition-colors',
      attrs.class,
    ],
  }, slots.default?.())

// 输入栏图标插槽
const IconSlot = (_p: any, { slots, attrs }: any) =>
  h('button', {
    ...attrs,
    class: [
      'p-2 rounded-full hover:bg-gpt-hover text-gpt-text-secondary hover:text-gpt-text-primary transition-colors',
      attrs.class,
    ],
  }, slots.default?.())

// 代码块已内联到 <template>（使用真实 <pre> 标签保留换行，不再走 functional component）
</script>

<style scoped>
/* 为什么加这段：项目的 Tailwind 配置刻意跳过了 Preflight（避免污染 Element Plus），
   但这意味着本页面所有 <button> 保留浏览器默认样式（灰底 + 凸起边）。
   这里在 scoped 作用域内复位，只影响本组件。 */
button {
  background: transparent;
  border: 0;
  padding: 0;
  margin: 0;
  cursor: pointer;
  font: inherit;
  color: inherit;
  text-align: inherit;
}

/* 同理，input/select 的默认表现也做一次局部复位 */
input,
select,
textarea {
  background: transparent;
  border: 0;
  padding: 0;
  margin: 0;
  font: inherit;
  color: inherit;
}

/* 输入栏 shadow 标记（Tailwind v4 arbitrary value 的转义类） */
.shadow-\[0_2px_8px_rgba\(0\,0\,0\,0\.04\)\] {
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.04);
}
</style>
