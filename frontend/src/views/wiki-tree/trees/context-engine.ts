import type { TreeModule } from './types'

export const contextEngineTree: TreeModule = {
  key: 'context-engine',
  title: '长上下文引擎 v2',
  caption: '7 层上下文模型 + Condenser Pipeline',
  note: '左子树 · 7 层上下文（L1…L7）；右子树 · Condenser Pipeline（events → … → langchain messages）。二者最终汇合到 LLM 可消费的 messages 数组。',
  wikiLink: '/wiki/context-engine',
  root: {
    id: 'root',
    label: 'Context Engine v2',
    sub: '集百家之长',
    role: 'compute',
    desc: 'OpenHands 式递归压缩 + Mem0 双时间记忆 + Zep 的 valid_at/invalidated_at schema。',
    source: 'backend/app/services/context_router.py',
    children: [
      {
        id: 'layers',
        label: '7-Layer Model',
        sub: '从静到动',
        role: 'storage',
        children: [
          { id: 'l1', label: 'L1 · Identity',   sub: '系统人设 + 用户画像（永久）', role: 'storage', source: 'backend/app/prompts/chat_system.j2' },
          { id: 'l2', label: 'L2 · Recent',     sub: '最近 N turn 原文（滚动窗口）', role: 'storage' },
          { id: 'l3', label: 'L3 · Summary',    sub: '滚动摘要（LLMSummarizingCondenser）', role: 'compute' },
          { id: 'l4', label: 'L4 · Memory',     sub: 'Mem0 长期事实（双时间）', role: 'storage' },
          { id: 'l5', label: 'L5 · Retrieval',  sub: 'KB 召回结果（Qdrant / LightRAG）', role: 'storage' },
          { id: 'l6', label: 'L6 · Runtime',    sub: '当前 turn 内工具回执', role: 'compute' },
          { id: 'l7', label: 'L7 · View',       sub: '最终 messages 数组', role: 'output' },
        ],
      },
      {
        id: 'cond',
        label: 'Condenser Pipeline',
        sub: 'events → messages',
        role: 'compute',
        children: [
          {
            id: 'evt',
            label: 'events 流',
            sub: 'Mongo events collection',
            role: 'storage',
            source: 'backend/app/db/models.py',
            children: [
              {
                id: 'tc',
                label: 'ToolOutputCondenser',
                sub: '截断超长 tool 输出',
                role: 'compute',
                children: [
                  {
                    id: 'sc',
                    label: 'LLMSummarizingCondenser',
                    sub: '递归滚动摘要（OpenHands）',
                    role: 'compute',
                    children: [
                      {
                        id: 'rc',
                        label: 'RecentBufferCondenser',
                        sub: '保留最近 K 条原文',
                        role: 'compute',
                        children: [
                          {
                            id: 'e2m',
                            label: 'events_to_messages',
                            sub: '事件 → BaseMessage',
                            role: 'compute',
                            children: [
                              { id: 'lc', label: 'langchain messages', sub: '塞进 LLM 的最终消息数组', role: 'output' },
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
        ],
      },
    ],
  },
}
