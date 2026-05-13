// 角色 → 视觉 token 的中央映射。
// 改配色只改这一个文件；所有 RoleNode + 边色都从这里读。
import * as Lucide from 'lucide-vue-next'
import type { Component } from 'vue'

export type Role =
  | 'user'
  | 'decision'
  | 'llm'
  | 'tool'
  | 'storage'
  | 'compute'
  | 'output'
  | 'done'
  | 'note'

export interface RoleTheme {
  bg: string          // node 主背景（filled）
  bgSoft: string      // node hover/选中前的浅底
  text: string        // node 正文文字
  border: string      // node 描边
  badge: string       // 顶部小标签
  edgeStroke: string  // edge stroke 颜色（hex/oklch 字符串，给 SVG 用）
  icon: Component     // lucide 图标
}

export const roleTheme: Record<Role, RoleTheme> = {
  user: {
    bg: 'bg-sky-500',
    bgSoft: 'bg-sky-50',
    text: 'text-sky-900',
    border: 'border-sky-300',
    badge: 'bg-sky-100 text-sky-700',
    edgeStroke: '#0ea5e9',
    icon: Lucide.User,
  },
  decision: {
    bg: 'bg-amber-500',
    bgSoft: 'bg-amber-50',
    text: 'text-amber-900',
    border: 'border-amber-300',
    badge: 'bg-amber-100 text-amber-800',
    edgeStroke: '#f59e0b',
    icon: Lucide.GitBranch,
  },
  llm: {
    bg: 'bg-violet-500',
    bgSoft: 'bg-violet-50',
    text: 'text-violet-900',
    border: 'border-violet-300',
    badge: 'bg-violet-100 text-violet-700',
    edgeStroke: '#8b5cf6',
    icon: Lucide.Sparkles,
  },
  tool: {
    bg: 'bg-emerald-500',
    bgSoft: 'bg-emerald-50',
    text: 'text-emerald-900',
    border: 'border-emerald-300',
    badge: 'bg-emerald-100 text-emerald-800',
    edgeStroke: '#10b981',
    icon: Lucide.Wrench,
  },
  storage: {
    bg: 'bg-slate-500',
    bgSoft: 'bg-slate-50',
    text: 'text-slate-900',
    border: 'border-slate-300',
    badge: 'bg-slate-100 text-slate-700',
    edgeStroke: '#64748b',
    icon: Lucide.Database,
  },
  compute: {
    bg: 'bg-fuchsia-500',
    bgSoft: 'bg-fuchsia-50',
    text: 'text-fuchsia-900',
    border: 'border-fuchsia-300',
    badge: 'bg-fuchsia-100 text-fuchsia-700',
    edgeStroke: '#d946ef',
    icon: Lucide.Layers,
  },
  output: {
    bg: 'bg-rose-500',
    bgSoft: 'bg-rose-50',
    text: 'text-rose-900',
    border: 'border-rose-300',
    badge: 'bg-rose-100 text-rose-700',
    edgeStroke: '#f43f5e',
    icon: Lucide.Send,
  },
  done: {
    bg: 'bg-green-600',
    bgSoft: 'bg-green-50',
    text: 'text-green-900',
    border: 'border-green-300',
    badge: 'bg-green-100 text-green-700',
    edgeStroke: '#16a34a',
    icon: Lucide.CircleCheck,
  },
  note: {
    bg: 'bg-zinc-500',
    bgSoft: 'bg-zinc-50',
    text: 'text-zinc-900',
    border: 'border-zinc-300',
    badge: 'bg-zinc-100 text-zinc-700',
    edgeStroke: '#71717a',
    icon: Lucide.StickyNote,
  },
}

export function getTheme(role: Role | string | undefined): RoleTheme {
  return roleTheme[(role as Role) ?? 'note'] ?? roleTheme.note
}

// 角色中文标签（顶部 badge 文字）
export const roleLabel: Record<Role, string> = {
  user: '用户',
  decision: '决策',
  llm: 'LLM',
  tool: '工具',
  storage: '存储',
  compute: '计算',
  output: '输出',
  done: '完成',
  note: '说明',
}
