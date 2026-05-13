import type { TreeModule } from './types'

export const memoryLifecycleTree: TreeModule = {
  key: 'memory-lifecycle',
  title: '记忆生命周期',
  caption: 'turn 结束 → 后台反思 → Mem0 LLM judge → 双时间 schema',
  note: 'ADD / UPDATE / DELETE / NOOP 四条判决最终都汇合到 "mark memory_flush"（图中未合并绘制，仅作语义说明）。',
  wikiLink: '/wiki/memory-lifecycle',
  root: {
    id: 'turn',
    label: 'turn 结束',
    sub: 'SSE [DONE] 后端点返回',
    role: 'output',
    source: 'backend/app/api/endpoints/chat.py',
    children: [
      {
        id: 'task',
        label: 'asyncio.create_task',
        sub: 'fire-and-forget · 用户零延迟',
        role: 'compute',
        children: [
          {
            id: 'reflect',
            label: 'reflect_and_write',
            sub: 'MEMORY_REFLECT_ENABLED=false 时 return []',
            role: 'llm',
            source: 'backend/app/services/memory_service.py:reflect_and_write',
            children: [
              {
                id: 'prep',
                label: '准备数据',
                sub: 'cursor + debounce + load',
                role: 'compute',
                children: [
                  { id: 'last',     label: '读 last_memory_flush', sub: '游标起点',          role: 'storage' },
                  { id: 'debounce', label: 'debounce check',        sub: '间隔 turn < N 跳过', role: 'decision' },
                  { id: 'load',     label: 'load dialog window',    sub: 'user/assistant 消息', role: 'storage' },
                ],
              },
              {
                id: 'mem0',
                label: 'mem0.add(messages)',
                sub: 'Mem0 内部 LLM 抽事实',
                role: 'llm',
                children: [
                  {
                    id: 'judge',
                    label: 'LLM judge',
                    sub: '与已有记忆做比对',
                    role: 'decision',
                    desc: '四向分类：新增（ADD）/ 更新已有（UPDATE）/ 删除矛盾（DELETE）/ 丢弃（NOOP）。',
                    children: [
                      {
                        id: 'add',
                        label: 'ADD',
                        sub: '写入新记忆',
                        role: 'storage',
                        edgeLabel: '新事实',
                        children: [{ id: 'add-q', label: 'Qdrant mem0 集合', role: 'storage' }],
                      },
                      {
                        id: 'update',
                        label: 'UPDATE',
                        sub: '更新已有 · 标 superseded_by',
                        role: 'storage',
                        edgeLabel: '事实变更',
                        children: [{ id: 'upd-m', label: 'Mongo memories', sub: '双时间 schema', role: 'storage' }],
                      },
                      {
                        id: 'delete',
                        label: 'DELETE',
                        sub: '矛盾 · 标 invalidated_at',
                        role: 'storage',
                        edgeLabel: '事实矛盾',
                      },
                      {
                        id: 'noop',
                        label: 'NOOP',
                        sub: '已存在或无价值',
                        role: 'note',
                        edgeLabel: '无新增',
                      },
                      {
                        id: 'mark',
                        label: 'mark memory_flush',
                        sub: '更新 events 游标',
                        role: 'done',
                        desc: '四条判决都最终走这里更新下次 reflect 的起点游标（图中为简化未连接）。',
                      },
                    ],
                  },
                ],
              },
            ],
          },
        ],
      },
    ],
  },
}
