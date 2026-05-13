import type { TreeModule } from './types'

export const classicPipelineTree: TreeModule = {
  key: 'classic-pipeline',
  title: 'Classic 聊天流水线',
  caption: '/api/chat/completions · 端点层 intent 识别 → 三向分流',
  note: '4 路 RAG 最终合流到 Assembler；图中每条分支以"→ Assembler"作为叶节点。合流后的线性链路见 general 分支下。',
  wikiLink: '/wiki/classic-pipeline',
  root: {
    id: 'q',
    label: 'User Query',
    sub: '前端 SSE POST',
    role: 'user',
    source: 'frontend/src/store/chat.ts',
    children: [
      {
        id: 'intent',
        label: 'detect_intent',
        sub: 'DeepSeek JSON-mode 三分类',
        role: 'decision',
        source: 'backend/app/services/intent_service.py',
        children: [
          {
            id: 'weather',
            label: 'weather',
            sub: '短路 · 不过 RAG',
            role: 'tool',
            edgeLabel: 'weather',
            children: [
              {
                id: 'w-mcp',
                label: 'Weather MCP',
                sub: '高德 · FastMCP SSE',
                role: 'tool',
                children: [{ id: 'w-sse', label: 'SSE Stream', sub: '直接输出', role: 'output' }],
              },
            ],
          },
          {
            id: 'thinking',
            label: 'code + thinking',
            sub: '保 thinking 走 DeepSeek',
            role: 'llm',
            edgeLabel: 'code+thinking',
            source: 'backend/app/services/chat_service.py:chat_stream_with_thinking',
            children: [
              {
                id: 'th-llm',
                label: 'DeepSeek thinking',
                role: 'llm',
                children: [
                  {
                    id: 'th-xml',
                    label: 'XML Parse',
                    role: 'compute',
                    children: [{ id: 'th-sse', label: 'SSE Stream', role: 'output' }],
                  },
                ],
              },
            ],
          },
          {
            id: 'general',
            label: 'general',
            sub: '主链路',
            role: 'decision',
            edgeLabel: 'general',
            children: [
              {
                id: 'ctx',
                label: 'Context Rebuild',
                sub: '7 层 + Condenser',
                role: 'compute',
                source: 'backend/app/services/context_router.py',
                link: '/wiki/context-engine',
                children: [
                  {
                    id: 'memrouter',
                    label: 'Memory Router',
                    sub: 'debounce + relevance',
                    role: 'decision',
                    source: 'backend/app/services/memory_service.py',
                    children: [
                      {
                        id: 'kb',
                        label: 'KB Strategy',
                        sub: '4 路按 config 路由',
                        role: 'decision',
                        children: [
                          { id: 'kb-cl',  label: 'classical',   sub: 'BGE-M3 hybrid',       role: 'storage', children: [{ id: 'kb-cl-a',  label: '→ Assembler', role: 'compute' }] },
                          { id: 'kb-mq',  label: 'multi_query', sub: 'LLM 改写 × N + RRF',  role: 'compute', children: [{ id: 'kb-mq-a',  label: '→ Assembler', role: 'compute' }] },
                          { id: 'kb-ag',  label: 'agentic',     sub: '4 档 off/grade/rw/full', role: 'compute', link: '/wiki/rag-strategies', children: [{ id: 'kb-ag-a',  label: '→ Assembler', role: 'compute' }] },
                          { id: 'kb-gr',  label: 'graph',       sub: 'LightRAG 5 mode',     role: 'storage', children: [{ id: 'kb-gr-a',  label: '→ Assembler', role: 'compute' }] },
                        ],
                      },
                      {
                        id: 'main',
                        label: '合流 · 主链路',
                        sub: 'Assembler → LLM → SSE',
                        role: 'compute',
                        desc: '4 路 RAG 的输出在此汇合，进入线性后处理。',
                        children: [
                          {
                            id: 'assembler',
                            label: 'Assembler',
                            sub: 'jinja2 · XML 转义',
                            role: 'compute',
                            source: 'backend/app/prompts/chat_query.j2',
                            children: [
                              {
                                id: 'llm',
                                label: 'LLM Stream',
                                sub: 'DeepSeek / Kimi / Doubao',
                                role: 'llm',
                                children: [
                                  {
                                    id: 'xml',
                                    label: 'XML Parse',
                                    sub: 'sloppy-xml → regex → text',
                                    role: 'compute',
                                    source: 'backend/app/services/xml_parser.py',
                                    children: [
                                      {
                                        id: 'sse',
                                        label: 'SSE Stream',
                                        sub: 'data: {content/parsed/[DONE]}',
                                        role: 'output',
                                        children: [
                                          { id: 'reflect', label: 'reflect_and_write', sub: '后台反思 · fire-and-forget', role: 'storage', link: '/wiki/memory-lifecycle' },
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
            ],
          },
        ],
      },
    ],
  },
}
