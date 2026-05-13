// Wiki 页节点 / 边的统一数据结构。
// 每个 wiki 页 data/*.ts 都导出这两个数组，由 WikiPage.vue 渲染。
import type { Role } from './lib/role-theme'
import type { Component } from 'vue'

export interface RoleNodeData {
  role: Role
  label: string
  desc?: string
  /** lucide-vue-next 图标名，未指定则用 role 默认 */
  icon?: string | Component
  /** 关联代码文件，例如 backend/app/api/endpoints/chat.py:17 */
  sourceFile?: string
  /** 相关计划文档 */
  planDoc?: string
  /** 用于详情面板的长说明（支持 \n 换行） */
  detail?: string
}

export interface WikiNode {
  id: string
  type?: 'role'
  position: { x: number; y: number }
  data: RoleNodeData
}

export interface WikiEdge {
  id: string
  source: string
  target: string
  label?: string
  animated?: boolean
  /** 主色取自 source role；可显式覆盖 */
  strokeRole?: Role
  /** 'default' (bezier) | 'smoothstep' | 'step' | 'straight' */
  type?: string
  /** RoleNode 上的 handle id: 'top' | 'bottom'（默认走 left/right） */
  sourceHandle?: string
  targetHandle?: string
  /** 加粗强调（如循环回边） */
  emphasize?: boolean
}

export interface WikiPageData {
  title: string
  caption: string
  nodes: WikiNode[]
  edges: WikiEdge[]
  /** 默认侧栏内容（无节点选中时） */
  intro?: string
}
