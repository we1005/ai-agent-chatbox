import type { WikiPageData } from '../types'

// Context Engine v2 · 7 层 + Condenser Pipeline
const Lx = 0       // 7 层堆叠列
const Cx = 640     // condenser pipeline 列
const Mx = 1280    // 输出列
const Y = (i: number) => 60 + i * 130

export const contextEngine: WikiPageData = {
  title: '长上下文引擎 v2',
  caption: '7 层上下文模型（OpenHands / Mem0 / Zep / Letta 之集大成）+ Condenser Pipeline',
  intro:
    '左侧 7 层（L1 → L7）从静到动堆叠：身份 / 最近 / 摘要 / 记忆 / 检索 / 运行时 / 视图。\n\n中间 Condenser Pipeline 将 events 按算法压成 LLM 可消费的 messages：\nevents → ToolOutputCondenser → LLMSummarizingCondenser → RecentBufferCondenser → events_to_messages → langchain。\n\n详细设计见 plan-doc-dir/长上下文机制设计v2·集百家之长.md。',
  nodes: [
    // ── 左侧 7 层 ──
    { id: 'L1', position: { x: Lx, y: Y(0) }, data: { role: 'storage', label: 'L1 · Identity', desc: '系统人设 + 用户画像（永久）', sourceFile: 'backend/app/prompts/chat_system.j2' } },
    { id: 'L2', position: { x: Lx, y: Y(1) }, data: { role: 'storage', label: 'L2 · Recent', desc: '最近 N turn 原文（滚动窗口）', sourceFile: 'backend/app/services/context_router.py' } },
    { id: 'L3', position: { x: Lx, y: Y(2) }, data: { role: 'compute', label: 'L3 · Summary', desc: '滚动摘要（OpenHands LLMSummarizingCondenser）' } },
    { id: 'L4', position: { x: Lx, y: Y(3) }, data: { role: 'storage', label: 'L4 · Memory', desc: 'Mem0 长期事实（双时间 valid_at / invalidated_at）', sourceFile: 'backend/app/services/memory_service.py' } },
    { id: 'L5', position: { x: Lx, y: Y(4) }, data: { role: 'storage', label: 'L5 · Retrieval', desc: 'KB 召回结果（Qdrant / LightRAG）' } },
    { id: 'L6', position: { x: Lx, y: Y(5) }, data: { role: 'compute', label: 'L6 · Runtime', desc: 'tool_outputs · 当前 turn 内的工具回执' } },
    { id: 'L7', position: { x: Lx, y: Y(6) }, data: { role: 'output', label: 'L7 · View', desc: '最终拼装给 LLM 的 messages 数组' } },

    // ── Condenser Pipeline ──
    { id: 'evt', position: { x: Cx, y: Y(0) }, data: { role: 'storage', label: 'events 流', desc: 'Mongo events collection · turn 级追加', sourceFile: 'backend/app/db/models.py' } },
    { id: 'tool-cond', position: { x: Cx, y: Y(1.5) }, data: { role: 'compute', label: 'ToolOutputCondenser', desc: '截断超长 tool 输出（保头尾）' } },
    { id: 'sum-cond', position: { x: Cx, y: Y(3) }, data: { role: 'compute', label: 'LLMSummarizingCondenser', desc: '递归滚动摘要（OpenHands 算法）' } },
    { id: 'recent-cond', position: { x: Cx, y: Y(4.5) }, data: { role: 'compute', label: 'RecentBufferCondenser', desc: '保留最近 K 条原文不压缩' } },
    { id: 'e2m', position: { x: Cx, y: Y(6) }, data: { role: 'compute', label: 'events_to_messages', desc: '事件 → langchain BaseMessage 列表' } },

    // ── 输出 ──
    { id: 'lc', position: { x: Mx, y: Y(3) }, data: { role: 'output', label: 'langchain messages', desc: '最终塞进 LLM 的消息数组', planDoc: 'analysis-for-backend/context-engine.md' } },
  ],
  edges: [
    // 7 层堆叠暗示（用淡边）
    { id: 'l12', source: 'L1', target: 'L2', animated: false, strokeRole: 'note' },
    { id: 'l23', source: 'L2', target: 'L3', animated: false, strokeRole: 'note' },
    { id: 'l34', source: 'L3', target: 'L4', animated: false, strokeRole: 'note' },
    { id: 'l45', source: 'L4', target: 'L5', animated: false, strokeRole: 'note' },
    { id: 'l56', source: 'L5', target: 'L6', animated: false, strokeRole: 'note' },
    { id: 'l67', source: 'L6', target: 'L7', animated: false, strokeRole: 'note' },

    // 各层 → 对应 condenser
    { id: 'l2c', source: 'L2', target: 'recent-cond' },
    { id: 'l3c', source: 'L3', target: 'sum-cond' },
    { id: 'l6c', source: 'L6', target: 'tool-cond' },

    // condenser pipeline
    { id: 'p1', source: 'evt', target: 'tool-cond' },
    { id: 'p2', source: 'tool-cond', target: 'sum-cond' },
    { id: 'p3', source: 'sum-cond', target: 'recent-cond' },
    { id: 'p4', source: 'recent-cond', target: 'e2m' },
    { id: 'p5', source: 'e2m', target: 'lc' },

    // L7 → 最终输出
    { id: 'l7out', source: 'L7', target: 'lc', strokeRole: 'output' },
  ],
}
