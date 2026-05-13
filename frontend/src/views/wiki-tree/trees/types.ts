// 树状视图的节点模型（与 /wiki 的 role 体系共用）。
// 每个子模块（Classic / Solo / Context / Memory / RAG / Architecture）
// 都导出一个 TreeModule 实例，由 WikiTreePage 统一渲染。
import type { Role } from '../../wiki/lib/role-theme'

export interface TreeNode {
  id: string
  label: string
  /** 二行副标（小字，显示在 label 下方） */
  sub?: string
  role: Role
  /** 详情说明（右侧抽屉展示） */
  desc?: string
  /** 关联代码文件 */
  source?: string
  /** 可跳转到的 /wiki 子页（节点详情抽屉里会出现"进入 Vue Flow 视图"按钮） */
  link?: string
  /** 边标签（本节点 → 父节点之间的箭头上写的文字） */
  edgeLabel?: string
  children?: TreeNode[]
}

export interface TreeModule {
  key: string
  title: string
  caption: string
  /** 若流程含有树无法表达的成分（合流 / 循环），写在这里显示在画布顶部 */
  note?: string
  /** 对应 /wiki 子页路由，右上角提供"切到 Vue Flow 视图"跳转 */
  wikiLink: string
  root: TreeNode
}
