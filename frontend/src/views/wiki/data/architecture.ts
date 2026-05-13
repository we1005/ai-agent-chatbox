import type { WikiPageData } from '../types'

// 系统全景：分 4 层（前端 / 后端 / 存储 / 外部）
const X = (col: number) => col * 320
const Y = (row: number) => row * 160

export const architecture: WikiPageData = {
  title: '系统架构 · 全景',
  caption: 'Vue 3 前端 ↔ FastAPI 后端 ↔ Mongo / Qdrant / LightRAG / mem0 · 外部 LLM × 4 + MCP × 1',
  intro:
    '从上到下分 4 层：前端组件层、后端服务层、本地持久化层、外部服务层。\n\n点击任一节点查看其在仓库中的入口文件。',
  nodes: [
    // ── 前端层（row 0）──
    { id: 'fe-chat', position: { x: X(0), y: Y(0) }, data: { role: 'user', label: 'ChatLayout', desc: '主聊天界面（shadcn-vue 外框）', sourceFile: 'frontend/src/components/ChatLayout.vue' } },
    { id: 'fe-config', position: { x: X(1), y: Y(0) }, data: { role: 'user', label: 'ConfigPanel', desc: 'Solo / 知识库 / 联网 / Reranker / Thinking 开关', sourceFile: 'frontend/src/components/ConfigPanel.vue' } },
    { id: 'fe-kb', position: { x: X(2), y: Y(0) }, data: { role: 'user', label: 'KnowledgeBase', desc: '上传 / 模型管理 / Graph 构建 / Agentic 档位', sourceFile: 'frontend/src/components/KnowledgeBase.vue' } },
    { id: 'fe-mem', position: { x: X(3), y: Y(0) }, data: { role: 'user', label: 'MemoryAudit', desc: '记忆审计页 · ADD/UPDATE/DELETE 历史', sourceFile: 'frontend/src/components/MemoryAudit.vue' } },
    { id: 'fe-ctx', position: { x: X(4), y: Y(0) }, data: { role: 'user', label: 'ContextViewer', desc: '当前 turn 的 7 层上下文可视化', sourceFile: 'frontend/src/components/ContextViewer.vue' } },

    // ── 后端服务层（row 1-2）──
    { id: 'be-api', position: { x: X(2), y: Y(1) }, data: { role: 'decision', label: 'FastAPI 路由', desc: '/api/chat/* /api/embedding/* /api/conversations/*', sourceFile: 'backend/main.py' } },
    { id: 'be-classic', position: { x: X(0), y: Y(2) }, data: { role: 'compute', label: 'chat_service', desc: 'Classic 主流水线', sourceFile: 'backend/app/services/chat_service.py' } },
    { id: 'be-solo', position: { x: X(1), y: Y(2) }, data: { role: 'compute', label: 'solo/graph', desc: 'LangGraph ReAct loop', sourceFile: 'backend/app/services/solo/graph.py' } },
    { id: 'be-agentic', position: { x: X(2), y: Y(2) }, data: { role: 'compute', label: 'agentic_rag', desc: 'grade / rewrite / hallucination check', sourceFile: 'backend/app/services/agentic_rag.py' } },
    { id: 'be-graph', position: { x: X(3), y: Y(2) }, data: { role: 'compute', label: 'graph_rag', desc: 'LightRAG 适配层（embed dim=1024）', sourceFile: 'backend/app/services/graph_rag.py' } },
    { id: 'be-mem', position: { x: X(4), y: Y(2) }, data: { role: 'compute', label: 'memory_service', desc: 'reflect_and_write + Mem0 judge', sourceFile: 'backend/app/services/memory_service.py' } },
    { id: 'be-router', position: { x: X(2), y: Y(3) }, data: { role: 'compute', label: 'context_router', desc: '7 层上下文 + Condenser pipeline', sourceFile: 'backend/app/services/context_router.py' } },

    // ── 存储层（row 4）──
    { id: 'st-mongo', position: { x: X(0), y: Y(4) }, data: { role: 'storage', label: 'MongoDB', desc: 'conversations / events / memories / tasks（双时间）', sourceFile: 'backend/app/db/database.py' } },
    { id: 'st-qdrant', position: { x: X(1), y: Y(4) }, data: { role: 'storage', label: 'Qdrant', desc: 'kb_main + mem0 集合 · BGE-M3 hybrid' } },
    { id: 'st-light', position: { x: X(2), y: Y(4) }, data: { role: 'storage', label: 'LightRAG 索引', desc: 'graphml + nano-vec · backend/data/lightrag/' } },
    { id: 'st-docs', position: { x: X(3), y: Y(4) }, data: { role: 'storage', label: '上传文档', desc: 'backend/data/uploads/（gitignore）' } },

    // ── 外部（row 5）──
    { id: 'ext-deepseek', position: { x: X(0), y: Y(5) }, data: { role: 'llm', label: 'DeepSeek', desc: '主 LLM · OpenAI SDK 兼容' } },
    { id: 'ext-kimi', position: { x: X(1), y: Y(5) }, data: { role: 'llm', label: 'Kimi (Moonshot)', desc: '备用 LLM' } },
    { id: 'ext-doubao', position: { x: X(2), y: Y(5) }, data: { role: 'llm', label: 'Doubao (Ark)', desc: '代码模型 · AsyncArk SDK' } },
    { id: 'ext-serp', position: { x: X(3), y: Y(5) }, data: { role: 'tool', label: 'SerpAPI', desc: 'web search · 评测时关闭' } },
    { id: 'ext-mcp', position: { x: X(4), y: Y(5) }, data: { role: 'tool', label: '高德 Weather MCP', desc: 'FastMCP SSE :8001 · 业务依赖' } },
  ],
  edges: [
    { id: 'fe1', source: 'fe-chat', target: 'be-api' },
    { id: 'fe2', source: 'fe-config', target: 'be-api' },
    { id: 'fe3', source: 'fe-kb', target: 'be-api' },
    { id: 'fe4', source: 'fe-mem', target: 'be-api' },
    { id: 'fe5', source: 'fe-ctx', target: 'be-api' },

    { id: 'be1', source: 'be-api', target: 'be-classic' },
    { id: 'be2', source: 'be-api', target: 'be-solo' },
    { id: 'be3', source: 'be-classic', target: 'be-agentic' },
    { id: 'be4', source: 'be-classic', target: 'be-graph' },
    { id: 'be5', source: 'be-classic', target: 'be-mem' },
    { id: 'be6', source: 'be-classic', target: 'be-router' },
    { id: 'be7', source: 'be-solo', target: 'be-router' },

    { id: 'st1', source: 'be-router', target: 'st-mongo' },
    { id: 'st2', source: 'be-mem', target: 'st-mongo' },
    { id: 'st3', source: 'be-mem', target: 'st-qdrant' },
    { id: 'st4', source: 'be-agentic', target: 'st-qdrant' },
    { id: 'st5', source: 'be-graph', target: 'st-light' },
    { id: 'st6', source: 'be-classic', target: 'st-docs' },

    { id: 'ext1', source: 'be-classic', target: 'ext-deepseek', strokeRole: 'llm' },
    { id: 'ext2', source: 'be-classic', target: 'ext-kimi', strokeRole: 'llm' },
    { id: 'ext3', source: 'be-classic', target: 'ext-doubao', strokeRole: 'llm' },
    { id: 'ext4', source: 'be-solo', target: 'ext-serp', strokeRole: 'tool' },
    { id: 'ext5', source: 'be-classic', target: 'ext-mcp', strokeRole: 'tool' },
    { id: 'ext6', source: 'be-solo', target: 'ext-mcp', strokeRole: 'tool' },
  ],
}
