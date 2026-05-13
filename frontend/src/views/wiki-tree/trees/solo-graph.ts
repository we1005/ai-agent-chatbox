import type { TreeModule } from './types'

export const soloGraphTree: TreeModule = {
  key: 'solo-graph',
  title: 'Solo Agent · LangGraph',
  caption: '/api/chat/solo · classify_complexity → planner → tools → ... (ReAct 循环)',
  note: 'planner ⇄ tools 是一个循环（recursion_limit=16）。本树展示单次前向链路；回边省略，跳到 Vue Flow 视图可看 U 型 loop。',
  wikiLink: '/wiki/solo-graph',
  root: {
    id: 'start',
    label: 'START',
    sub: 'POST /api/chat/solo',
    role: 'user',
    source: 'backend/app/api/endpoints/solo.py',
    children: [
      {
        id: 'classify',
        label: 'classify_complexity',
        sub: 'LLM 预判 query 复杂度',
        role: 'decision',
        source: 'backend/app/services/solo/graph.py',
        children: [
          {
            id: 'planner',
            label: 'planner',
            sub: 'DeepSeek + tools schema',
            role: 'llm',
            desc: '每轮返回 (reasoning, tool_calls, answer)。tool_calls 非空 → tools；空 → END。',
            children: [
              {
                id: 'end',
                label: 'END',
                sub: 'tool_calls 为空 → 流式输出',
                role: 'done',
                edgeLabel: '① 无 tool_calls',
              },
              {
                id: 'tools',
                label: 'tools',
                sub: '5 个工具自主调度',
                role: 'tool',
                edgeLabel: '② 有 tool_calls',
                source: 'backend/app/services/solo/tools.py',
                children: [
                  { id: 't-kb',    label: 'search_knowledge_base', sub: 'Qdrant 向量召回',  role: 'storage' },
                  { id: 't-cat',   label: 'query_kb_catalog',       sub: '只查 Mongo 元数据', role: 'storage' },
                  { id: 't-web',   label: 'search_web',             sub: 'SerpAPI',          role: 'tool' },
                  { id: 't-wx',    label: 'get_weather',            sub: '高德 MCP',         role: 'tool' },
                  { id: 't-think', label: 'request_thinking',       sub: '工具化思考',        role: 'compute' },
                  {
                    id: 't-loop',
                    label: '↻ 回到 planner',
                    sub: '工具结果回灌 · 最多 16 轮',
                    role: 'decision',
                    desc: 'LangGraph conditional_edges：工具结果 append 到 messages，再进 planner 节点评估是否需要继续调工具。',
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
