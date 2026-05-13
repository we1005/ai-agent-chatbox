<script setup lang="ts">
import { computed, ref, markRaw } from 'vue'
import { VueFlow, MarkerType, useVueFlow } from '@vue-flow/core'
import { Background } from '@vue-flow/background'
import { MiniMap } from '@vue-flow/minimap'
import { Controls } from '@vue-flow/controls'
import { useRouter } from 'vue-router'
import { ArrowLeft, FileCode2, BookOpen, MousePointerClick } from 'lucide-vue-next'
import RoleNode from './nodes/RoleNode.vue'
import { getTheme } from './lib/role-theme'
import type { WikiPageData, WikiNode } from './types'

const props = defineProps<{ page: WikiPageData }>()

const router = useRouter()

// Vue Flow 的 NodeTypesObject 期望严格匹配 NodeProps<any> 的组件签名；
// 我们的 RoleNode 用 defineProps<{ data, selected }>() 是 SFC 标准写法，
// 两者类型上对不上但运行时完全 OK —— Vue Flow 内部只读 data/selected 两个 prop。
// 业务上没必要为了 TS 严格签名重写组件，直接 any 强转。
const nodeTypes = { role: markRaw(RoleNode) } as any

const flowNodes = computed(() =>
  props.page.nodes.map(n => ({
    id: n.id,
    type: n.type ?? 'role',
    position: n.position,
    data: n.data,
  }))
)

const flowEdges = computed(() =>
  props.page.edges.map(e => {
    // 取 source 节点的 role 决定 stroke 颜色（除非显式指定）
    const sourceNode = props.page.nodes.find(n => n.id === e.source)
    const role = e.strokeRole ?? sourceNode?.data.role ?? 'note'
    const stroke = getTheme(role).edgeStroke
    const sw = e.emphasize ? 3 : 1.8
    return {
      id: e.id,
      source: e.source,
      target: e.target,
      sourceHandle: e.sourceHandle,
      targetHandle: e.targetHandle,
      label: e.label,
      animated: e.animated ?? true,
      type: e.type ?? 'smoothstep',
      style: { stroke, strokeWidth: sw, ...(e.emphasize ? { strokeDasharray: '6 4' } : {}) },
      labelBgStyle: e.emphasize ? { fill: stroke, opacity: 0.15 } : undefined,
      labelStyle: e.emphasize ? { fill: stroke, fontWeight: 700 } : undefined,
      markerEnd: {
        type: MarkerType.ArrowClosed,
        color: stroke,
        width: e.emphasize ? 22 : 18,
        height: e.emphasize ? 22 : 18,
      },
    }
  })
)

const selectedNode = ref<WikiNode | null>(null)
function onNodeClick(evt: { node: { id: string } }) {
  const found = props.page.nodes.find(n => n.id === evt.node.id) ?? null
  selectedNode.value = found
}
function clearSelection() {
  selectedNode.value = null
}

const minimapColor = (n: { data?: any }) => getTheme(n.data?.role).edgeStroke

// Vue Flow 默认 fit-view-on-init 会缩到"整图塞满"，节点多时全挤成小豆子。
// 这里改成：首次定位到左上角，zoom 固定 0.8，保证节点文字永远可读；
// 超出视口的部分让用户用平移 / minimap / 滚轮自行探索。
const { onNodesInitialized, setViewport } = useVueFlow()
onNodesInitialized(() => {
  // 留出左侧 40px 让第一个节点有呼吸感，顶部 30px 给 loop 回边空间
  setViewport({ x: 40, y: 30, zoom: 0.8 })
})
</script>

<template>
  <div class="wiki-page flex flex-col h-screen bg-gradient-to-br from-zinc-50 to-white">
    <!-- 顶部 -->
    <header class="border-b border-zinc-200 bg-white/80 backdrop-blur px-6 py-3 flex items-center gap-4">
      <button
        class="inline-flex items-center gap-1.5 text-sm text-zinc-600 hover:text-zinc-900 transition"
        @click="router.push('/wiki')"
      >
        <ArrowLeft class="w-4 h-4" />
        Wiki 首页
      </button>
      <div class="flex-1 min-w-0">
        <h1 class="text-lg font-bold text-zinc-900 truncate">{{ page.title }}</h1>
        <p class="text-xs text-zinc-500 truncate">{{ page.caption }}</p>
      </div>
      <div class="hidden md:flex items-center gap-1.5 text-xs text-zinc-400">
        <MousePointerClick class="w-3.5 h-3.5" />
        点击节点查看详情 · 拖动节点重排
      </div>
    </header>

    <!-- 主体 -->
    <div class="flex-1 flex min-h-0">
      <!-- 左侧 70% 画布 -->
      <div class="flex-1 min-w-0 relative">
        <VueFlow
          :nodes="flowNodes"
          :edges="flowEdges"
          :node-types="nodeTypes"
          :default-viewport="{ x: 0, y: 0, zoom: 1 }"
          :min-zoom="0.3"
          :max-zoom="2"
          :fit-view-on-init="false"
          :nodes-draggable="true"
          :elements-selectable="true"
          :select-nodes-on-drag="false"
          @node-click="onNodeClick"
          @pane-click="clearSelection"
        >
          <Background pattern-color="#e4e4e7" :gap="20" />
          <MiniMap pannable zoomable :node-color="minimapColor as any" />
          <Controls />
        </VueFlow>
      </div>

      <!-- 右侧 30% 详情侧栏 -->
      <aside class="w-[360px] shrink-0 border-l border-zinc-200 bg-white overflow-y-auto">
        <div v-if="!selectedNode" class="p-5 space-y-4">
          <h2 class="text-sm font-semibold text-zinc-700 uppercase tracking-wider">页面总览</h2>
          <p class="text-sm text-zinc-600 leading-relaxed whitespace-pre-line">
            {{ page.intro || page.caption }}
          </p>
          <div class="rounded-lg bg-zinc-50 border border-zinc-200 p-3 text-xs text-zinc-500">
            点击图中任意节点查看其角色、说明、关联代码与设计文档。
          </div>
          <div>
            <h3 class="text-xs font-semibold text-zinc-500 uppercase mb-2">节点角色图例</h3>
            <div class="grid grid-cols-2 gap-1.5 text-xs">
              <div v-for="r in legend" :key="r.role" class="flex items-center gap-1.5">
                <span class="inline-block w-3 h-3 rounded" :class="getTheme(r.role).bg"></span>
                <span class="text-zinc-700">{{ r.label }}</span>
              </div>
            </div>
          </div>
        </div>

        <div v-else class="p-5 space-y-4">
          <button
            class="text-xs text-zinc-400 hover:text-zinc-700 transition"
            @click="clearSelection"
          >← 返回总览</button>

          <div class="flex items-center gap-2">
            <span
              class="inline-flex items-center justify-center w-9 h-9 rounded-lg text-white shadow"
              :class="getTheme(selectedNode.data.role).bg"
            >
              <component :is="getTheme(selectedNode.data.role).icon" class="w-5 h-5" />
            </span>
            <div class="flex-1">
              <div class="text-xs uppercase tracking-wider font-semibold"
                :class="getTheme(selectedNode.data.role).text">
                {{ selectedNode.data.role }}
              </div>
              <h2 class="text-base font-bold text-zinc-900">{{ selectedNode.data.label }}</h2>
            </div>
          </div>

          <p v-if="selectedNode.data.desc" class="text-sm text-zinc-700 leading-relaxed">
            {{ selectedNode.data.desc }}
          </p>

          <div v-if="selectedNode.data.detail"
            class="text-sm text-zinc-600 leading-relaxed whitespace-pre-line border-l-2 pl-3"
            :class="getTheme(selectedNode.data.role).border"
          >
            {{ selectedNode.data.detail }}
          </div>

          <div v-if="selectedNode.data.sourceFile"
            class="rounded-lg border border-zinc-200 bg-zinc-50 p-3"
          >
            <div class="flex items-center gap-1.5 text-xs font-semibold text-zinc-500 mb-1">
              <FileCode2 class="w-3.5 h-3.5" />
              SOURCE
            </div>
            <code class="text-xs text-zinc-800 break-all font-mono">
              {{ selectedNode.data.sourceFile }}
            </code>
          </div>

          <div v-if="selectedNode.data.planDoc"
            class="rounded-lg border border-zinc-200 bg-zinc-50 p-3"
          >
            <div class="flex items-center gap-1.5 text-xs font-semibold text-zinc-500 mb-1">
              <BookOpen class="w-3.5 h-3.5" />
              DESIGN DOC
            </div>
            <code class="text-xs text-zinc-800 break-all font-mono">
              {{ selectedNode.data.planDoc }}
            </code>
          </div>

          <div class="text-xs text-zinc-400 pt-2 border-t border-zinc-100">
            节点 ID · <code>{{ selectedNode.id }}</code>
          </div>
        </div>
      </aside>
    </div>
  </div>
</template>

<script lang="ts">
const legend = [
  { role: 'user' as const, label: '用户输入' },
  { role: 'decision' as const, label: '路由/决策' },
  { role: 'llm' as const, label: 'LLM 调用' },
  { role: 'tool' as const, label: '工具/MCP' },
  { role: 'storage' as const, label: '存储' },
  { role: 'compute' as const, label: '计算' },
  { role: 'output' as const, label: '输出' },
  { role: 'done' as const, label: '完成' },
]
</script>
