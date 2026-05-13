<!--
  StyleLab —— 隔离的前端样式实验页（路由 /style-lab）。

  当前风格：ChatGPT（见 frontend/DESIGN-chatgpt.md）
  之前版本：Linear（见 frontend/DESIGN.md；git 历史里有前一版 Vue 文件）
  两套 token 都保留在 src/assets/tailwind.css 里，通过前缀区分：
    - linear-*  Linear 深色高密度
    - gpt-*     ChatGPT 浅色内容优先

  实现约束（不变）：
    - 不使用任何 Element Plus 组件
    - Tailwind v4，跳过 Preflight
    - 全部样式走 tailwind.css 里 @theme 定义的 token
-->

<template>
  <div class="min-h-screen font-sans antialiased bg-gpt-canvas text-gpt-text-primary">
    <!-- 顶栏：ChatGPT 风格——细边 + 超轻 chrome -->
    <nav class="sticky top-0 z-10 flex items-center justify-between px-6 py-3 bg-gpt-canvas border-b border-gpt-border">
      <div class="flex items-center gap-3">
        <div class="w-7 h-7 rounded-full bg-gpt-text-primary flex items-center justify-center text-white text-[12px] font-semibold">
          AI
        </div>
        <h1 class="text-[14px] font-medium text-gpt-text-primary">Style Lab</h1>
        <span class="text-[13px] text-gpt-text-tertiary">ChatGPT design system preview · frontend/DESIGN-chatgpt.md</span>
      </div>
      <router-link to="/" class="text-[13px] text-gpt-text-secondary hover:text-gpt-text-primary transition-colors">
        ← 回到主界面
      </router-link>
    </nav>

    <div class="max-w-[1200px] mx-auto px-8 py-12 space-y-20">

      <!-- 1. Empty State (ChatGPT 的灵魂场景) -->
      <section>
        <SectionLabel>1 · Empty State · 对话入口</SectionLabel>
        <div class="mt-6 px-8 py-20 rounded-2xl bg-gpt-canvas border border-gpt-border">
          <div class="max-w-[720px] mx-auto text-center">
            <div class="w-14 h-14 mx-auto rounded-full bg-gpt-hover flex items-center justify-center mb-6">
              <svg class="w-7 h-7 text-gpt-text-primary" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 15a2 2 0 01-2 2H7l-4 4V5a2 2 0 012-2h14a2 2 0 012 2z"/></svg>
            </div>
            <h2 class="text-[30px] font-semibold text-gpt-text-primary mb-3 tracking-[-0.01em]">
              How can I help you today?
            </h2>
            <p class="text-[14px] text-gpt-text-secondary mb-12">
              提问、总结文档、写代码 —— 你的私人 AI 助理
            </p>
            <!-- 4 条建议卡片 -->
            <div class="grid grid-cols-2 gap-3 text-left">
              <SuggestionCard title="列出所有政治学相关的书" hint="Document catalog query" />
              <SuggestionCard title="总结政治学导论第三章" hint="Summarization" />
              <SuggestionCard title="解释 BGE-M3 的 sparse 编码" hint="Technical question" />
              <SuggestionCard title="对比 Solo 模式和 classic 路径" hint="Comparison" />
            </div>
          </div>
        </div>
      </section>

      <!-- 2. Color Palette -->
      <section>
        <SectionLabel>2 · Color Palette</SectionLabel>
        <div class="mt-6 grid grid-cols-4 gap-3">
          <Swatch name="canvas" hex="#ffffff" purpose="主画布" bgClass="bg-gpt-canvas" border />
          <Swatch name="sidebar" hex="#f9f9f9" purpose="侧栏" bgClass="bg-gpt-sidebar" border />
          <Swatch name="hover" hex="#f4f4f4" purpose="hover / 用户气泡" bgClass="bg-gpt-hover" border />
          <Swatch name="text-primary" hex="#0d0d0d" purpose="主文本" bgClass="bg-gpt-text-primary" dark />
          <Swatch name="text-secondary" hex="#676767" purpose="辅助文本" bgClass="bg-gpt-text-secondary" dark />
          <Swatch name="text-tertiary" hex="#8e8ea0" purpose="元数据" bgClass="bg-gpt-text-tertiary" dark />
          <Swatch name="border" hex="#e5e5e5" purpose="边框" bgClass="bg-gpt-border" border />
          <Swatch name="teal" hex="#10a37f" purpose="Upgrade / Success" bgClass="bg-gpt-teal" dark />
        </div>
      </section>

      <!-- 3. Typography Scale -->
      <section>
        <SectionLabel>3 · Typography Scale</SectionLabel>
        <div class="mt-6 space-y-5 px-8 py-10 rounded-2xl bg-gpt-canvas border border-gpt-border">
          <Row label="Hero / 30">
            <span class="text-[30px] font-semibold text-gpt-text-primary tracking-[-0.01em]">How can I help you today?</span>
          </Row>
          <Row label="H2 / 20">
            <span class="text-[20px] font-semibold text-gpt-text-primary tracking-[-0.005em]">Section Heading · 章节标题</span>
          </Row>
          <Row label="Body / 16">
            <span class="text-[16px] leading-[1.75] text-gpt-text-primary">
              对话正文用 16px line-height 1.75，ChatGPT 最辨识的排版决定。这个行距比 Linear 的 1.5 明显宽松，目的是让长文本像书一样舒服阅读。
            </span>
          </Row>
          <Row label="Sidebar / 14">
            <span class="text-[14px] font-normal text-gpt-text-primary">Sidebar item default · 会话标题</span>
          </Row>
          <Row label="Sidebar Active / 14">
            <span class="text-[14px] font-medium text-gpt-text-primary">Sidebar item active · 选中的会话</span>
          </Row>
          <Row label="Caption / 13">
            <span class="text-[13px] text-gpt-text-secondary">Metadata · 时间戳 · 模型名</span>
          </Row>
          <Row label="Mono / 14">
            <span class="font-mono text-[14px] text-gpt-text-secondary">query_knowledge_base_catalog(topic="politics")</span>
          </Row>
        </div>
      </section>

      <!-- 4. Buttons -->
      <section>
        <SectionLabel>4 · Buttons</SectionLabel>
        <div class="mt-6 flex flex-wrap gap-3 px-8 py-10 rounded-2xl bg-gpt-canvas border border-gpt-border">
          <PrimaryButton>Primary</PrimaryButton>
          <SecondaryButton>Secondary</SecondaryButton>
          <IconGhostButton>
            <svg class="w-4 h-4" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" d="M12 4v16m8-8H4"/></svg>
          </IconGhostButton>
          <!-- Send button 单独展示：圆形黑 -->
          <button class="w-9 h-9 rounded-full bg-gpt-text-primary text-white flex items-center justify-center hover:opacity-90 transition-opacity">
            <svg class="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path stroke-linecap="round" stroke-linejoin="round" d="M5 12h14M12 5l7 7-7 7"/></svg>
          </button>
          <!-- Upgrade (仅此场合用品牌绿) -->
          <button class="px-4 py-2.5 rounded-xl text-[14px] font-medium bg-gpt-teal text-white hover:opacity-90 transition-opacity">
            Upgrade
          </button>
          <button disabled class="px-4 py-2.5 rounded-xl text-[14px] font-medium bg-gpt-hover text-gpt-text-tertiary cursor-not-allowed">
            Disabled
          </button>
        </div>
      </section>

      <!-- 5. Card -->
      <section>
        <SectionLabel>5 · Card（无阴影，仅细边）</SectionLabel>
        <div class="mt-6 grid grid-cols-2 gap-4">
          <div class="p-5 rounded-xl bg-gpt-canvas border border-gpt-border">
            <div class="flex items-center gap-2 mb-2">
              <span class="w-1.5 h-1.5 rounded-full bg-gpt-teal"></span>
              <span class="text-[12px] font-medium text-gpt-teal uppercase tracking-wide">Ready</span>
            </div>
            <h3 class="text-[16px] font-semibold text-gpt-text-primary mb-2">政治学导论.pdf</h3>
            <p class="text-[14px] leading-[1.6] text-gpt-text-secondary mb-3">系统介绍政治哲学主要流派，涵盖自由主义、保守主义、马克思主义等核心思想体系。</p>
            <div class="flex flex-wrap gap-1.5">
              <Tag>政治学</Tag>
              <Tag>哲学</Tag>
              <Tag>马克思主义</Tag>
              <Tag>+5</Tag>
            </div>
          </div>
          <div class="p-5 rounded-xl bg-gpt-canvas border border-gpt-border">
            <div class="flex items-center gap-2 mb-2">
              <span class="w-1.5 h-1.5 rounded-full bg-gpt-text-tertiary animate-pulse"></span>
              <span class="text-[12px] font-medium text-gpt-text-tertiary uppercase tracking-wide">Processing</span>
            </div>
            <h3 class="text-[16px] font-semibold text-gpt-text-primary mb-2">深度学习方法.docx</h3>
            <p class="text-[14px] leading-[1.6] text-gpt-text-secondary mb-3">处理中 · 23 / 86 chunks · 使用 BGE-M3 生成 dense + sparse 双通道向量。</p>
            <div class="h-1 bg-gpt-hover rounded-full overflow-hidden">
              <div class="h-full w-[27%] bg-gpt-text-primary rounded-full"></div>
            </div>
          </div>
        </div>
      </section>

      <!-- 6. Input Box (ChatGPT 的签名特征) -->
      <section>
        <SectionLabel>6 · Input Box · ChatGPT 签名组件</SectionLabel>
        <div class="mt-6 px-8 py-10 rounded-2xl bg-gpt-canvas border border-gpt-border space-y-4">
          <!-- ChatGPT 风格的大圆角输入框 -->
          <div class="flex items-center gap-2 px-4 py-2 rounded-3xl bg-gpt-canvas border border-gpt-border focus-within:border-gpt-text-primary transition-colors">
            <button class="p-2 text-gpt-text-secondary hover:text-gpt-text-primary hover:bg-gpt-hover rounded-lg transition">
              <svg class="w-5 h-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 12a9 9 0 01-9 9m0 0a9 9 0 01-9-9m9 9v-9m0 0l3.5 3.5M12 12l-3.5 3.5"/></svg>
            </button>
            <input
              type="text"
              placeholder="Message AI…"
              class="flex-1 bg-transparent outline-none text-[16px] text-gpt-text-primary placeholder-gpt-text-tertiary py-2"
            />
            <button class="w-9 h-9 rounded-full bg-gpt-text-primary text-white flex items-center justify-center hover:opacity-90 transition-opacity shrink-0">
              <svg class="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path stroke-linecap="round" stroke-linejoin="round" d="M12 19V5M5 12l7-7 7 7"/></svg>
            </button>
          </div>

          <!-- 普通表单元素 -->
          <div class="grid grid-cols-2 gap-3">
            <div>
              <label class="block text-[13px] font-medium text-gpt-text-primary mb-1.5">Model</label>
              <select class="w-full px-3 py-2 rounded-lg bg-gpt-canvas border border-gpt-border text-[14px] text-gpt-text-primary focus:outline-none focus:border-gpt-text-primary transition-colors">
                <option>Kimi K2 0905 Preview</option>
                <option>DeepSeek Chat</option>
                <option>Doubao Code</option>
              </select>
            </div>
            <div>
              <label class="block text-[13px] font-medium text-gpt-text-primary mb-1.5">Search mode</label>
              <select class="w-full px-3 py-2 rounded-lg bg-gpt-canvas border border-gpt-border text-[14px] text-gpt-text-primary focus:outline-none focus:border-gpt-text-primary transition-colors">
                <option>Hybrid (dense + sparse RRF)</option>
                <option>Dense only</option>
              </select>
            </div>
          </div>
        </div>
      </section>

      <!-- 7. Tags -->
      <section>
        <SectionLabel>7 · Tags / 状态</SectionLabel>
        <div class="mt-6 flex flex-wrap gap-2 px-8 py-10 rounded-2xl bg-gpt-canvas border border-gpt-border">
          <Tag>default</Tag>
          <StatusTag variant="success">Ready</StatusTag>
          <StatusTag variant="info">Processing</StatusTag>
          <StatusTag variant="warning">Pending</StatusTag>
          <StatusTag variant="danger">Failed</StatusTag>
          <Tag>.pdf</Tag>
          <Tag>.md</Tag>
          <Tag>.docx</Tag>
        </div>
      </section>

      <!-- 8. Chat Message Bubble（对标当前 ChatArea.vue） -->
      <section>
        <SectionLabel>8 · Chat Conversation · 消息流</SectionLabel>
        <div class="mt-6 px-6 py-10 rounded-2xl bg-gpt-canvas border border-gpt-border">
          <div class="max-w-[720px] mx-auto space-y-8">
            <!-- 用户消息：有气泡，右对齐 -->
            <div class="flex justify-end">
              <div class="max-w-[70%] px-4 py-2.5 rounded-[18px] bg-gpt-user-bubble text-[16px] leading-[1.75] text-gpt-text-primary">
                我知识库里和政治学相关的书有哪些？
              </div>
            </div>

            <!-- AI 消息：无气泡，直接排文字 -->
            <div class="flex gap-4">
              <div class="w-8 h-8 rounded-full bg-gpt-hover flex items-center justify-center text-[12px] font-semibold text-gpt-text-primary shrink-0">AI</div>
              <div class="flex-1 min-w-0">
                <div class="text-[16px] leading-[1.75] text-gpt-text-primary">
                  知识库里有 <strong class="font-semibold">1 份</strong>与政治学相关的文档：
                  <ol class="mt-3 ml-5 list-decimal space-y-1.5">
                    <li>
                      <span class="font-medium">政治学导论.pdf</span>
                      <sup class="ml-1 px-1.5 py-0.5 rounded-md bg-gpt-hover text-gpt-text-secondary text-[11px] font-medium">1</sup>
                      —— 涵盖自由主义、保守主义、马克思主义等主要流派
                    </li>
                  </ol>
                </div>
                <!-- 消息尾部动作 -->
                <div class="mt-3 flex items-center gap-2 text-gpt-text-tertiary">
                  <button class="p-1.5 hover:bg-gpt-hover rounded-md transition-colors" title="Copy">
                    <svg class="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="9" y="9" width="13" height="13" rx="2"/><path d="M5 15H4a2 2 0 01-2-2V4a2 2 0 012-2h9a2 2 0 012 2v1"/></svg>
                  </button>
                  <button class="p-1.5 hover:bg-gpt-hover rounded-md transition-colors" title="Good response">
                    <svg class="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M7 11V21H4a1 1 0 01-1-1v-8a1 1 0 011-1h3zM7 11l4-7a2 2 0 013 1v4h4a2 2 0 012 2l-2 7a2 2 0 01-2 1H7"/></svg>
                  </button>
                  <button class="p-1.5 hover:bg-gpt-hover rounded-md transition-colors" title="Bad response">
                    <svg class="w-4 h-4 rotate-180" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M7 11V21H4a1 1 0 01-1-1v-8a1 1 0 011-1h3zM7 11l4-7a2 2 0 013 1v4h4a2 2 0 012 2l-2 7a2 2 0 01-2 1H7"/></svg>
                  </button>
                  <button class="p-1.5 hover:bg-gpt-hover rounded-md transition-colors" title="Regenerate">
                    <svg class="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M23 4v6h-6M1 20v-6h6M3.5 9a9 9 0 0114.8-3.3L23 10M1 14l4.7 4.3A9 9 0 0020.5 15"/></svg>
                  </button>
                  <span class="text-[12px] ml-2">Model: DeepSeek Chat · 2.3s</span>
                </div>
                <!-- Sources -->
                <div class="mt-3 pt-3 border-t border-gpt-border flex items-center gap-2 text-[13px] text-gpt-text-secondary">
                  <span class="text-gpt-text-tertiary">Sources:</span>
                  <a href="#" class="px-2 py-0.5 rounded-md bg-gpt-hover hover:text-gpt-text-primary transition">[1] 政治学导论.pdf</a>
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>

      <!-- 9. Sidebar -->
      <section>
        <SectionLabel>9 · Sidebar · 会话列表</SectionLabel>
        <div class="mt-6 max-w-[280px] rounded-xl bg-gpt-sidebar border border-gpt-border overflow-hidden">
          <div class="p-3">
            <button class="w-full flex items-center justify-between px-3 py-2.5 rounded-lg bg-gpt-canvas border border-gpt-border hover:bg-gpt-hover text-[14px] font-medium text-gpt-text-primary transition-colors">
              <span class="flex items-center gap-2">
                <svg class="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 5v14m-7-7h14"/></svg>
                New chat
              </span>
              <svg class="w-4 h-4 text-gpt-text-tertiary" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 20h9M16.5 3.5a2.121 2.121 0 013 3L7 19l-4 1 1-4L16.5 3.5z"/></svg>
            </button>
          </div>

          <div class="px-3 pb-2">
            <div class="text-[11px] font-medium text-gpt-text-tertiary uppercase tracking-wide px-3 py-2">Today</div>
            <SidebarItem active>政治学相关的书有哪些？</SidebarItem>
            <SidebarItem>LangGraph 怎么装？</SidebarItem>
          </div>

          <div class="px-3 pb-2">
            <div class="text-[11px] font-medium text-gpt-text-tertiary uppercase tracking-wide px-3 py-2">Yesterday</div>
            <SidebarItem>BGE-M3 sparse 编码原理</SidebarItem>
            <SidebarItem>Solo 模式和 classic 区别</SidebarItem>
            <SidebarItem>今天北京天气</SidebarItem>
          </div>

          <div class="p-3 border-t border-gpt-border">
            <button class="w-full flex items-center gap-2 px-3 py-2 rounded-lg text-[13px] text-gpt-text-secondary hover:bg-gpt-hover hover:text-gpt-text-primary transition-colors">
              <svg class="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 00.33 1.82l.06.06a2 2 0 11-2.83 2.83l-.06-.06a1.65 1.65 0 00-1.82-.33 1.65 1.65 0 00-1 1.51V21a2 2 0 11-4 0v-.09a1.65 1.65 0 00-1-1.51 1.65 1.65 0 00-1.82.33l-.06.06a2 2 0 11-2.83-2.83l.06-.06a1.65 1.65 0 00.33-1.82H3a2 2 0 110-4h.09a1.65 1.65 0 001.51-1 1.65 1.65 0 00-.33-1.82l-.06-.06a2 2 0 112.83-2.83l.06.06a1.65 1.65 0 001.82.33H9a1.65 1.65 0 001-1.51V3a2 2 0 114 0v.09a1.65 1.65 0 001 1.51 1.65 1.65 0 001.82-.33l.06-.06a2 2 0 112.83 2.83l-.06.06a1.65 1.65 0 00-.33 1.82V9a1.65 1.65 0 001.51 1H21a2 2 0 110 4h-.09a1.65 1.65 0 00-1.51 1z"/></svg>
              Settings
            </button>
          </div>
        </div>
      </section>

      <!-- 尾注 -->
      <section class="pt-10 border-t border-gpt-border text-center">
        <p class="text-[13px] text-gpt-text-tertiary">
          此页仅预览 ChatGPT design system 在本项目场景下的效果；所有样式不影响其他路由。
          <br>
          若想切换为 Linear 深色风（上一版），可从 git 历史还原上一个 StyleLab.vue 版本。
        </p>
      </section>

    </div>
  </div>
</template>

<script setup lang="ts">
import { h } from 'vue'

// ── 基础组件（仅本页使用，无 Element Plus 依赖） ──

const SectionLabel = (_p: any, { slots }: any) =>
  h('div', {
    class: 'text-[11px] font-medium uppercase tracking-[0.15em] text-gpt-text-tertiary',
  }, slots.default?.())

const Row = (props: { label: string }, { slots }: any) =>
  h('div', { class: 'flex items-baseline gap-5' }, [
    h('span', { class: 'w-[140px] shrink-0 text-[12px] font-medium text-gpt-text-tertiary uppercase tracking-wide' }, props.label),
    h('div', { class: 'flex-1' }, slots.default?.()),
  ])

// ── Buttons ──

const PrimaryButton = (_p: any, { slots, attrs }: any) =>
  h('button', {
    ...attrs,
    class: [
      'inline-flex items-center px-4 py-2.5 rounded-xl text-[14px] font-medium',
      'bg-gpt-text-primary text-white hover:opacity-90 transition-opacity',
      attrs.class,
    ],
  }, slots.default?.())

const SecondaryButton = (_p: any, { slots, attrs }: any) =>
  h('button', {
    ...attrs,
    class: [
      'inline-flex items-center px-4 py-2.5 rounded-xl text-[14px] font-medium',
      'bg-gpt-canvas text-gpt-text-primary border border-gpt-border',
      'hover:bg-gpt-hover transition-colors',
      attrs.class,
    ],
  }, slots.default?.())

const IconGhostButton = (_p: any, { slots, attrs }: any) =>
  h('button', {
    ...attrs,
    class: [
      'inline-flex items-center justify-center w-10 h-10 rounded-lg',
      'text-gpt-text-secondary hover:bg-gpt-hover hover:text-gpt-text-primary transition-colors',
      attrs.class,
    ],
  }, slots.default?.())

// ── Tags ──

const Tag = (_p: any, { slots, attrs }: any) =>
  h('span', {
    ...attrs,
    class: [
      'inline-flex items-center px-2.5 py-0.5 rounded-md text-[12px] font-medium',
      'bg-gpt-hover text-gpt-text-secondary',
      attrs.class,
    ],
  }, slots.default?.())

const StatusTag = (props: { variant?: 'success' | 'info' | 'warning' | 'danger' }, { slots, attrs }: any) => {
  const styleMap = {
    success: 'bg-gpt-teal/10 text-gpt-teal',
    info: 'bg-blue-50 text-blue-700',
    warning: 'bg-amber-50 text-amber-700',
    danger: 'bg-red-50 text-red-700',
  }
  return h('span', {
    ...attrs,
    class: [
      'inline-flex items-center gap-1 px-2.5 py-0.5 rounded-md text-[12px] font-medium',
      styleMap[props.variant || 'info'],
      attrs.class,
    ],
  }, slots.default?.())
}

// ── Suggestion Card (Empty state 专用) ──

const SuggestionCard = (props: { title: string; hint: string }) =>
  h('button', {
    class: [
      'text-left p-4 rounded-xl border border-gpt-border',
      'hover:bg-gpt-hover transition-colors',
    ],
  }, [
    h('div', { class: 'text-[14px] font-medium text-gpt-text-primary mb-1' }, props.title),
    h('div', { class: 'text-[13px] text-gpt-text-secondary' }, props.hint),
  ])

// ── Sidebar Item ──

const SidebarItem = (props: { active?: boolean }, { slots, attrs }: any) =>
  h('div', {
    ...attrs,
    class: [
      'px-3 py-2 rounded-lg text-[14px] truncate cursor-pointer transition-colors',
      props.active
        ? 'bg-gpt-hover text-gpt-text-primary font-medium'
        : 'text-gpt-text-primary hover:bg-gpt-hover',
      attrs.class,
    ],
  }, slots.default?.())

// ── Color Swatch ──

const Swatch = (props: { name: string; hex: string; purpose: string; bgClass: string; dark?: boolean; border?: boolean }) =>
  h('div', { class: 'rounded-xl overflow-hidden border border-gpt-border' }, [
    h('div', {
      class: [
        `${props.bgClass} h-20 flex items-end p-2`,
        props.border ? 'border-b border-gpt-border' : '',
      ],
    }, [
      h('span', {
        class: ['font-mono text-[11px]', props.dark ? 'text-white/90' : 'text-gpt-text-secondary'],
      }, props.hex),
    ]),
    h('div', { class: 'p-3 bg-gpt-canvas' }, [
      h('div', { class: 'text-[13px] font-medium text-gpt-text-primary' }, props.name),
      h('div', { class: 'text-[12px] text-gpt-text-secondary mt-0.5' }, props.purpose),
    ]),
  ])
</script>
