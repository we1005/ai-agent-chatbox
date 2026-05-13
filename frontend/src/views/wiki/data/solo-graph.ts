import type { WikiPageData } from '../types'

// Solo LangGraph: classify_complexity → planner ⇄ tools 循环 → END
// 节点 + 循环箭头是这条页面的视觉重点
export const soloGraph: WikiPageData = {
  title: 'Solo Agent · LangGraph',
  caption: 'POST /api/chat/solo · ReAct 风格：planner ⇄ tools 循环到收敛 · recursion_limit=16',
  intro:
    'Solo 是项目的 agentic 路径。开启 Solo 后所有请求走 /api/chat/solo，模型强制切到 DeepSeek。\n\n5 个工具：search_knowledge_base / query_knowledge_base_catalog / search_web / get_weather / request_thinking。Embedding 未就绪时 search_knowledge_base 自动从工具列表剔除。',
  nodes: [
    {
      id: 'start',
      position: { x: 60, y: 260 },
      data: {
        role: 'user',
        label: 'START',
        desc: '前端 Solo ON · POST /api/chat/solo',
        sourceFile: 'backend/app/api/endpoints/solo.py',
      },
    },
    {
      id: 'classify',
      position: { x: 380, y: 260 },
      data: {
        role: 'decision',
        label: 'classify_complexity',
        desc: 'LLM 预判 query 复杂度 · 决定初始 system prompt 模板',
        sourceFile: 'backend/app/services/solo/graph.py',
      },
    },
    {
      id: 'planner',
      position: { x: 720, y: 260 },
      data: {
        role: 'llm',
        label: 'planner',
        desc: 'DeepSeek + tools schema · 返回 reasoning + (tool_calls | answer)',
        sourceFile: 'backend/app/services/solo/graph.py:planner_node',
        detail:
          '每轮看完整 message 历史，判断是否还需要调工具。tool_calls 非空 → 走 tools 节点；为空 → END 输出最终回答。',
      },
    },
    {
      id: 'tools',
      position: { x: 1440, y: 320 },
      data: {
        role: 'tool',
        label: 'tools',
        desc: '5 个工具：KB / KB catalog / web / weather / thinking',
        sourceFile: 'backend/app/services/solo/tools.py',
      },
    },
    {
      id: 'kb',
      position: { x: 1440, y: 40 },
      data: {
        role: 'storage',
        label: 'search_knowledge_base',
        desc: 'Qdrant 向量召回 · embedding 未就绪时自动 disable',
        sourceFile: 'backend/app/services/solo/tools.py',
      },
    },
    {
      id: 'web',
      position: { x: 1440, y: 180 },
      data: {
        role: 'tool',
        label: 'search_web',
        desc: 'SerpAPI · 评测时关闭（成本敏感）',
        sourceFile: 'backend/app/services/solo/tools.py',
      },
    },
    {
      id: 'weather',
      position: { x: 1440, y: 320 },
      data: {
        role: 'tool',
        label: 'get_weather',
        desc: '高德 MCP（FastMCP SSE）· 与 classic 共享',
      },
    },
    {
      id: 'thinking',
      position: { x: 1440, y: 460 },
      data: {
        role: 'compute',
        label: 'request_thinking',
        desc: '"工具化"的思考动作 · planner 主动调用以攒推理深度',
      },
    },
    {
      id: 'end',
      position: { x: 1820, y: 260 },
      data: {
        role: 'done',
        label: 'END',
        desc: 'tool_calls 为空 → 流式输出 final answer · SSE',
        sourceFile: 'backend/app/api/endpoints/solo.py',
      },
    },
    // 循环注解：悬在 planner ↔ tools 中间下方，视觉上强化这是一个 cycle
    {
      id: 'loop-note',
      position: { x: 820, y: 640 },
      data: {
        role: 'decision',
        label: '⟲ ReAct 循环',
        desc: '每轮 planner 看完整消息历史 · 有 tool_calls 就继续调 · 无则收敛到 END · recursion_limit=16',
        detail:
          'LangGraph 的 conditional_edges：planner 节点每次返回后走 should_continue()，若 tool_calls 非空则 → tools 节点执行工具、把结果 append 回 messages，再回到 planner；直到某一轮 planner 直接给出纯文本答案。\n\nrecursion_limit=16 是硬防线：极端情况下（LLM 卡在重复调工具）最多走 16 次 planner→tools→planner 就强制退出。',
      },
    },
  ],
  edges: [
    { id: 'e1', source: 'start', target: 'classify' },
    { id: 'e2', source: 'classify', target: 'planner' },
    { id: 'e3', source: 'planner', target: 'tools', label: '① tool_calls 非空' },
    { id: 'e4', source: 'planner', target: 'end', label: 'tool_calls 为空' },
    { id: 'e5a', source: 'tools', target: 'kb' },
    { id: 'e5b', source: 'tools', target: 'web' },
    { id: 'e5c', source: 'tools', target: 'weather' },
    { id: 'e5d', source: 'tools', target: 'thinking' },
    // 核心回边：走底部 handles 形成清晰的 U 型 loop（强调样式：粗虚线 + amber 色 + 大箭头）
    {
      id: 'e6',
      source: 'tools',
      target: 'planner',
      sourceHandle: 'bottom',
      targetHandle: 'top',
      label: '② 工具结果回灌 · 回到 planner（最多 16 轮）',
      strokeRole: 'decision',
      type: 'smoothstep',
      emphasize: true,
    },
  ],
}
