<script setup lang="ts">
import { computed, ref, onMounted, watch, nextTick } from 'vue'
import { useRouter } from 'vue-router'
import {
  ArrowLeft, ArrowUpRight, Minus, Plus, RotateCcw,
  ChevronsDownUp, ChevronsUpDown, FileCode2, Info,
} from 'lucide-vue-next'
import { allTrees, type TreeNode, type TreeModule } from './trees'
import { getTheme, roleLabel } from '../wiki/lib/role-theme'

const router = useRouter()

/* ────────────── Tab 切换 ────────────── */
const activeKey = ref<string>(allTrees[0].key)
const activeTree = computed<TreeModule>(() =>
  allTrees.find(t => t.key === activeKey.value) ?? allTrees[0]
)

/* 每个 tree 独立维护 collapsed / selected 状态 */
const collapsedByKey = ref<Record<string, Set<string>>>({})
const selectedByKey = ref<Record<string, string | null>>({})
const collapsed = computed(() => collapsedByKey.value[activeKey.value] ?? new Set<string>())
const selectedId = computed({
  get: () => selectedByKey.value[activeKey.value] ?? null,
  set: v => { selectedByKey.value = { ...selectedByKey.value, [activeKey.value]: v } },
})

function toggleCollapse(id: string) {
  const cur = new Set(collapsed.value)
  cur.has(id) ? cur.delete(id) : cur.add(id)
  collapsedByKey.value = { ...collapsedByKey.value, [activeKey.value]: cur }
}
function collapseAll() {
  const s = new Set<string>()
  function walk(n: TreeNode) {
    if (n.children?.length && n.id !== activeTree.value.root.id) s.add(n.id)
    n.children?.forEach(walk)
  }
  walk(activeTree.value.root)
  collapsedByKey.value = { ...collapsedByKey.value, [activeKey.value]: s }
}
function expandAll() {
  collapsedByKey.value = { ...collapsedByKey.value, [activeKey.value]: new Set() }
}

/* ────────────── 布局（Reingold-Tilford lite） ────────────── */
interface LayoutNode {
  node: TreeNode
  x: number; y: number
  parentId: string | null
  depth: number
  hasHiddenKids: boolean
}
interface LayoutEdge { from: string; to: string; label?: string }

const NODE_W = 190
const NODE_H = 64
const COL_GAP = 28
const ROW_GAP = 72
const UNIT_X = NODE_W + COL_GAP

const layout = computed(() => {
  const nodes: LayoutNode[] = []
  const edges: LayoutEdge[] = []
  let leafCol = 0

  function walk(n: TreeNode, depth: number, parentId: string | null): number {
    const isCollapsed = collapsed.value.has(n.id)
    const show = !isCollapsed && !!n.children?.length
    let cx: number
    if (!show) {
      cx = leafCol * UNIT_X + NODE_W / 2
      leafCol += 1
    } else {
      const xs = n.children!.map(c => walk(c, depth + 1, n.id))
      cx = (Math.min(...xs) + Math.max(...xs)) / 2
    }
    const cy = depth * (NODE_H + ROW_GAP) + NODE_H / 2
    nodes.push({
      node: n, x: cx, y: cy, parentId, depth,
      hasHiddenKids: isCollapsed && !!n.children?.length,
    })
    if (parentId) edges.push({ from: parentId, to: n.id, label: n.edgeLabel })
    return cx
  }

  walk(activeTree.value.root, 0, null)

  const maxX = nodes.reduce((m, n) => Math.max(m, n.x + NODE_W / 2), 0)
  const maxY = nodes.reduce((m, n) => Math.max(m, n.y + NODE_H / 2), 0)
  return { nodes, edges, width: maxX + 40, height: maxY + 40 }
})

const nodeById = computed(() => {
  const m = new Map<string, LayoutNode>()
  layout.value.nodes.forEach(n => m.set(n.node.id, n))
  return m
})

/* ────────────── hover path highlight ────────────── */
const hoverId = ref<string | null>(null)

function ancestorsOf(id: string | null): Set<string> {
  const s = new Set<string>()
  let cur = id
  while (cur) {
    s.add(cur)
    cur = nodeById.value.get(cur)?.parentId ?? null
  }
  return s
}
function descendantsOf(id: string | null): Set<string> {
  const s = new Set<string>()
  if (!id) return s
  function walk(nid: string) {
    s.add(nid)
    const ln = nodeById.value.get(nid)
    ln?.node.children?.forEach(c => { if (nodeById.value.has(c.id)) walk(c.id) })
  }
  walk(id)
  return s
}
const highlighted = computed<Set<string> | null>(() => {
  if (!hoverId.value) return null
  return new Set([...ancestorsOf(hoverId.value), ...descendantsOf(hoverId.value)])
})
const isHi = (id: string) => !highlighted.value || highlighted.value.has(id)
const isEdgeHi = (e: LayoutEdge) =>
  !highlighted.value || (highlighted.value.has(e.from) && highlighted.value.has(e.to))

/* ────────────── node actions ────────────── */
function onNodeClick(id: string, hasKids: boolean, ev: MouseEvent) {
  if (hasKids && (ev.altKey || ev.metaKey)) { toggleCollapse(id); return }
  selectedId.value = id
}

/* ────────────── 缩放 & 自适应 ────────────── */
const zoom = ref(1)
const canvasRef = ref<HTMLElement | null>(null)
function zoomIn()   { zoom.value = Math.min(1.6, +(zoom.value + 0.1).toFixed(2)) }
function zoomOut()  { zoom.value = Math.max(0.4, +(zoom.value - 0.1).toFixed(2)) }
function zoomReset(){ zoom.value = 1 }

function fitToCanvas() {
  if (!canvasRef.value) return
  const padH = 48, padV = 100
  const cw = canvasRef.value.clientWidth  - padH
  const ch = canvasRef.value.clientHeight - padV
  const fw = cw / layout.value.width
  const fh = ch / layout.value.height
  zoom.value = Math.max(0.4, Math.min(1, Math.round(Math.min(fw, fh) * 10) / 10))
}

onMounted(() => nextTick(fitToCanvas))
// 切 tab / 折叠变化时重新 fit
watch(activeKey, () => nextTick(fitToCanvas))

/* edge path */
function edgePath(e: LayoutEdge) {
  const a = nodeById.value.get(e.from)
  const b = nodeById.value.get(e.to)
  if (!a || !b) return ''
  const x1 = a.x, y1 = a.y + NODE_H / 2
  const x2 = b.x, y2 = b.y - NODE_H / 2
  const midY = (y1 + y2) / 2
  return `M ${x1} ${y1} C ${x1} ${midY}, ${x2} ${midY}, ${x2} ${y2}`
}
function edgeMid(e: LayoutEdge) {
  const a = nodeById.value.get(e.from)
  const b = nodeById.value.get(e.to)
  if (!a || !b) return { x: 0, y: 0 }
  return { x: (a.x + b.x) / 2, y: (a.y + NODE_H / 2 + b.y - NODE_H / 2) / 2 }
}

/* selected node */
const selectedNode = computed<TreeNode | null>(() => {
  if (!selectedId.value) return null
  return nodeById.value.get(selectedId.value)?.node ?? null
})

/* Legend (对应 /wiki 用色) */
const legend = [
  { role: 'user',     label: '用户' },
  { role: 'decision', label: '决策' },
  { role: 'llm',      label: 'LLM' },
  { role: 'tool',     label: '工具' },
  { role: 'storage',  label: '存储' },
  { role: 'compute',  label: '计算' },
  { role: 'output',   label: '输出' },
  { role: 'done',     label: '完成' },
] as const
</script>

<template>
  <div class="tree-root relative min-h-screen flex">
    <!-- 环境背景 -->
    <div class="ambient">
      <div class="blob b1"></div>
      <div class="blob b2"></div>
      <div class="grid-pattern"></div>
    </div>

    <!-- 主画布 -->
    <div class="relative z-10 flex-1 flex flex-col min-w-0">
      <!-- Header -->
      <header class="flex items-center justify-between gap-4 px-6 py-4 backdrop-blur-md bg-white/60 border-b border-zinc-200/70">
        <div class="flex items-center gap-3 min-w-0">
          <button
            class="inline-flex items-center gap-1.5 text-sm text-zinc-600 hover:text-zinc-900 px-3 py-1.5 rounded-full hover:bg-white transition shrink-0"
            @click="router.push('/wiki')"
          >
            <ArrowLeft class="w-4 h-4" />
            Wiki
          </button>
          <div class="h-4 w-px bg-zinc-200 shrink-0"></div>
          <div class="min-w-0">
            <p class="text-[10px] uppercase tracking-[0.28em] text-zinc-500 font-medium">Wiki · Tree View</p>
            <h1 class="text-lg font-bold text-zinc-900 leading-tight truncate">{{ activeTree.title }}</h1>
          </div>
        </div>

        <div class="flex items-center gap-1.5 shrink-0">
          <button class="tool-btn" title="展开全部" @click="expandAll">
            <ChevronsUpDown class="w-4 h-4" />
          </button>
          <button class="tool-btn" title="折叠可折叠项" @click="collapseAll">
            <ChevronsDownUp class="w-4 h-4" />
          </button>
          <div class="h-5 w-px bg-zinc-200 mx-1"></div>
          <button class="tool-btn" title="缩小" @click="zoomOut"><Minus class="w-4 h-4" /></button>
          <span class="tabular-nums text-xs text-zinc-600 w-10 text-center">{{ Math.round(zoom * 100) }}%</span>
          <button class="tool-btn" title="放大" @click="zoomIn"><Plus class="w-4 h-4" /></button>
          <button class="tool-btn" title="重置" @click="zoomReset"><RotateCcw class="w-4 h-4" /></button>
          <div class="h-5 w-px bg-zinc-200 mx-1"></div>
          <button
            class="px-3 py-1.5 rounded-full text-xs font-medium bg-zinc-900 text-white hover:bg-zinc-700 transition inline-flex items-center gap-1"
            @click="router.push(activeTree.wikiLink)"
          >
            Vue Flow 视图
            <ArrowUpRight class="w-3.5 h-3.5" />
          </button>
        </div>
      </header>

      <!-- Tabs -->
      <div class="px-6 py-3 backdrop-blur-md bg-white/40 border-b border-zinc-200/70 overflow-x-auto">
        <div class="flex items-center gap-1.5">
          <button
            v-for="t in allTrees"
            :key="t.key"
            @click="activeKey = t.key"
            class="tab"
            :class="{ 'tab-active': activeKey === t.key }"
          >
            {{ t.title }}
          </button>
        </div>
      </div>

      <!-- Note banner（当前 tree 的特殊说明） -->
      <div
        v-if="activeTree.note"
        class="mx-6 mt-4 flex items-start gap-2 px-3 py-2 rounded-lg bg-amber-50/70 border border-amber-200/60 text-xs text-amber-900 leading-snug"
      >
        <Info class="w-3.5 h-3.5 shrink-0 mt-0.5" />
        <span>{{ activeTree.note }}</span>
      </div>

      <!-- SVG canvas -->
      <div ref="canvasRef" class="flex-1 overflow-auto p-6 pt-6">
        <svg
          :width="layout.width * zoom"
          :height="layout.height * zoom"
          :viewBox="`0 0 ${layout.width} ${layout.height}`"
          preserveAspectRatio="xMinYMin meet"
          class="block mx-auto"
          @click.self="selectedId = null; hoverId = null"
        >
          <defs>
            <marker id="arr"    viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
              <path d="M 0 0 L 10 5 L 0 10 z" fill="#94a3b8"/>
            </marker>
            <marker id="arr-hi" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">
              <path d="M 0 0 L 10 5 L 0 10 z" fill="#0f172a"/>
            </marker>
            <filter id="node-shadow" x="-8%" y="-8%" width="116%" height="130%">
              <feDropShadow dx="0" dy="3" stdDeviation="3" flood-color="#0f172a" flood-opacity="0.08"/>
            </filter>
          </defs>

          <!-- Edges -->
          <g>
            <template v-for="e in layout.edges" :key="`e-${e.from}-${e.to}`">
              <path
                :d="edgePath(e)"
                fill="none"
                :stroke="isEdgeHi(e) ? '#0f172a' : '#cbd5e1'"
                :stroke-width="isEdgeHi(e) ? 1.8 : 1.2"
                :opacity="highlighted && !isEdgeHi(e) ? 0.22 : 1"
                :marker-end="isEdgeHi(e) ? 'url(#arr-hi)' : 'url(#arr)'"
                class="transition-all duration-200"
              />
              <g v-if="e.label">
                <rect
                  :x="edgeMid(e).x - (e.label.length * 3.5 + 8)"
                  :y="edgeMid(e).y - 9"
                  :width="e.label.length * 7 + 16" height="18" rx="9"
                  fill="#fff" stroke="#e2e8f0" stroke-width="1"
                  :opacity="highlighted && !isEdgeHi(e) ? 0.3 : 1"
                />
                <text
                  :x="edgeMid(e).x"
                  :y="edgeMid(e).y + 4"
                  text-anchor="middle" font-size="10.5"
                  fill="#475569" font-weight="500"
                  :opacity="highlighted && !isEdgeHi(e) ? 0.3 : 1"
                  style="font-family: 'Inter', system-ui, sans-serif;"
                >{{ e.label }}</text>
              </g>
            </template>
          </g>

          <!-- Nodes -->
          <g>
            <g
              v-for="n in layout.nodes"
              :key="n.node.id"
              :transform="`translate(${n.x - NODE_W / 2}, ${n.y - NODE_H / 2})`"
              :opacity="isHi(n.node.id) ? 1 : 0.28"
              class="cursor-pointer transition-opacity duration-200"
              @mouseenter="hoverId = n.node.id"
              @mouseleave="hoverId = null"
              @click="(ev) => onNodeClick(n.node.id, !!n.node.children?.length, ev)"
            >
              <rect
                :width="NODE_W" :height="NODE_H" rx="14" ry="14"
                :fill="n.node.id === activeTree.root.id ? '#0f172a' : 'rgba(255,255,255,0.95)'"
                :stroke="selectedId === n.node.id ? '#0f172a' : getTheme(n.node.role).edgeStroke"
                :stroke-width="selectedId === n.node.id ? 2.2 : 1.2"
                filter="url(#node-shadow)"
              />
              <rect
                v-if="n.node.id !== activeTree.root.id"
                x="0" y="0" width="4" :height="NODE_H" rx="2"
                :fill="getTheme(n.node.role).edgeStroke"
              />
              <text
                x="16" y="26"
                :fill="n.node.id === activeTree.root.id ? '#fff' : '#0f172a'"
                font-size="13.5" font-weight="700"
                style="font-family: 'Inter', 'Noto Serif SC', system-ui, sans-serif;"
              >{{ n.node.label }}</text>
              <text
                v-if="n.node.sub"
                x="16" y="44"
                :fill="n.node.id === activeTree.root.id ? 'rgba(255,255,255,0.7)' : '#64748b'"
                font-size="10" font-weight="500"
                style="font-family: 'Inter', system-ui, sans-serif; letter-spacing: 0.02em;"
              >{{ n.node.sub }}</text>
              <!-- 折叠徽章 -->
              <g v-if="n.hasHiddenKids">
                <circle :cx="NODE_W - 14" cy="14" r="9" fill="#0f172a"/>
                <text :x="NODE_W - 14" y="18" text-anchor="middle" fill="#fff" font-size="11" font-weight="700">+</text>
              </g>
              <g v-else-if="n.node.children?.length && n.node.id !== activeTree.root.id">
                <circle :cx="NODE_W - 14" cy="14" r="9" fill="rgba(15,23,42,0.08)"/>
                <text :x="NODE_W - 14" y="18" text-anchor="middle" fill="#0f172a" font-size="11" font-weight="700">−</text>
              </g>
            </g>
          </g>
        </svg>
      </div>

      <!-- Footer legend -->
      <footer class="px-6 py-3 backdrop-blur-md bg-white/60 border-t border-zinc-200/70 flex items-center justify-between gap-4 text-xs text-zinc-500 flex-wrap">
        <span class="shrink-0">
          <kbd class="kbd">Click</kbd> 详情 ·
          <kbd class="kbd">⌥/⌘ Click</kbd> 折叠 ·
          <kbd class="kbd">Hover</kbd> 聚焦路径
        </span>
        <div class="flex items-center gap-3 flex-wrap">
          <span v-for="r in legend" :key="r.role" class="inline-flex items-center gap-1">
            <span class="w-2.5 h-2.5 rounded-sm" :style="{ background: getTheme(r.role).edgeStroke }"></span>
            {{ r.label }}
          </span>
        </div>
      </footer>
    </div>

    <!-- 详情抽屉 -->
    <aside class="relative z-10 w-[340px] shrink-0 border-l border-zinc-200 bg-white/80 backdrop-blur-xl overflow-y-auto">
      <div v-if="!selectedNode" class="p-6">
        <p class="text-[10px] uppercase tracking-[0.28em] text-zinc-500 font-medium mb-3">Details</p>
        <h2 class="text-base font-semibold text-zinc-900 mb-3">{{ activeTree.title }}</h2>
        <p class="text-sm text-zinc-600 leading-relaxed">{{ activeTree.caption }}</p>
        <p class="mt-4 text-sm text-zinc-500 leading-relaxed">
          顶部 Tab 切换 6 个子模块。任何节点点击查看详情；<kbd class="kbd">⌥ Click</kbd> 展开/折叠。
        </p>
        <div class="mt-6 rounded-xl border border-zinc-200 p-4 bg-zinc-50/50">
          <p class="text-[10px] uppercase tracking-[0.24em] font-semibold text-zinc-500 mb-2">提示</p>
          <p class="text-xs text-zinc-600 leading-relaxed">
            同一流程另有可拖拽节点图（Vue Flow）视图。点右上 "Vue Flow 视图" 切换。
          </p>
        </div>
      </div>

      <div v-else class="p-6">
        <button class="text-xs text-zinc-400 hover:text-zinc-700 mb-4 inline-flex items-center gap-1" @click="selectedId = null">
          ← 返回总览
        </button>
        <div class="flex items-center gap-2 mb-3">
          <span class="inline-block w-8 h-8 rounded-lg" :style="{ background: getTheme(selectedNode.role).edgeStroke }"></span>
          <div class="flex-1">
            <p class="text-[10px] uppercase tracking-[0.24em] font-semibold" :class="getTheme(selectedNode.role).text">
              {{ roleLabel[selectedNode.role] }}
            </p>
            <h2 class="text-lg font-bold text-zinc-900 leading-tight">{{ selectedNode.label }}</h2>
          </div>
        </div>
        <p v-if="selectedNode.sub" class="text-xs text-zinc-500 mb-4 tracking-wider">{{ selectedNode.sub }}</p>

        <p v-if="selectedNode.desc" class="text-sm text-zinc-700 leading-relaxed border-l-2 pl-3 mb-5"
           :style="{ borderColor: getTheme(selectedNode.role).edgeStroke }">
          {{ selectedNode.desc }}
        </p>

        <div v-if="selectedNode.source" class="rounded-lg border border-zinc-200 bg-zinc-50 p-3 mb-3">
          <div class="flex items-center gap-1.5 text-[10px] tracking-[0.24em] uppercase font-semibold text-zinc-500 mb-1">
            <FileCode2 class="w-3.5 h-3.5" /> Source
          </div>
          <code class="text-xs text-zinc-800 break-all font-mono">{{ selectedNode.source }}</code>
        </div>

        <button v-if="selectedNode.link"
          class="w-full mt-3 inline-flex items-center justify-center gap-1.5 px-4 py-2.5 rounded-xl bg-zinc-900 text-white text-sm font-medium hover:bg-zinc-700 transition"
          @click="router.push(selectedNode.link!)"
        >
          进入对应 Wiki 子页 <ArrowUpRight class="w-4 h-4" />
        </button>

        <div v-if="selectedNode.children?.length" class="mt-6">
          <p class="text-[10px] uppercase tracking-[0.24em] font-semibold text-zinc-500 mb-2">
            子节点 · {{ selectedNode.children.length }}
          </p>
          <div class="flex flex-wrap gap-1.5">
            <button
              v-for="c in selectedNode.children" :key="c.id"
              class="px-2.5 py-1 rounded-full bg-white border border-zinc-200 text-xs text-zinc-700 hover:border-zinc-400 transition"
              @click="selectedId = c.id"
            >{{ c.label }}</button>
          </div>
        </div>

        <div class="mt-6 text-xs text-zinc-400 pt-4 border-t border-zinc-100">
          节点 ID · <code class="font-mono">{{ selectedNode.id }}</code>
        </div>
      </div>
    </aside>
  </div>
</template>

<style scoped>
.tree-root {
  background: #f5f5f7;
  font-family: 'Inter', 'Noto Serif SC', -apple-system, BlinkMacSystemFont, sans-serif;
}

.ambient { position: fixed; inset: -8%; pointer-events: none; z-index: 0; }
.grid-pattern {
  position: absolute; inset: 0;
  background-image:
    linear-gradient(to right, rgba(0,0,0,0.035) 1px, transparent 1px),
    linear-gradient(to bottom, rgba(0,0,0,0.035) 1px, transparent 1px);
  background-size: 48px 48px;
  mask-image: radial-gradient(ellipse at center, #000 35%, transparent 80%);
  -webkit-mask-image: radial-gradient(ellipse at center, #000 35%, transparent 80%);
}
.blob { position: absolute; border-radius: 50%; filter: blur(90px); opacity: 0.45; }
.blob.b1 { top: -6%; left: 10%;  width: 460px; height: 460px; background: radial-gradient(closest-side, hsl(210 92% 72% / 0.6), transparent); }
.blob.b2 { bottom: 10%; right: 14%; width: 520px; height: 520px; background: radial-gradient(closest-side, hsl(320 82% 72% / 0.5), transparent); }

.tool-btn {
  display: inline-flex; align-items: center; justify-content: center;
  width: 32px; height: 32px; border-radius: 8px;
  color: #475569; transition: all 160ms;
}
.tool-btn:hover { background: rgba(15,23,42,0.06); color: #0f172a; }

.tab {
  padding: 6px 14px;
  border-radius: 9999px;
  font-size: 12.5px;
  font-weight: 500;
  color: #475569;
  white-space: nowrap;
  transition: all 180ms;
}
.tab:hover { background: rgba(15,23,42,0.05); color: #0f172a; }
.tab-active {
  background: #0f172a;
  color: #fff;
}
.tab-active:hover { background: #0f172a; color: #fff; }

.kbd {
  font-family: 'Berkeley Mono', ui-monospace, monospace;
  font-size: 10px; padding: 1px 6px;
  border: 1px solid #e2e8f0; border-bottom-width: 2px;
  border-radius: 4px; background: #fff; color: #334155;
}
</style>
