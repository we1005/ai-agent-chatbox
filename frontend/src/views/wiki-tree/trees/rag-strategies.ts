import type { TreeModule } from './types'

export const ragStrategiesTree: TreeModule = {
  key: 'rag-strategies',
  title: 'RAG 策略矩阵',
  caption: '5 主策略 × 各自档位 · Classic 路径运行时切换',
  wikiLink: '/wiki/rag-strategies',
  root: {
    id: 'root',
    label: 'RAG 策略',
    sub: 'graph > agentic > multi_query > classical > off',
    role: 'decision',
    desc: '优先级硬编码在 chat_service.chat_stream 里，高档位启用时覆盖低档。',
    source: 'backend/app/services/chat_service.py',
    children: [
      { id: 'off',   label: 'off',        sub: '不召回 · 直答',           role: 'note' },
      { id: 'cl',    label: 'classical',  sub: 'BGE-M3 dense+sparse',     role: 'storage' },
      { id: 'mq',    label: 'multi_query', sub: 'LLM rewrite × N + RRF',  role: 'compute' },
      {
        id: 'agent',
        label: 'agentic',
        sub: '评估循环',
        role: 'compute',
        source: 'backend/app/services/agentic_rag.py',
        children: [
          { id: 'a-off',   label: 'off',             sub: '完全禁用',             role: 'note' },
          { id: 'a-grade', label: 'grading_only',    sub: '只评分不重写',          role: 'compute' },
          { id: 'a-rw',    label: 'grading_rewrite', sub: '评分 + 失败重写',       role: 'compute' },
          { id: 'a-full',  label: 'full',            sub: '全开 · 含 hallucination check', role: 'compute' },
        ],
      },
      {
        id: 'graph',
        label: 'graph',
        sub: 'LightRAG',
        role: 'storage',
        source: 'backend/app/services/graph_rag.py',
        desc: '启用时覆盖 agentic + multi_query；hallucination check 跳过。',
        children: [
          { id: 'g-naive',  label: 'naive',  sub: '纯向量（baseline）',  role: 'storage' },
          { id: 'g-local',  label: 'local',  sub: '实体邻域',             role: 'storage' },
          { id: 'g-global', label: 'global', sub: '社区摘要',             role: 'storage' },
          { id: 'g-hybrid', label: 'hybrid', sub: 'local + global',      role: 'storage' },
          { id: 'g-mix',    label: 'mix',    sub: '推荐档 · 0.970 Recall@K', role: 'storage' },
        ],
      },
    ],
  },
}
