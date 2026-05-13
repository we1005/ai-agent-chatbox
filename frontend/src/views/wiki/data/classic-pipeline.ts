import type { WikiPageData } from '../types'

// Classic chat 流水线（POST /api/chat/completions）
// 节点布局采用横向 swim-lane：上行主链路，下方两个分支（weather 短路 / code+thinking）
const X = (col: number) => col * 320
const Y = (row: number) => row * 170

export const classicPipeline: WikiPageData = {
  title: 'Classic 聊天流水线',
  caption:
    '/api/chat/completions · 端点层 intent 识别 → 三向分流（weather 短路 / code+thinking 保留 / general 主链路）',
  intro:
    'Classic 路径是项目的"线性可读"主线：意图识别提到端点层后，一目了然地分出三条岔路。\n\n绿色主链路覆盖大多数 query：上下文重建 → 记忆路由 → 4 路 KB 召回 → 上下文装配 → LLM 流式 → XML 解析 → SSE → 后台反思。',
  nodes: [
    {
      id: 'q',
      position: { x: X(0), y: Y(2) },
      data: {
        role: 'user',
        label: '用户 Query',
        desc: '前端 SSE POST /api/chat/completions',
        sourceFile: 'frontend/src/store/chat.ts',
      },
    },
    {
      id: 'intent',
      position: { x: X(1), y: Y(2) },
      data: {
        role: 'decision',
        label: 'detect_intent',
        desc: 'DeepSeek JSON-mode 三分类：code / weather / general（带 city 抽取）',
        sourceFile: 'backend/app/services/intent_service.py',
        detail:
          '提到 chat.py 端点层：weather/thinking/general 都先识别一次意图，避免 enable_thinking 路径绕过 weather MCP。识别失败软降级 general。',
      },
    },
    {
      id: 'weather',
      position: { x: X(2), y: Y(0) },
      data: {
        role: 'tool',
        label: 'Weather MCP 短路',
        desc: '高德 MCP（FastMCP SSE :8001）· thinking on/off 都走这里',
        sourceFile: 'backend/app/services/chat_service.py:_handle_weather_query',
      },
    },
    {
      id: 'thinking',
      position: { x: X(2), y: Y(1) },
      data: {
        role: 'llm',
        label: 'DeepSeek thinking',
        desc: 'enable_thinking + deepseek 模型：保 thinking，沉默地不切 Doubao',
        sourceFile: 'backend/app/services/chat_service.py:chat_stream_with_thinking',
        detail:
          'code 意图 + thinking 时不切 Doubao 代码模型（Doubao 不支持 thinking）。语义决定优先级：尊重用户的 thinking 选择。LangSmith metadata 标 doubao_skipped_due_to_thinking=true 可追踪。',
      },
    },
    {
      id: 'ctx',
      position: { x: X(2), y: Y(2) },
      data: {
        role: 'compute',
        label: 'Context Rebuild',
        desc: 'events → context_router → 7 层 → Condenser pipeline',
        sourceFile: 'backend/app/services/context_router.py',
        planDoc: 'plan-doc-dir/长上下文机制设计v2·集百家之长.md',
      },
    },
    {
      id: 'mem-router',
      position: { x: X(3), y: Y(2) },
      data: {
        role: 'decision',
        label: 'Memory Router',
        desc: '决定是否注入 user memory（debounce + relevance）',
        sourceFile: 'backend/app/services/memory_service.py',
      },
    },
    {
      id: 'kb',
      position: { x: X(4), y: Y(2) },
      data: {
        role: 'decision',
        label: 'KB 策略路由',
        desc: '4 路：classical / multi_query / agentic / graph',
        sourceFile: 'backend/app/services/chat_service.py:chat_stream',
        detail:
          '优先级：graph_rag > agentic > multi_query > classical。graph_rag 启用时 hallucination_check 跳过；agentic 与启发式 rewrite 互斥。',
      },
    },
    {
      id: 'kb-graph',
      position: { x: X(5), y: Y(0) },
      data: {
        role: 'storage',
        label: 'LightRAG (Graph RAG)',
        desc: 'naive / local / global / hybrid / mix · graphml + nano-vec',
        sourceFile: 'backend/app/services/graph_rag.py',
      },
    },
    {
      id: 'kb-agent',
      position: { x: X(5), y: Y(1) },
      data: {
        role: 'compute',
        label: 'Agentic RAG',
        desc: 'grade → rewrite → retrieve → hallucination_check（4 档 off/grading/rewrite/full）',
        sourceFile: 'backend/app/services/agentic_rag.py',
      },
    },
    {
      id: 'kb-classic',
      position: { x: X(5), y: Y(2) },
      data: {
        role: 'storage',
        label: 'Qdrant 向量召回',
        desc: 'BGE-M3 dense + sparse hybrid（可降级 dense-only）',
        sourceFile: 'backend/app/services/vector_store/qdrant_backend.py',
      },
    },
    {
      id: 'kb-mq',
      position: { x: X(5), y: Y(3) },
      data: {
        role: 'compute',
        label: 'Multi-Query',
        desc: 'LLM 重写 query 为 N 条 → 并行召回 → fusion',
        sourceFile: 'backend/app/services/chat_service.py',
      },
    },
    {
      id: 'assembler',
      position: { x: X(6), y: Y(2) },
      data: {
        role: 'compute',
        label: 'Context Assembler',
        desc: '按文件分组 <document index=N>，jinja2 转义防注入',
        sourceFile: 'backend/app/prompts/chat_query.j2',
      },
    },
    {
      id: 'llm',
      position: { x: X(7), y: Y(2) },
      data: {
        role: 'llm',
        label: 'LLM Stream',
        desc: 'DeepSeek / Kimi / Doubao · @traceable LangSmith',
        sourceFile: 'backend/app/services/_langsmith.py',
      },
    },
    {
      id: 'xml',
      position: { x: X(8), y: Y(2) },
      data: {
        role: 'compute',
        label: 'XML Parse',
        desc: 'sloppy-xml → 正则 → 纯文本 三级降级；refs 持久化',
        sourceFile: 'backend/app/services/xml_parser.py',
      },
    },
    {
      id: 'sse',
      position: { x: X(9), y: Y(2) },
      data: {
        role: 'output',
        label: 'SSE Stream',
        desc: 'data: {content/parsed/title_update/[DONE]}',
        sourceFile: 'backend/app/api/endpoints/chat.py:event_generator',
      },
    },
    {
      id: 'reflect',
      position: { x: X(9), y: Y(3) },
      data: {
        role: 'storage',
        label: '后台反思',
        desc: 'fire-and-forget · reflect_and_write · Mem0 judge',
        sourceFile: 'backend/app/services/memory_service.py:reflect_and_write',
        planDoc: 'analysis-for-backend/context-engine.md',
      },
    },
  ],
  edges: [
    { id: 'e1', source: 'q', target: 'intent', label: 'msg_dicts' },
    { id: 'e2a', source: 'intent', target: 'weather', label: 'weather' },
    { id: 'e2b', source: 'intent', target: 'thinking', label: 'code+thinking' },
    { id: 'e2c', source: 'intent', target: 'ctx', label: 'general' },
    { id: 'e3', source: 'ctx', target: 'mem-router' },
    { id: 'e4', source: 'mem-router', target: 'kb' },
    { id: 'e5a', source: 'kb', target: 'kb-graph', label: 'graph_rag' },
    { id: 'e5b', source: 'kb', target: 'kb-agent', label: 'agentic' },
    { id: 'e5c', source: 'kb', target: 'kb-classic', label: 'classical' },
    { id: 'e5d', source: 'kb', target: 'kb-mq', label: 'multi_query' },
    { id: 'e6a', source: 'kb-graph', target: 'assembler' },
    { id: 'e6b', source: 'kb-agent', target: 'assembler' },
    { id: 'e6c', source: 'kb-classic', target: 'assembler' },
    { id: 'e6d', source: 'kb-mq', target: 'assembler' },
    { id: 'e7', source: 'assembler', target: 'llm' },
    { id: 'e7b', source: 'thinking', target: 'xml', label: '直接 → XML' },
    { id: 'e7c', source: 'weather', target: 'sse', label: '直接 → SSE' },
    { id: 'e8', source: 'llm', target: 'xml' },
    { id: 'e9', source: 'xml', target: 'sse' },
    { id: 'e10', source: 'sse', target: 'reflect', label: 'turn 结束', strokeRole: 'storage' },
  ],
}
