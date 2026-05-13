import type { WikiPageData } from '../types'

// Memory lifecycle: turn 结束 → reflect_and_write 全流程
const X = (col: number) => col * 320
const Y = (row: number) => row * 180

export const memoryLifecycle: WikiPageData = {
  title: '记忆生命周期',
  caption: 'turn 结束 → 后台反思 → Mem0 LLM judge（ADD/UPDATE/DELETE/NOOP）→ 双时间 schema',
  intro:
    'reflect_and_write 是 fire-and-forget 后台任务，对用户零延迟。\n\nMem0 的 LLM judge 决定每条候选记忆的命运：写入新条目（ADD）、更新已有（UPDATE）、删除矛盾（DELETE）或丢弃（NOOP）。\n\n所有写入同时 mirror 到 Mongo memories 集合，带双时间字段 valid_at + invalidated_at + superseded_by（Zep/Graphiti 模式）。',
  nodes: [
    { id: 'turn', position: { x: X(0), y: Y(1) }, data: { role: 'output', label: 'turn 结束', desc: 'SSE [DONE] 后端点立即返回', sourceFile: 'backend/app/api/endpoints/chat.py' } },
    { id: 'task', position: { x: X(1), y: Y(1) }, data: { role: 'compute', label: 'asyncio.create_task', desc: 'fire-and-forget · 不 await · 用户零延迟' } },
    { id: 'reflect', position: { x: X(2), y: Y(1) }, data: { role: 'llm', label: 'reflect_and_write', desc: '入口函数 · MEMORY_REFLECT_ENABLED=false 时立即 return []', sourceFile: 'backend/app/services/memory_service.py:reflect_and_write' } },
    { id: 'last-flush', position: { x: X(3), y: Y(0) }, data: { role: 'storage', label: '读 last_memory_flush', desc: 'events 中找最近 memory_flush · 起点游标' } },
    { id: 'debounce', position: { x: X(3), y: Y(1) }, data: { role: 'decision', label: 'debounce check', desc: '间隔 turn < N 直接跳过 · 防抖' } },
    { id: 'load', position: { x: X(3), y: Y(2) }, data: { role: 'storage', label: 'load dialog window', desc: '从游标到当前 turn 的所有 user/assistant 消息' } },
    { id: 'mem0', position: { x: X(4), y: Y(1) }, data: { role: 'llm', label: 'mem0.add(messages)', desc: 'Mem0 内部 LLM 抽事实 + 与已有记忆做 judge' } },
    { id: 'judge', position: { x: X(5), y: Y(1) }, data: { role: 'decision', label: 'LLM judge', desc: 'ADD / UPDATE / DELETE / NOOP 四向分类' } },
    { id: 'qdrant', position: { x: X(6), y: Y(0) }, data: { role: 'storage', label: 'Qdrant mem0 集合', desc: 'Mem0 自带向量持久化' } },
    { id: 'mongo', position: { x: X(6), y: Y(2) }, data: { role: 'storage', label: 'Mongo memories', desc: '镜像写入 · 双时间 valid_at / invalidated_at / superseded_by', sourceFile: 'backend/app/db/models.py' } },
    { id: 'mark', position: { x: X(7), y: Y(1) }, data: { role: 'done', label: 'mark memory_flush', desc: '在 events 写一条 memory_flush · 下次 reflect 起点' } },
  ],
  edges: [
    { id: 'e1', source: 'turn', target: 'task' },
    { id: 'e2', source: 'task', target: 'reflect' },
    { id: 'e3a', source: 'reflect', target: 'last-flush' },
    { id: 'e3b', source: 'reflect', target: 'debounce' },
    { id: 'e3c', source: 'reflect', target: 'load' },
    { id: 'e4', source: 'load', target: 'mem0' },
    { id: 'e4b', source: 'last-flush', target: 'mem0' },
    { id: 'e5', source: 'mem0', target: 'judge' },
    { id: 'e6a', source: 'judge', target: 'qdrant', label: 'ADD / UPDATE', strokeRole: 'storage' },
    { id: 'e6b', source: 'judge', target: 'mongo', label: 'mirror（含 DELETE）', strokeRole: 'storage' },
    { id: 'e7', source: 'mongo', target: 'mark' },
    { id: 'e7b', source: 'qdrant', target: 'mark' },
  ],
}
