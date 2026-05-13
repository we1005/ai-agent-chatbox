<script setup lang="ts">
import { computed, ref } from 'vue'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { RadarChart, BarChart, LineChart } from 'echarts/charts'
import {
  TitleComponent, TooltipComponent, LegendComponent, GridComponent, PolarComponent,
} from 'echarts/components'
import VChart from 'vue-echarts'
import { useRouter } from 'vue-router'
import { ArrowLeft, BarChart3 } from 'lucide-vue-next'
import bench from './data/bench-snapshot.json'

use([
  CanvasRenderer, RadarChart, BarChart, LineChart,
  TitleComponent, TooltipComponent, LegendComponent, GridComponent, PolarComponent,
])

const router = useRouter()

// 颜色方案：跟 role-theme 大致一致
const palette = ['#0ea5e9', '#f59e0b', '#10b981', '#8b5cf6', '#f43f5e', '#22c55e', '#a855f7', '#06b6d4', '#fb923c', '#ec4899']

const cfgs = bench.configs
const names = cfgs.map(c => c.name)

// ── 雷达图：4 个维度（Recall@K / Faithfulness / Correctness / 速度反比）──
const radarOption = computed(() => ({
  title: { text: '四维度综合对比', left: 'center', textStyle: { fontSize: 14, fontWeight: 600 } },
  tooltip: { trigger: 'item' },
  legend: { type: 'scroll', bottom: 0, textStyle: { fontSize: 11 } },
  radar: {
    indicator: [
      { name: 'Recall@K', max: 1 },
      { name: 'Faithfulness', max: 1 },
      { name: 'Correctness', max: 1 },
      { name: '速度（1/lat）', max: 0.15 },
    ],
    radius: '62%',
    splitNumber: 4,
  },
  series: [{
    type: 'radar',
    data: cfgs.map((c, i) => ({
      value: [
        c.recallK ?? 0,
        c.faithfulness ?? 0,
        c.correctness ?? 0,
        +(1 / Math.max(c.latency, 1)).toFixed(3),
      ],
      name: c.name,
      lineStyle: { color: palette[i % palette.length], width: 1.5 },
      itemStyle: { color: palette[i % palette.length] },
      areaStyle: { color: palette[i % palette.length], opacity: 0.05 },
    })),
  }],
}))

// ── 柱状对比：3 个指标 × 10 配置 ──
const barOption = computed(() => ({
  title: { text: '三指标横向对比（Recall@K · Faithfulness · Correctness）', left: 'center', textStyle: { fontSize: 14, fontWeight: 600 } },
  tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
  legend: { top: 28 },
  grid: { left: 70, right: 30, top: 80, bottom: 60 },
  xAxis: { type: 'category', data: names, axisLabel: { rotate: 30, fontSize: 10 } },
  yAxis: { type: 'value', max: 1 },
  series: [
    { name: 'Recall@K', type: 'bar', data: cfgs.map(c => c.recallK ?? 0), itemStyle: { color: '#0ea5e9' } },
    { name: 'Faithfulness', type: 'bar', data: cfgs.map(c => c.faithfulness ?? 0), itemStyle: { color: '#f59e0b' } },
    { name: 'Correctness', type: 'bar', data: cfgs.map(c => c.correctness ?? 0), itemStyle: { color: '#10b981' } },
  ],
}))

// ── 延迟折线 ──
const latencyOption = computed(() => ({
  title: { text: '平均延迟（秒，越低越好）', left: 'center', textStyle: { fontSize: 14, fontWeight: 600 } },
  tooltip: { trigger: 'axis' },
  grid: { left: 60, right: 30, top: 50, bottom: 60 },
  xAxis: { type: 'category', data: names, axisLabel: { rotate: 30, fontSize: 10 } },
  yAxis: { type: 'value', name: 'sec' },
  series: [{
    type: 'line',
    smooth: true,
    data: cfgs.map(c => c.latency),
    itemStyle: { color: '#f43f5e' },
    areaStyle: { color: 'rgba(244,63,94,0.12)' },
    markLine: { data: [{ type: 'average', name: 'Avg' }] },
  }],
}))

const tab = ref<'radar' | 'bar' | 'latency' | 'table'>('radar')

const tabs = [
  { key: 'radar', label: '雷达图' },
  { key: 'bar', label: '柱状对比' },
  { key: 'latency', label: '延迟折线' },
  { key: 'table', label: '原始数据表' },
] as const
</script>

<template>
  <div class="min-h-screen bg-gradient-to-br from-zinc-50 to-white">
    <header class="border-b border-zinc-200 bg-white/80 backdrop-blur px-6 py-3 flex items-center gap-4">
      <button
        class="inline-flex items-center gap-1.5 text-sm text-zinc-600 hover:text-zinc-900 transition"
        @click="router.push('/wiki')"
      >
        <ArrowLeft class="w-4 h-4" />
        Wiki 首页
      </button>
      <div class="flex-1 min-w-0">
        <h1 class="text-lg font-bold text-zinc-900 flex items-center gap-2">
          <BarChart3 class="w-5 h-5 text-rose-500" />
          评测结果 · CRUD-mini
        </h1>
        <p class="text-xs text-zinc-500 truncate">
          {{ bench.meta.dataset }} · {{ bench.meta.n_per_config }} query × {{ cfgs.length }} 配置 · Judge {{ bench.meta.judge }}
        </p>
      </div>
    </header>

    <div class="max-w-6xl mx-auto px-6 py-6">
      <div class="flex gap-2 mb-4">
        <button
          v-for="t in tabs"
          :key="t.key"
          @click="tab = t.key"
          class="px-3 py-1.5 text-sm rounded-md transition border"
          :class="tab === t.key
            ? 'bg-primary text-white border-primary shadow-sm'
            : 'bg-white text-zinc-700 border-zinc-200 hover:border-zinc-400'"
        >{{ t.label }}</button>
      </div>

      <div class="rounded-xl border border-zinc-200 bg-white p-4 shadow-sm">
        <VChart v-if="tab === 'radar'" :option="radarOption" autoresize style="height: 520px;" />
        <VChart v-else-if="tab === 'bar'" :option="barOption" autoresize style="height: 480px;" />
        <VChart v-else-if="tab === 'latency'" :option="latencyOption" autoresize style="height: 380px;" />

        <div v-else class="overflow-x-auto">
          <table class="w-full text-sm">
            <thead class="bg-zinc-50 text-zinc-700 text-xs uppercase">
              <tr>
                <th class="text-left px-3 py-2">配置</th>
                <th class="text-right px-3 py-2">Recall@K</th>
                <th class="text-right px-3 py-2">Faithfulness</th>
                <th class="text-right px-3 py-2">Correctness</th>
                <th class="text-right px-3 py-2">延迟 (s)</th>
                <th class="text-right px-3 py-2">错误</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="(c, i) in cfgs" :key="c.name" class="border-t border-zinc-100">
                <td class="px-3 py-2 font-mono text-xs">
                  <span class="inline-block w-2 h-2 rounded mr-2" :style="{ background: palette[i % palette.length] }"></span>
                  {{ c.name }}
                </td>
                <td class="text-right px-3 py-2 tabular-nums">{{ c.recallK?.toFixed(3) ?? '—' }}</td>
                <td class="text-right px-3 py-2 tabular-nums">{{ c.faithfulness?.toFixed(3) ?? '—' }}</td>
                <td class="text-right px-3 py-2 tabular-nums">{{ c.correctness?.toFixed(3) ?? '—' }}</td>
                <td class="text-right px-3 py-2 tabular-nums">{{ c.latency.toFixed(2) }}</td>
                <td class="text-right px-3 py-2 tabular-nums">{{ c.errors }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>

      <div class="mt-4 text-xs text-zinc-500 leading-relaxed">
        <p>📌 <span class="font-semibold">关键观察</span>：</p>
        <ul class="list-disc pl-5 mt-1 space-y-1">
          <li>Graph RAG 在 <code>graph_mix</code> 档 Recall@K 达 0.970，是所有 10 个配置中最高 —— 这是 2026-04-23 修复 LightRAG 1.4.x parser 后的重跑结果（之前 graph_* 全为 0）。</li>
          <li>Agentic 三档延迟逐档递增（10s → 13s → 15s），但 Correctness 反而 grading 档最高（0.702）—— hallucination check 过严会扣分。</li>
          <li><code>off</code>（不召回直答）在 Correctness 上 0.679 已经接近平均水平，说明评测集中部分题型 LLM 内置知识就够用。</li>
        </ul>
        <p class="mt-3 text-zinc-400">数据快照来自 <code>RAG评测/报告/full-2026-04-22-with-ragas.md</code> + <code>graph-rerun-2026-04-23-with-ragas.md</code>。</p>
      </div>
    </div>
  </div>
</template>
