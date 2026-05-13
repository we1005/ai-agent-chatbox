<div align="center">

# 玄鉴 · Xuanjian

### *The Deep Mirror — A reflective companion for knowledge*

> *"知识不应沉默于索引，而该在对话中被映照。"*

### [🌐 Live Demo · agent-deep-mirror.netlify.app](https://agent-deep-mirror.netlify.app/)

[![Netlify Status](https://img.shields.io/badge/Netlify-deployed-00C7B7?style=flat-square&logo=netlify&logoColor=white)](https://agent-deep-mirror.netlify.app/)
[![Live Demo](https://img.shields.io/badge/🌐_Live-agent--deep--mirror.netlify.app-10B981?style=flat-square)](https://agent-deep-mirror.netlify.app/)

[![Vue 3](https://img.shields.io/badge/Vue-3.5-4FC08D?style=flat-square&logo=vue.js&logoColor=white)](https://vuejs.org/)
[![TypeScript](https://img.shields.io/badge/TypeScript-5.x-3178C6?style=flat-square&logo=typescript&logoColor=white)](https://www.typescriptlang.org/)
[![Tailwind v4](https://img.shields.io/badge/Tailwind-v4-06B6D4?style=flat-square&logo=tailwindcss&logoColor=white)](https://tailwindcss.com/)
[![Vite](https://img.shields.io/badge/Vite-8-646CFF?style=flat-square&logo=vite&logoColor=white)](https://vitejs.dev/)
[![Vue Flow](https://img.shields.io/badge/Vue%20Flow-1.4-FF5C8D?style=flat-square)](https://vueflow.dev/)
&nbsp;
[![Python](https://img.shields.io/badge/Python-3.13-3776AB?style=flat-square&logo=python&logoColor=white)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115-009688?style=flat-square&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![LangChain](https://img.shields.io/badge/LangChain-1.x-1C3C3C?style=flat-square&logo=langchain&logoColor=white)](https://www.langchain.com/)
[![LangGraph](https://img.shields.io/badge/LangGraph-ReAct-1C3C3C?style=flat-square)](https://github.com/langchain-ai/langgraph)
&nbsp;
[![MongoDB](https://img.shields.io/badge/MongoDB-8.x-47A248?style=flat-square&logo=mongodb&logoColor=white)](https://www.mongodb.com/)
[![Qdrant](https://img.shields.io/badge/Qdrant-1.12+-DC244C?style=flat-square)](https://qdrant.tech/)
[![LightRAG](https://img.shields.io/badge/LightRAG-Graph-FFA500?style=flat-square)](https://github.com/HKUDS/LightRAG)
[![Mem0](https://img.shields.io/badge/Mem0-Bi--Temporal-7C3AED?style=flat-square)](https://mem0.ai/)
[![BGE-M3](https://img.shields.io/badge/BGE--M3-Hybrid-FF6B35?style=flat-square)](https://huggingface.co/BAAI/bge-m3)
&nbsp;
[![Redis](https://img.shields.io/badge/Redis-AOF-DC382D?style=flat-square&logo=redis&logoColor=white)](https://redis.io/)
[![Celery](https://img.shields.io/badge/Celery-5.3-37814A?style=flat-square&logo=celery&logoColor=white)](https://docs.celeryq.dev/)
[![Flower](https://img.shields.io/badge/Flower-monitor-EC407A?style=flat-square)](https://flower.readthedocs.io/)
[![Docker](https://img.shields.io/badge/Docker-compose-2496ED?style=flat-square&logo=docker&logoColor=white)](https://www.docker.com/)

</div>

---

**玄鉴**（Xuánjiàn）取「玄」之幽深以容知识黑盒，藉「鉴」之映照以勘验思辨。

一个**会反思的知识伙伴** —— 融 RAG 四路召回、LangGraph Agent、七层上下文工程与双时间记忆于一体。基于 **FastAPI** + **Vue 3** 构建。

### 🚪 入口

> 🌍 **公网可直接访问落地页**：<https://agent-deep-mirror.netlify.app/>
> 其它子路由（`/`、`/wiki` 等）仅在本地自部署版本里工作（需要后端 + MongoDB + Qdrant）。

| 路由 | 公网 | 本地 | 内容 |
|---|---|---|---|
| `/home` 🏠 | [🌐 Live](https://agent-deep-mirror.netlify.app/) | [local](http://localhost:5173/home) | **视觉门脸** · Apple 风格落地页（毛玻璃 · 大字排版 · 水墨意象） |
| `/` 💬 | — | [local](http://localhost:5173/) | **主聊天** · ChatGPT 式一体化输入框（模型/Solo/设置 三图标 + Fuse.js 模糊会话搜索） |
| `/wiki` 🗺️ | — | [local](http://localhost:5173/wiki) | **技术手册** · Vue Flow 可拖拽节点图（7 子页 · 液态玻璃首页） |
| `/wiki-tree` 🌿 | — | [local](http://localhost:5173/wiki-tree) | **树状视图** · 同 6 个流程的纵向有向树（顶部 Tab 切换 · SVG 渲染） |

> 💡 想知道公网版是怎么部署的？见 [`netify部署流程.md`](./netify部署流程.md)（形态 B · 仅 /home 独立打包，bundle 从 2.96MB → 147KB）。

### 🎯 核心能力

- 🤖 **多模型路由** — Kimi · DeepSeek · Doubao（代码）· 三分类意图识别 + 自动切模型
- 🔍 **混合检索** — Qdrant dense + learned sparse + RRF 融合（BGE-M3 一次前向出双通道）
- 🧠 **Solo Agent** — LangGraph ReAct 循环（5 工具自主调度 · recursion_limit=16）
- 📚 **七层上下文** — Identity → Recent → Summary → Memory → Retrieval → Runtime → View
- ⚖️ **双时间记忆** — Mem0 ADD/UPDATE/DELETE/NOOP judge + Zep schema（valid_at / invalidated_at / superseded_by）
- 🌐 **天气 MCP** — 高德 FastMCP SSE · 同名多地并行查询
- 📊 **真实评测** — CRUD-mini 60 query × 10 配置 · RAGAS DeepSeek judge · 0.970 peak Recall@K
- 🚀 **Celery 异步队列**（可选）— Redis AOF 持久化 + Docker worker（~100MB）· concurrency 阀门削峰填谷 · Flower 监控

### 📑 目录

- [✨ 主要功能](#-主要功能) · [📊 代码规模](#-代码规模) · [🛠️ 技术栈](#️-技术栈)
- [🚀 快速开始](#-快速开始) · [📂 项目结构](#-项目结构) · [🔧 Prompt 架构](#-prompt-架构说明)
- [📡 API 端点](#-主要-api-端点) · [🗺️ 开发路线图](#️-开发路线图) · [📝 注意事项](#-注意事项)

---

## ✨ 主要功能

### 🏠 /home 落地页（Apple 风格视觉门脸）

> 🌐 **公网直达**：<https://agent-deep-mirror.netlify.app/>（Netlify 独立部署 · 仅 /home · bundle 147KB）
> 本地入口：侧栏底部 **🏠 首页 · 玄鉴** · 路由：[`/home`](http://localhost:5173/home)
> 部署流程：[`netify部署流程.md`](./netify部署流程.md)

单页纵向 8 section 落地页，给第一次来访的人一个有语境的入口：

- **Hero**：品牌大字 + 浮动装饰汉字（知·鉴·忆）+ 朱砂 / 墨色渐变 · 纯 SVG 水墨飞白背景
- **Philosophy**：题跋式中文引言（霞鹜文楷）+ 朱砂印章「博观约取」+ 纯 SVG 三重远山意象
- **Features**：4 张毛玻璃大卡，点击直达对应 Wiki 子页（Classic RAG / Solo / Context Engine / Graph × Memory）
- **Stats**：6 组关键指标数字 count-up（60 query · 10 RAG 配置 · 7 层上下文 · 4 LLM · 5 Agent 工具 · 0.970 Recall@K）
- **ArchPreview** · **TechStack marquee** · **Footer**（"博观而约取 · 厚积而薄发" — 苏轼）
- 字体栈：Noto Serif SC（中文古韵）+ LXGW 霞鹜文楷（题跋感）+ Inter Variable（英文）
- 全 Apple 风格视觉语言：米白 canvas · 毛玻璃 `backdrop-filter: blur(20px)` · 220ms hover lift · 尊重 `prefers-reduced-motion`

### 🗺️ 项目 Wiki（可视化架构页）

> 入口：侧栏底部 **📚 项目 Wiki** · 路由：[`/wiki`](http://localhost:5173/wiki)

把 6 个月后回来读代码的"考古"成本降到 5 分钟。基于 [Vue Flow](https://vueflow.dev/) 的 7 个可拖拽 / 可缩放 / 流动边动画的子页面：

| 路由 | 内容 |
|---|---|
| `/wiki/architecture` | 全栈架构：前端 ↔ FastAPI ↔ Mongo / Qdrant / LightRAG / Mem0 / MCP / 4 个 LLM |
| `/wiki/classic-pipeline` | Classic 聊天流水线：意图识别 → 三向分流（weather / thinking / general）→ 4 路 KB → 装配 → LLM → XML → SSE → 后台反思 |
| `/wiki/solo-graph` | Solo LangGraph：classify_complexity → planner ⇄ tools 循环（recursion_limit=16）|
| `/wiki/context-engine` | Context Engine v2 七层模型 + Condenser Pipeline（OpenHands 算法） |
| `/wiki/memory-lifecycle` | reflect_and_write 全流程 + Mem0 ADD/UPDATE/DELETE/NOOP judge + 双时间 schema |
| `/wiki/rag-strategies` | 5 主策略（off / multi_query / agentic / graph / classical）+ Graph 5 子模式 + Agentic 4 档 |
| `/wiki/bench-results` | CRUD-mini 真实评测数据：vue-echarts 雷达 / 柱状 / 延迟折线 / 原始数据表 |

**设计要点**：
- 节点按 8 种角色统一配色（用户 sky / 决策 amber / LLM violet / 工具 emerald / 存储 slate / 计算 fuchsia / 输出 rose / 完成 green），跨页面视觉语言一致
- 数据驱动：架构调整时只改 `frontend/src/views/wiki/data/*.ts`，UI 模板 0 修改
- 每个节点点击展开右侧详情：角色 / 长说明 / 关联代码文件路径 / 设计文档链接
- 仅 BenchResults 页用 vue-echarts，其他页面统一 Vue Flow（包体最优）

---

### 🤖 Solo 模式（Agentic ReAct · LangGraph）

> 📖 详细架构见 [`analysis-for-backend/solo-module.md`](analysis-for-backend/solo-module.md)

**一句话**：前端顶栏「Solo」打开 → 请求走 `/api/chat/solo` → LangGraph 接管 → Agent 自主决定调哪些工具。Classic 路径完全不感知，零影响。

**5 个 Agent 工具**：

| 工具 | 用途 |
|---|---|
| `search_knowledge_base` | Qdrant 向量召回（Embedding 未就绪自动 disable）|
| `query_knowledge_base_catalog` | 只查 Mongo 元数据 · 始终可用 |
| `search_web` | SerpAPI 联网 |
| `get_weather` | 高德 MCP · 与 classic 共享 |
| `request_thinking` | "工具化"思考 · planner 主动调用攒推理深度 |

<details>
<summary>📋 详细行为（点击展开）</summary>

- **自动切 DeepSeek**：开启 Solo 时若当前模型不是 DeepSeek，自动切换到 `deepseek-chat`（Kimi 的 function calling 稳定性不足），顶部 toast 告知
- **复杂度自动识别**：图入口处 `classify_complexity_node`（DeepSeek JSON-mode，~300ms）判定复杂度；复杂问题自动启用 DeepSeek 原生思考模式（`extra_body={"thinking":{"type":"enabled"}}`），`reasoning_content` 流式展示
- **工具网关**：Embedding 模型未加载时 `search_knowledge_base` 从 LLM 候选工具中剔除 + prompt 追加"RAG 不可用"提示，避免幻觉
- **工具优先级与去重**：system prompt 明确"天气 → `get_weather` 权威，不要 search_web 交叉验证"等规则；同一工具单次对话最多 2 次
- **思考链可视化**：前端 `<AgentTrace>` 组件展示"已识别需求 → 已规划任务 → 已调用工具 X → 完成回答"四阶段折叠面板，每次工具调用可展开看 args + result_preview
- **幻觉兜底**：planner 发现"只说不调工具"时触发 nudge，提供"一字不改的 refuse template"作为合法拒绝路径
- **会话一致性**：切换会话 / 清空 / 删除时自动中止 in-flight SSE（`_abortInFlight`），避免 token 污染新会话

</details>

---

### 💬 对话核心

- 🤖 **多模型** — 无缝切换 Kimi (Moonshot AI) 与 DeepSeek
- 🧭 **三分类意图识别路由** — 每轮先做一次 DeepSeek JSON 调用：
  - `code` → 自动切到 `doubao-seed-2-0-code-preview-260215`
  - `weather` → 走天气短路路径，跳过 RAG / 联网搜索
  - `general` → 走 RAG / 联网搜索标准路径
- 🌤️ **实时天气** — 高德天气 MCP；同步抽取城市名；同名多地（如"朝阳"自动查北京/长春/辽宁所有朝阳区市）并行返回
- ⚡ **流式响应** — SSE 打字机效果
- ⏹ **停止 / 重新生成** — 任意时刻中止；对最后一条助手回复一键重新生成
- 🪄 **智能标题** — LLM 自动生成中文摘要标题（≤10 字）
- 💭 **推荐追问** — 每条回答底部 2 条相关追问气泡

---

### 🚀 Celery 异步向量化队列（默认关闭）

> 📖 架构决策见 [`analysis-for-backend/celery-module.md`](analysis-for-backend/celery-module.md)
> 📘 运维手册见 [`backend/CELERY.md`](backend/CELERY.md)
>
> ⚠️ 默认 **off** —— 开关在 `/admin/infra`；关闭时完全等同于此特性不存在。

**一句话**：上传知识库文档走 Redis 持久化队列，Docker worker 按 `concurrency=2` 消费，削峰填谷。

**关键架构决策**：**Worker 不加载 BGE-M3**，只做 HTTP 转发到 backend 内部端点。

```
upload → backend → task.delay(file_id) → Redis queue
                                              ↓
                                    Celery Worker (~100MB Docker)
                                    concurrency=2 ← 水龙头开度
                                              ↓
                              HTTP POST /api/internal/vectorize
                                              ↓
                            backend 的 _do_vectorize_sync()
                              BGE-M3 仅主进程加载一份
```

<details>
<summary><b>📋 细节</b>（点击展开）</summary>

- **削峰阀门** = worker `--concurrency=2`（`backend/docker-compose.celery.yml`）· 调成 1 更保守
- **Worker 容器 ~100MB**（不装 torch / BGE-M3）· 启动秒级
- **Redis AOF 持久化** = `bash backend/start-redis-with-aof.sh` 一键开启；备份原 conf → 追加 AOF → `brew services restart redis` → 验证
- **Flower 监控** :5555（`admin/xuanjian`）· 任务历史 / 失败重试 / worker 状态
- **健康检查** `/api/embedding/celery/health` → 前端 `/admin/infra` 三张卡实时显示
- **开启前预检** `PUT /api/embedding/celery` 先查 Redis ping + Celery inspect + Flower HTTP；任一失败 503 + 详情 + 不持久化
- **重启恢复** backend 重启时查 Celery inspect active/reserved/scheduled，已在跑的任务不重复入队
- **/api/internal/* 中间件** 拒绝非本机 IP（127.0.0.1 / 172.x / 192.168.x / 10.x 白名单）
- **完全兼容** — 关闭时走原 `asyncio.create_task(_vectorize_document)` 零破坏
- **autoretry** `RequestException` 指数退避 × 3 次

</details>

---

### 🧠 Context Engine v2（长对话记忆 · 默认关闭）

> 📖 完整架构见 [`analysis-for-backend/context-engine.md`](analysis-for-backend/context-engine.md)
> 🎨 设计与开源选型过程见 [`plan-doc-dir/长上下文机制设计v2·集百家之长.md`](plan-doc-dir/长上下文机制设计v2·集百家之长.md)
>
> ⚠️ 所有开关默认 **off**，按里程碑顺序独立翻启避免一次性放大面。

**七层模型**：

```
L1 Identity → L2 Recent → L3 Summary → L4 Memory → L5 Retrieval → L6 Runtime → L7 View
```

**六大支柱**（点击展开看实现细节）：

<details>
<summary><b>① Event Stream 作真相源</b> · Mongo events 集合 9 种 EventKind</summary>

- 所有对话事件（user_msg / assistant_msg / tool_call / tool_result / rag_retrieval / web_search / **summary** / **memory_flush** / **intent_routed**）统一进 Mongo `events` 集合
- `Conversation.messages[]` 嵌入数组保留作兼容层
- `CHAT_REBUILD_HISTORY_FROM_EVENTS=true`（默认开）时服务端按 `conversation_id` 从 events 重建历史，忽略前端 `request.messages[:-1]` —— **上下文主权回到后端**

</details>

<details>
<summary><b>② Condenser Pipeline</b> · OpenHands 递归 Summary + Recent Buffer + Tool Output 三件套（CONTEXT_ENGINE_ENABLED=true）</summary>

- **RecentBufferCondenser**：最近 N 轮（默认 5）user turn 的全部 events 原样保留；summary/memory_flush 等受保护 kind 不受 cutoff 影响
- **LLMSummarizingCondenser**（OpenHands 算法移植）：events 数超 `max_size=20` 触发 → head(`keep_first=1`) + 前一次摘要 + tail(`max_size//2`) → DeepSeek 生成**递归 rolling summary**；新 summary 作为 `kind="summary"` event 回写 Mongo，下一轮自动成为 prev_summary 输入
- **ToolOutputCondenser**：工具返回 > 2000 字时 head(500)+tail(500)+error-regex 裁剪；可选 LLM 200 字摘要 + sha1 缓存同输入不重算；原文永远存 `metadata.raw_content` 审计

</details>

<details>
<summary><b>③ Durable Memory</b> · Mem0 ADD/UPDATE/DELETE/NOOP judge + Zep 双时间 schema（MEMORY_REFLECT_ENABLED=true）</summary>

- turn 结束后 `asyncio.create_task` 后台反思：每 **3 轮 debounce** 一次，拉最近对话段交给 mem0 做 extract → LLM judge（`deepseek-chat` + 本地 BGE-M3 + Qdrant `mem0` 独立 collection，不污染 `kb_main`）
- 每次 mem0 操作同步镜像到 Mongo `memories` collection，采 **Zep 双时间 schema**：`valid_at` / `invalidated_at` / `superseded_by` —— 事实永不物理删，永远可溯源
- `MEMORY_RETRIEVAL_ENABLED=true` 时 Context Router 规则层命中代词 / 回指 / 自指 query 触发 top-K memory 查询；hits 以 system message 注入 View

</details>

<details>
<summary><b>④ Context Router + Assembler</b> · 7 维决策 + TokenBudget 优先级装配（P4）</summary>

- `route_context()` 把散乱的 4 个 kb 开关 + memory + web 汇总成单一 `InjectionPlan`（7 维决策）
- `assemble_messages()` 按 `TokenBudget` 的 priority 表（system=0 最优先保 ... web=10 最先丢）累加装配
- 超 `input_cap` 丢低优先级 block，输出 `AssembledMessages` 含 `dropped_blocks / included_blocks / cap_utilization` trace

</details>

<details>
<summary><b>⑤ Task Context 隔离</b> · Solo 路径复杂任务隔离（P5）</summary>

- Mongo `tasks` collection + `TaskContext` Document
- Solo 路径请求进入时 `ensure_task(task_id=conversation_id, goal=first_user_query)`，完成后 `finish_task(status="completed"|"failed")`
- 未来 Solo 子图可仅加载 TaskContext + 最小对话锚点，避免复杂任务污染普通对话记忆

</details>

<details>
<summary><b>⑥ 前端可见性 + 可观测性 + Fail-Soft</b></summary>

- **`/settings/memory`** 审计页（`MemoryAudit.vue`）：列出 durable memory，可编辑 / 软删（打 `invalidated_at`）；含失效高亮 + include_invalidated 开关
- **Context Viewer 抽屉**（`ContextViewer.vue`）：当前会话的 recent events 预览 / rolling summary / memory hits 三段，含"去 memory 审计页"深链
- **@pin 语法解析器**（`pin_parser.ts`）：`@kb:filename` / `@memory:topic` / `@last-turn` / `@reset` —— 客户端纯解析
- **可观测性**：15+ LangSmith metadata 字段覆盖 compaction / summary drift / memory hits / router path / tool prune
- **全链路 fail-soft**：任何 condenser / mem0 / router 节点异常都只 `logger.warning`，自动 fallback 到上一级 / classical，**绝不 raise**

</details>

---

### 📚 知识库 (RAG)

**支持格式**：PDF · Markdown · Word (.docx) · 纯文本 · CSV · Excel (.xlsx/.xls) · PowerPoint (.pptx) · EPUB

**核心特性**：

- 📥 **异步向量化** — 上传立即返回，后台 `asyncio.to_thread` 完成向量化；服务重启自动将 `processing` 状态重置为 `pending` 并重跑
- 🗄️ **三方一致** — 元数据在 Mongo（`KnowledgeDocument`），向量在 Qdrant（`kb_main`），原文在磁盘；删除操作保证三方一致
- 🔍 **Qdrant 原生混合检索** — dense (1024d Cosine) + learned sparse（IDF modifier）双通道命名向量，BGE-M3 一次前向出双结果 + 服务端 RRF 融合
- 🎯 **Reranker 动态加载** — `/knowledge` 页一键开关；开启 Recall Top-20 → CrossEncoder 精排 Top-4，关闭立即释放 ~2.4GB VRAM
- 📑 **按文件分组注入** — RAG 结果按源文件分组，同一文件多 chunk 共享同一 `<document index="N">`，LLM 引用文件级单一角标
- 🏷️ **引用角标 + 参考面板** — `<ref>N</ref>` 渲染为可 hover 角标，悬浮显示来源文件名 + 原文片段；回答底部列出引用文档去重列表

<details>
<summary><b>📋 高级特性</b>（点击展开：抽象层 · Query Rewrite · Multi-Query · Agentic RAG · 文档级摘要 · LangSmith）</summary>

- **向量存储抽象层**：业务代码不直接 import qdrant_client；`backend/app/services/vector_store/{base,qdrant_backend,bge_m3_sparse}.py` 提供统一接口（10 个方法），便于后端替换或 mock 测试
- **检索模式可配置**：`VECTOR_STORE_SEARCH_MODE` 支持 `dense | hybrid`（默认 hybrid；非 BGE-M3 模型自动降级为 dense），`VECTOR_STORE_HYBRID_FUSION` 支持 `rrf | dbsf`
- **调试端点**：`/api/vs/health` 查看连接与集合统计；`/api/vs/search?q=...&mode=dense|sparse|hybrid&k=N` 不经 Reranker 直接返回原始召回，便于肉眼评估各通道质量
- **自研 BGE-M3 sparse 头**：`BGEM3SparseEncoder` 基于 transformers 复刻（50 行），不依赖 FlagEmbedding；**复用 HuggingFaceEmbeddings 已加载的底层 transformer**，只额外加载 `sparse_linear.pt`（~2KB）
- **Query Rewriting**（默认开）：多轮对话含代词 / 省略 / 过短的 query，DeepSeek-chat 基于最近 2 轮历史轻量改写（如 "它怎么装？" + 上文讨论 LangGraph → "LangGraph 怎么安装"）；启发式门控单轮 query 直接跳过 LLM 零成本；失败软着陆降级原 query
- **Multi-Query 多路召回**（默认关）：DeepSeek 生成 3 个 variant（同义转写 / 上位 / 下位 / 英文同义）并行 hybrid 召回，合并去重后 Reranker 精排或 RRF 融合（k=60）取 Top-4；与 Rewrite 互斥
- **Solo 目录路由规则**：Solo 模式 Planner 首轮纯规则（零 LLM）识别"目录型 query"（列举动词 + 文档指代）命中时注入强路由 hint，让 Planner 优先调 `query_knowledge_base_catalog`；事件日志 `logs/catalog_intent.jsonl` + `backend/scripts/analyze_catalog_intent.py` 输出触发率
- **Agentic RAG 4 档**（`off / grading_only / grading_rewrite / full`）：① Document Grading（LLM 评分过滤，通过率 < 30% 触发 rewrite）② Rewrite-and-retry Loop（上限 2 次）③ Hallucination Check（`full` 档校验事实性，缺支撑时追加 `⚠️` banner）；与 Rewrite 互斥，与 Multi-Query 可并存；任何节点失败软降级到 classical
- **文档级 summary + topics**：向量化完成后异步由 DeepSeek-chat 生成 100-150 字摘要 + 3-8 个主题标签入 Mongo（`$text` 索引）；`query_knowledge_base_catalog(topic="X")` 用 `$regex` 在 `topics[] / summary / original_name` 匹配，解决"我知识库里和 X 相关的书"这类 chunk 级漏书的 document-level 查询；`backend/scripts/backfill_summaries.py` 历史回填
- **LangSmith 可观测性**（默认关）：`.env` 设 `LANGSMITH_TRACING=true` + `LANGSMITH_API_KEY` 后全链路 trace；覆盖 LangGraph Solo / 6 处 `AsyncOpenAI` / AsyncArk Doubao / 4 个 `@traceable` 边界函数；Classic 自动挂 `model/intent/use_*` metadata；Solo 挂 `conversation_id/model/mode=solo`；**关闭时零开销空转**

</details>

---

### 🧬 Embedding 模型管理

- ⚙️ **延迟初始化** — 启动时不自动加载模型（即便本地已缓存），需 `/knowledge` 手动点"加载模型"
- 📥 **BGE-M3 下载管理** — SSE 实时进度条 / 速度 / 剩余时间 / 停止 / 继续 / 重下
- 🎮 **GPU / CPU 切换** — 前端显示 `nvidia-smi` + `torch.cuda.is_available()` 状态，可手动选择
- 🌐 **在线 Embedding API** — 可接入云端 Embedding 服务（默认关）
- 💾 **Reranker 真动态加载** — 开关控制 `/api/embedding/reranker/load|unload`；卸载触发 `torch.cuda.empty_cache()` / `torch.mps.empty_cache()` 释放 ~2.4GB VRAM
- 🚫 未就绪时上传按钮自动禁用 + 操作引导 Tooltip

---

### 🌐 联网搜索

- 🔎 集成 SerpApi 实时网络搜索，结果以 `<web_search_results>` XML 注入当前轮 query
- ⚙️ 配置面板随时开关，与 RAG 模式可同时使用

---

### 💭 DeepSeek 深度思考

- ✅ DeepSeek 模型可开启 "Deep Think"，通过 `extra_body: {"thinking": {"type": "enabled"}}` 启用（绕过 LangChain，原生 AsyncOpenAI SDK）
- 🌊 思考链（reasoning）实时流式展示，可折叠/展开
- 🔒 非 DeepSeek 模型自动禁用该开关

---

### 🎨 富文本渲染

- 📊 Markdown 表格 / 引用块 / 标题等元素美观渲染
- 🌈 代码块语法高亮（Python · JavaScript · TypeScript · Java · Go · SQL 等 12+ 语言）
- 📋 代码块一键复制，显示语言标签
- 💬 引用角标 hover Popover，显示文件名 + 原文摘要

---

### 💼 对话管理

- 💾 **MongoDB 持久化** — 含 `refs` 引用数据，侧栏切换无缝恢复
- 🔄 **状态恢复** — 刷新页面后引用角标完整恢复（`refs` 从 DB；`recommend` 临时态不持久化）
- 🔍 **Fuse.js 模糊搜索** — 标题 + 消息正文加权全文检索，命中字符高亮（terracotta 半透明 `<mark>`）
- 🗑️ **新建 / 删除会话** — Sidebar 直接操作

---

### 🎛️ 后台管理界面（UI 预览，功能尚未接入后端）

> ⚠️ **当前状态**：后台管理界面仅为前端 UI Demo，所有数据均为 mock 静态数据，使用 `localStorage` 做本地持久化。页面展示的数值、图表、配置均**不与后端实际通信**，修改后也**不会影响系统运行行为**。后续版本将逐步完成后端集成。

访问 `/admin` 进入六模块后台管理：

| 模块 | 功能说明 |
|------|---------|
| **仪表盘** | Token 用量、费用趋势、模型分布、KV Cache 命中率、请求日志 |
| **模型配置** | 各模型的 temperature / top_p / max_tokens 参数配置，System Prompt 编辑，思考模式开关 |
| **工具中心** | Kimi 官方工具开关、联网搜索提供商选择（Kimi Native / SerpApi / 禁用）、自定义工具管理 |
| **Prompt 工作室** | System Prompt 模板库、JSON Mode / Partial Mode 配置、对话历史截断策略 |
| **费用监控** | API 余额查询、模型计价参考、KV Cache 分析、详细消费日志 |
| **调试沙盒** | Prompt 测试、多模型并排对比、测试历史记录 |

---

## 📊 代码规模

后端（`backend/`，排除 venv 和 `__pycache__`）主要文件：

| 文件 | 行数 | 说明 |
|------|-----:|------|
| `app/services/rag_service.py` | 465 | 文档向量化（异步 to_thread）、检索、延迟初始化、Reranker 动态 load/unload、`_BackendRetriever` 适配器 |
| `app/services/embedding_service.py` | 380 | GPU 检测、BGE-M3 下载管理、配置持久化 |
| `app/services/vector_store/qdrant_backend.py` | 359 | Qdrant 唯一实现（named vectors + IDF sparse + RRF 融合 + payload index + 维度不匹配自动重建） |
| `app/services/chat_service.py` | 292 | LLM 对话、三分类路由、天气短路路径、RAG 分组注入、标题生成 |
| `app/api/endpoints/embedding.py` | 206 | Embedding 配置 / 下载 / 激活 / Reranker load/unload API |
| `app/services/weather_service.py` | 186 | 城市编码表加载、四级漏斗地名解析、MCP 客户端管理 |
| `app/services/xml_parser.py` | 152 | 多级容错 XML 解析（sloppy-xml + 正则兜底） |
| `app/services/vector_store/bge_m3_sparse.py` | 125 | 自研 BGE-M3 sparse 编码器（复用 HF 已加载的 encoder，只额外加载 sparse_linear.pt） |
| `app/api/endpoints/vector_store.py` | 95 | `/vs/health` · `/vs/search` · `/vs/test-retrieval` 调试端点 |
| `app/services/vector_store/base.py` | 77 | `VectorStoreBackend` 抽象基类（10 个方法） |
| `app/services/intent_service.py` | 65 | 三分类意图识别（code/weather/general）+ city 字段提取 |
| `main.py` | ~155 | 应用入口、lifespan、自动初始化、重启恢复、MCP 连接管理 |
| `app/api/endpoints/upload.py` | ~105 | 文档上传 / 删除 / 状态 API |
| `app/api/endpoints/chat.py` | ~105 | SSE 流式对话、XML 解析、parsed 事件 |
| 其余模型 / Schema / 工具 | — | DB 初始化、Beanie 模型、Pydantic Schema、Jinja2 模板、联网搜索等 |

---

## 🛠️ 技术栈

#### 🐍 后端

[![Python](https://img.shields.io/badge/Python-3.13-3776AB?style=flat-square&logo=python&logoColor=white)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115-009688?style=flat-square&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![Uvicorn](https://img.shields.io/badge/Uvicorn-ASGI-499848?style=flat-square)](https://www.uvicorn.org/)
[![Beanie](https://img.shields.io/badge/Beanie-ODM-47A248?style=flat-square)](https://github.com/BeanieODM/beanie)
[![Pydantic](https://img.shields.io/badge/Pydantic-v2-E92063?style=flat-square&logo=pydantic&logoColor=white)](https://docs.pydantic.dev/)
[![Jinja2](https://img.shields.io/badge/Jinja2-templates-B41717?style=flat-square&logo=jinja&logoColor=white)](https://jinja.palletsprojects.com/)

#### 🤖 AI / LLM 编排

[![LangChain](https://img.shields.io/badge/LangChain-1.x-1C3C3C?style=flat-square&logo=langchain&logoColor=white)](https://www.langchain.com/)
[![LangGraph](https://img.shields.io/badge/LangGraph-ReAct-1C3C3C?style=flat-square)](https://github.com/langchain-ai/langgraph)
[![LangSmith](https://img.shields.io/badge/LangSmith-tracing-F59E0B?style=flat-square)](https://smith.langchain.com/)
[![OpenAI SDK](https://img.shields.io/badge/OpenAI-SDK-412991?style=flat-square&logo=openai&logoColor=white)](https://platform.openai.com/)
[![DeepSeek](https://img.shields.io/badge/DeepSeek-V3.2-4D6BFE?style=flat-square)](https://www.deepseek.com/)
[![Kimi](https://img.shields.io/badge/Kimi-K2-FF6900?style=flat-square)](https://www.moonshot.cn/)
[![Doubao](https://img.shields.io/badge/Doubao-Code-1E40AF?style=flat-square)](https://www.volcengine.com/product/doubao)
[![mem0](https://img.shields.io/badge/mem0-2.0-7C3AED?style=flat-square)](https://mem0.ai/)

#### 💾 存储 / 检索

[![MongoDB](https://img.shields.io/badge/MongoDB-8.x-47A248?style=flat-square&logo=mongodb&logoColor=white)](https://www.mongodb.com/)
[![Qdrant](https://img.shields.io/badge/Qdrant-1.12+-DC244C?style=flat-square)](https://qdrant.tech/)
[![BGE-M3](https://img.shields.io/badge/BGE--M3-1024d-FF6B35?style=flat-square)](https://huggingface.co/BAAI/bge-m3)
[![BGE Reranker](https://img.shields.io/badge/BGE--Reranker-v2--m3-FF6B35?style=flat-square)](https://huggingface.co/BAAI/bge-reranker-v2-m3)
[![LightRAG](https://img.shields.io/badge/LightRAG-Graph-FFA500?style=flat-square)](https://github.com/HKUDS/LightRAG)
[![HuggingFace](https://img.shields.io/badge/🤗_HuggingFace-Embeddings-FFD21E?style=flat-square)](https://huggingface.co/)

#### 🚀 任务队列 / 基础设施

[![Celery](https://img.shields.io/badge/Celery-5.3-37814A?style=flat-square&logo=celery&logoColor=white)](https://docs.celeryq.dev/)
[![Redis](https://img.shields.io/badge/Redis-AOF-DC382D?style=flat-square&logo=redis&logoColor=white)](https://redis.io/)
[![Flower](https://img.shields.io/badge/Flower-monitor-EC407A?style=flat-square)](https://flower.readthedocs.io/)
[![Docker](https://img.shields.io/badge/Docker-compose-2496ED?style=flat-square&logo=docker&logoColor=white)](https://www.docker.com/)

#### 🔌 MCP / 工具

[![FastMCP](https://img.shields.io/badge/FastMCP-SSE-2196F3?style=flat-square)](https://gofastmcp.com/)
[![langchain-mcp](https://img.shields.io/badge/langchain--mcp--adapters-1C3C3C?style=flat-square)](https://github.com/langchain-ai/langchain-mcp-adapters)
[![SerpAPI](https://img.shields.io/badge/SerpAPI-search-4285F4?style=flat-square)](https://serpapi.com/)
[![高德 MCP](https://img.shields.io/badge/%E9%AB%98%E5%BE%B7-Weather_MCP-00BFFF?style=flat-square)](https://lbs.amap.com/)

#### 🎨 前端

[![Vue 3](https://img.shields.io/badge/Vue-3.5-4FC08D?style=flat-square&logo=vue.js&logoColor=white)](https://vuejs.org/)
[![TypeScript](https://img.shields.io/badge/TypeScript-5.x-3178C6?style=flat-square&logo=typescript&logoColor=white)](https://www.typescriptlang.org/)
[![Vite](https://img.shields.io/badge/Vite-8-646CFF?style=flat-square&logo=vite&logoColor=white)](https://vitejs.dev/)
[![Pinia](https://img.shields.io/badge/Pinia-3-FFD43B?style=flat-square&logo=pinia&logoColor=black)](https://pinia.vuejs.org/)
[![Vue Router](https://img.shields.io/badge/Vue_Router-4-4FC08D?style=flat-square&logo=vue.js&logoColor=white)](https://router.vuejs.org/)
[![Tailwind v4](https://img.shields.io/badge/Tailwind-v4-06B6D4?style=flat-square&logo=tailwindcss&logoColor=white)](https://tailwindcss.com/)
[![shadcn-vue](https://img.shields.io/badge/shadcn--vue-radix-000000?style=flat-square)](https://www.shadcn-vue.com/)
[![Element Plus](https://img.shields.io/badge/Element_Plus-2.x-409EFF?style=flat-square&logo=element&logoColor=white)](https://element-plus.org/)
[![Vue Flow](https://img.shields.io/badge/Vue_Flow-1.4-FF5C8D?style=flat-square)](https://vueflow.dev/)
[![ECharts](https://img.shields.io/badge/ECharts-vue--echarts-AA344D?style=flat-square&logo=apacheecharts&logoColor=white)](https://echarts.apache.org/)
[![Fuse.js](https://img.shields.io/badge/Fuse.js-fuzzy_search-2196F3?style=flat-square)](https://fusejs.io/)
[![Lucide](https://img.shields.io/badge/lucide--vue-icons-F56565?style=flat-square&logo=lucide&logoColor=white)](https://lucide.dev/)

#### 📄 文档解析

[![pdfplumber](https://img.shields.io/badge/pdfplumber-PDF-FF0000?style=flat-square)](https://github.com/jsvine/pdfplumber)
[![docx2txt](https://img.shields.io/badge/docx2txt-Word-2B579A?style=flat-square)](https://pypi.org/project/docx2txt/)
[![unstructured](https://img.shields.io/badge/unstructured-multi-9C27B0?style=flat-square)](https://unstructured.io/)
[![ebooklib](https://img.shields.io/badge/ebooklib-EPUB-795548?style=flat-square)](https://github.com/aerkalov/ebooklib)
[![openpyxl](https://img.shields.io/badge/openpyxl-Excel-217346?style=flat-square)](https://openpyxl.readthedocs.io/)
[![python-pptx](https://img.shields.io/badge/python--pptx-PowerPoint-D24726?style=flat-square)](https://python-pptx.readthedocs.io/)

<details>
<summary>📋 完整技术栈说明（点击展开）</summary>

| 层级 | 技术 |
|------|------|
| **后端框架** | Python 3.12+, FastAPI[all], Uvicorn |
| **数据库** | MongoDB 8.x (Beanie ODM + AsyncMongoClient 原生异步驱动) |
| **AI/LLM** | LangChain 1.x, LangChain-OpenAI, LangGraph, OpenAI SDK (AsyncOpenAI) |
| **MCP 集成** | langchain-mcp-adapters（SSE 客户端）, FastMCP（高德天气 MCP Server，端口 8001） |
| **向量检索** | Qdrant 原生混合检索（dense + sparse 服务端 RRF 融合），qdrant-client, HuggingFace Embeddings |
| **Embedding 模型** | BAAI/bge-m3（默认，1024 维，8192 Token 上限，GPU 推理；dense + learned sparse 双通道；sparse 头由自研 `BGEM3SparseEncoder` 基于 transformers 复刻） |
| **Reranker 模型** | BAAI/bge-reranker-v2-m3（CrossEncoder，Top-20 → Top-4，**按需动态加载/卸载**） |
| **图谱检索** | LightRAG 1.4.x（graphml + nano-vec，5 档查询模式：naive/local/global/hybrid/mix） |
| **长记忆** | mem0ai 2.0（ADD/UPDATE/DELETE/NOOP LLM judge）+ Mongo 双时间镜像 |
| **Prompt 模板** | Jinja2 (.j2 模板，结构化 XML 注入，`\| e` 转义) |
| **XML 解析** | sloppy-xml（容错 LLM XML 解析，多级降级） |
| **联网搜索** | SerpAPI (google-search-results) |
| **文档解析** | pdfplumber, docx2txt, unstructured, ebooklib, openpyxl, python-pptx |
| **前端框架** | Vue 3.5, TypeScript 5, Vite 8 |
| **UI 组件库** | shadcn-vue (reka-ui) + Element Plus（共存 · 渐进迁移）, Pinia, Vue Router |
| **可视化** | Vue Flow（节点图）, vue-echarts（统计图） |
| **搜索 / 工具** | Fuse.js（会话模糊搜索）, lucide-vue-next（图标）, @vueuse/motion（动效） |
| **Markdown 渲染** | markdown-it, highlight.js |

</details>

## 🚀 快速开始

### 前置要求

- Python 3.12+（**macOS 实测环境 Python 3.13.13**）
- Node.js 18+
- **MongoDB**（**版本须与数据目录严格对应，见下方警告**）
  - Windows 主开发环境实测：**mongod 8.2.6**（数据目录 `backend/mongo-data/`，FCV=8.2）
  - macOS 实测：**mongod 8.0.21**（Homebrew `mongodb-community`，数据目录 `backend/mongo-data-macos/`，FCV=8.0）
- **Qdrant** 1.12+（本地二进制或 Docker 镜像均可）

> ⚠️ **MongoDB 版本兼容性警告（踩过坑）**
>
> MongoDB 对数据目录的 `featureCompatibilityVersion (FCV)` 做**严格前向兼容检查**：
> **高版本 mongod 写入的数据目录，低版本 mongod 打不开**，会以 `exitCode 62` 直接退出，错误提示类似：
>
> ```
> Wrong mongod version. UPGRADE PROBLEM: Found an invalid featureCompatibilityVersion document ...
> Invalid feature compatibility version value '8.2'; expected '7.0' or '7.3' or '8.0'.
> ```
>
> 本项目最初在 Windows 上用 mongod 8.2.6 开发，`backend/mongo-data/` 里的 FCV 已升到 8.2；切到 macOS 用 Homebrew 默认的 mongod 8.0.21 启动时**无法读取**这份数据。
>
> **解决方案**：macOS 侧使用独立数据目录（`backend/mongo-data-macos/`）和独立配置（`backend/mongo-macos.conf`），两个平台各用各的，互不污染。**切记不要共用同一份 `mongo-data/`**。如果一定要跨平台迁移数据，需先在高版本机器上 `mongodump` 导出，目标平台新库 `mongorestore` 导入。

### 1. 启动 Qdrant 向量数据库

项目提供了 Windows 快速启动脚本（数据盘路径等配置在 `backend/Qdrant-config-data/config.yaml`）：

```bash
# 双击或命令行执行
backend\Qdrant-config-data\start-qdrant.bat
```

启动后访问：
- HTTP API: `http://localhost:6333`
- Web UI Dashboard: `http://localhost:6333/dashboard`
- Health check: `http://localhost:6333/healthz`

数据存储在 `backend/Qdrant-config-data/storage/`，快照存在 `snapshots/`（`config.yaml` 中已设为绝对路径）。

### 2. 启动 MongoDB

**Windows（mongod 8.2.x）**：

```bash
cd backend
start-mongodb.bat
# 或手动：mongod --config backend/mongo.conf
```

数据存储在 `backend/mongo-data/`（FCV=8.2）。

**macOS（mongod 8.0.x，Homebrew）**：

```bash
brew tap mongodb/brew
brew install mongodb-community    # 目前 formula 是 8.0.x
bash backend/start-mongodb.sh
# 或手动：mongod --config backend/mongo-macos.conf
```

数据存储在 `backend/mongo-data-macos/`（FCV=8.0），**与 Windows 的 `mongo-data/` 是两份独立库，互不干扰**。配置文件 `backend/mongo-macos.conf` 与 `mongo.conf` 内容几乎相同，只有 `dbPath` / `log.path` 指向 macOS 专用目录。

两个平台都监听 `127.0.0.1:27017`，默认启动不冲突（因为不会同时开）。

### 3. 后端设置

```bash
cd backend

# 创建并激活虚拟环境
python -m venv venv
venv\Scripts\activate        # Windows
# source venv/bin/activate   # macOS/Linux

# 安装依赖（CPU 版，默认）
pip install -r requirements.txt

# 如果有 NVIDIA GPU（推荐，用于 BGE-M3 加速推理）
# 需要 CUDA 驱动 >= 12.4（nvidia-smi 中确认 CUDA Version >= 12.4）
pip install torch>=2.6.0 torchvision torchaudio --index-url https://download.pytorch.org/whl/cu124
pip install -r requirements.txt
```

在 `backend/` 目录下创建 `.env` 文件：

```env
MOONSHOT_API_KEY=sk-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
DEEPSEEK_API_KEY=sk-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
ARK_API_KEY=xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
SERPAPI_API_KEY=xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
HF_ENDPOINT=https://hf-mirror.com
MONGODB_URL=mongodb://localhost:27017
MONGODB_DB_NAME=chatbox

# Vector store (Qdrant)
QDRANT_URL=http://localhost:6333
QDRANT_COLLECTION=kb_main
QDRANT_API_KEY=
VECTOR_STORE_SEARCH_MODE=hybrid        # dense | hybrid（非 BGE-M3 模型自动降级为 dense）
VECTOR_STORE_HYBRID_FUSION=rrf         # rrf | dbsf
VECTOR_STORE_RECALL_K=20               # 有 Reranker 时的候选数
VECTOR_STORE_TOP_K=4                   # 无 Reranker 时直接返回的数量
```

> ⚠️ **安全提醒**：`.env` 文件**不应**提交到 Git 仓库。请确保 `.gitignore` 已包含 `backend/.env`；如果历史提交中已泄露过真实 API Key，需立即 rotate 这些 key 并用 `git filter-repo` 清理历史。

启动后端：

```bash
# 正式环境（推荐）：不启用 --reload，启动速度更快
uvicorn main:app

# 开发环境：仅监听 app/ 目录变更，避免 data/、venv/ 等大目录触发无效重载
uvicorn main:app --reload --reload-dir app
```

服务将在 `http://localhost:8000` 启动，API 文档访问 `http://localhost:8000/docs`。

### 3.5 启动高德天气 MCP Server（天气查询功能需要）

天气查询功能依赖独立的 MCP Server 进程，需在后端启动**之前或同时**运行：

```powershell
# Windows PowerShell（在项目根目录）
cd Gaode-weather-MCP-server
$env:PORT=8001; python server.py
```

MCP Server 将监听 `http://127.0.0.1:8001`（SSE 端点：`/sse`）。

> 若 MCP Server 未启动，后端仍可正常启动（连接失败会打印 WARNING 日志），但天气查询功能不可用，其他功能不受影响。

### 3.6 （可选）启用 Celery 异步向量化（默认 off）

> 削峰填谷模式：上传文档走 Redis 队列 + Docker worker 消费。
> 📘 **运维手册**：[`backend/CELERY.md`](backend/CELERY.md)（首次启动 / 日常使用 / 故障排查）
> 📐 **架构决策**：[`analysis-for-backend/celery-module.md`](analysis-for-backend/celery-module.md)

```bash
# 前提：本机 Redis 已安装（brew install redis）+ Docker 已启动

# 1. 开启 Redis AOF 持久化（一键脚本：检测配置 + 备份 + 追加 + brew services restart）
bash backend/start-redis-with-aof.sh

# 2. 启 Docker worker + Flower 监控
cd backend
docker compose -f docker-compose.celery.yml up -d
docker logs xuanjian-celery-worker    # 应看到 "celery@... ready"

# 3. 前端访问 /admin/infra → 三张健康卡应全绿 → 打开 Celery 异步向量化 toggle
# 4. Flower 监控：打开 http://localhost:5555（账号 admin / 密码 xuanjian）
```

**关闭**：前端 `/admin/infra` 关掉 toggle 即可，立即回到 `asyncio.to_thread` 路径，零破坏。Docker worker 可继续保持运行，也可 `docker compose down`。

### 4. 前端设置

```bash
cd frontend

npm install
npm run dev
```

访问 `http://localhost:5173` 开始使用，`http://localhost:5173/admin` 进入后台管理。

---

## 📂 项目结构

```
.
├── backend/
│   ├── app/
│   │   ├── api/
│   │   │   └── endpoints/
│   │   │       ├── chat.py              # SSE 流式对话接口（classic 路径，XML 解析 + parsed 事件）
│   │   │       ├── solo.py              # /api/chat/solo SSE 端点（Solo 模式入口，LangGraph 编排）
│   │   │       ├── conversations.py     # 对话 CRUD 接口
│   │   │       ├── embedding.py         # Embedding 配置 / 下载 / 激活 / Reranker load/unload / Agentic RAG / Graph RAG
│   │   │       ├── upload.py            # 文档上传 / 列表 / 删除 / 状态轮询接口
│   │   │       ├── vector_store.py      # /vs/health · /vs/search · /vs/test-retrieval 调试端点
│   │   │       └── memory.py            # Context Engine v2 P3.4 · /api/memory 审计 + /context-view 端点
│   │   ├── core/
│   │   │   └── config.py               # 应用配置 (pydantic-settings)
│   │   ├── db/
│   │   │   └── database.py             # MongoDB / Beanie 初始化
│   │   ├── models/
│   │   │   ├── conversation.py         # Beanie Document 模型（对话，含 refs 字段）
│   │   │   ├── knowledge_document.py   # Beanie Document 模型（知识库文档 + 向量化状态）
│   │   │   ├── event.py                # Context Engine v2 P1 · 事件流真相源（9 种 EventKind）
│   │   │   ├── memory.py               # Context Engine v2 P3 · durable memory 双时间 schema
│   │   │   └── task.py                 # Context Engine v2 P5 · TaskContext 复杂任务隔离
│   │   ├── prompts/                    # Jinja2 Prompt 模板
│   │   │   ├── chat_system.j2          # system message（角色 + XML 格式指令 + KB 引用说明）
│   │   │   └── chat_query.j2           # user message（XML 嵌入 RAG + 联网搜索结果，含 | e 转义）
│   │   ├── schemas/
│   │   │   ├── chat.py                 # ChatRequest / ChatMessage Pydantic 模型
│   │   │   └── conversation.py         # 对话相关 schema（含 refs 字段）
│   │   ├── services/
│   │   │   ├── chat_service.py         # LLM 对话、三分类意图路由、天气短路路径、标题生成
│   │   │   ├── conversation_service.py # 会话 CRUD 业务逻辑
│   │   │   ├── embedding_service.py    # GPU 检测、Embedding 配置、BGE-M3 下载管理
│   │   │   ├── intent_service.py       # 三分类意图识别（code/weather/general）+ city 提取
│   │   │   ├── rag_service.py          # 延迟初始化、异步向量化（to_thread）& 检索
│   │   │   ├── vector_store/
│   │   │   ├── vector_store/
│   │   │   │   ├── base.py              # VectorStoreBackend 抽象基类（10 个方法）
│   │   │   │   ├── qdrant_backend.py    # Qdrant 唯一实现（named vectors + RRF + payload index）
│   │   │   │   ├── bge_m3_sparse.py     # 自研 BGE-M3 sparse 编码器（复用 HF 已加载模型）
│   │   │   │   └── __init__.py          # get_vector_store() 单例工厂
│   │   │   ├── condenser.py            # Context Engine v2 P2 · RecentBuffer + OpenHands 递归 Summary + ToolOutput
│   │   │   ├── graph_rag.py            # Graph RAG (LightRAG 1.4.x) 适配层 · 5 档查询模式 + fail-soft
│   │   │   ├── agentic_rag.py          # Agentic RAG · Document Grading + Rewrite-Loop + Hallucination Check
│   │   │   ├── memory_service.py       # Context Engine v2 P3 · mem0 薄包装 + Mongo memories 双写
│   │   │   ├── context_router.py       # Context Engine v2 P3.3/P4.2 · 规则路由 + InjectionPlan 生成
│   │   │   ├── context_types.py        # Context Engine v2 P4.1 · InjectionPlan/TokenBudget/AssembledMessages
│   │   │   ├── context_assembler.py    # Context Engine v2 P4.3 · budget 裁剪装配器
│   │   │   ├── task_service.py         # Context Engine v2 P5.1 · TaskContext CRUD helper
│   │   │   ├── solo/                   # Solo 模式（LangGraph ReAct 通道，详见 analysis-for-backend/solo-module.md）
│   │   │   │   ├── state.py             # SoloState TypedDict（messages/model_name/need_thinking/iteration）
│   │   │   │   ├── tools.py             # 5 个 @tool 薄包装 + 权威数据源 docstring + weather 载荷清洗
│   │   │   │   ├── complexity.py        # DeepSeek JSON-mode 复杂度分类（~300ms）
│   │   │   │   ├── nodes.py             # classify_complexity_node / planner_node（含 nudge 兜底）/ should_continue
│   │   │   │   ├── graph.py             # StateGraph：START → classify_complexity → planner ⇄ tools → END
│   │   │   │   └── events.py            # astream_events(v2) → 前端 SSE 协议翻译（含嵌套工具事件过滤）
│   │   │   ├── weather_service.py      # 城市编码表加载、地名四级漏斗解析、MCP 调用
│   │   │   └── xml_parser.py           # 多级容错 XML 解析器（sloppy-xml + 正则兜底）
│   │   └── tools/
│   │       └── web_search.py           # SerpApi 联网搜索工具
│   ├── data/
│   │   ├── chroma/                     # 🗄️ 历史遗留：Chroma 向量库（已被 Qdrant 替换，保留存档不动）
│   │   ├── models/                     # 本地缓存的 Embedding 模型（bge-m3 / minilm + sparse_linear.pt）
│   │   ├── uploads/                    # 用户上传的文档
│   │   └── AMap_adcode_citycode.xlsx   # 高德城市编码表（启动时加载为内存 dict）
│   ├── Qdrant-config-data/             # Qdrant 配置与数据目录
│   │   ├── config.yaml                 # Qdrant 服务配置（绝对路径 + IDF sparse）
│   │   ├── start-qdrant.bat            # Qdrant 启动脚本 (Windows)
│   │   ├── storage/                    # Qdrant 主数据
│   │   ├── snapshots/                  # Qdrant 快照
│   │   └── static/                     # qdrant-web-ui 静态资源
│   ├── mongo.conf                      # MongoDB 配置文件
│   ├── start-mongodb.bat               # MongoDB 启动脚本 (Windows)
│   ├── main.py                         # 应用入口（lifespan、自动初始化、重启恢复）
│   ├── requirements.txt                # Python 依赖（CPU 版）
│   └── requirements-gpu.txt            # Python 依赖（GPU 版，含 cu124 torch 索引）
│
├── frontend/
│   ├── src/
│   │   ├── components/
│   │   │   ├── admin/                  # 后台管理界面（6 个模块）
│   │   │   │   ├── AdminLayout.vue
│   │   │   │   ├── AdminDashboard.vue
│   │   │   │   ├── AdminModelConfig.vue
│   │   │   │   ├── AdminToolHub.vue
│   │   │   │   ├── AdminPromptStudio.vue
│   │   │   │   ├── AdminCostMonitor.vue
│   │   │   │   └── AdminSandbox.vue
│   │   │   ├── ChatArea.vue            # 消息区（引用角标 / Popover / Sources / 推荐追问 / 思考块）
│   │   │   ├── ChatLayout.vue          # 聊天页面布局
│   │   │   ├── ConfigPanel.vue         # 配置面板（模型、知识库、联网、思考模式开关）
│   │   │   ├── InputBox.vue            # 输入框（发送 / 停止生成）
│   │   │   ├── KnowledgeBase.vue       # 知识库管理（上传 / 删除 / 向量化状态 / Embedding 配置 / Reranker 开关 / Agentic RAG 4 档 / Graph RAG 开关）
│   │   │   ├── MemoryAudit.vue         # Context Engine v2 P3.4 · /settings/memory 审计页（编辑 / 软删 / 失效高亮）
│   │   │   ├── ContextViewer.vue       # Context Engine v2 P5.2 · 上下文视图抽屉（recent events + rolling summary + memory hits）
│   │   │   └── Sidebar.vue             # 侧边栏（历史对话 + 后台管理入口）
│   │   ├── router/
│   │   │   └── index.ts                # Vue Router（/ 聊天、/knowledge、/admin）
│   │   ├── store/
│   │   │   └── chat.ts                 # Pinia 全局状态（消息、对话、refs、recommend）
│   │   ├── utils/
│   │   │   └── pin_parser.ts           # Context Engine v2 P5.2 · @kb / @memory / @last-turn / @reset 语法解析
│   │   └── App.vue
│   └── package.json
│
├── tests/
│   ├── test_xml_parser.py              # XML 解析器单元测试（多场景，含 mock 数据）
│   └── ...
│
├── Gaode-weather-MCP-server/           # 高德天气 MCP Server（独立进程，端口 8001）
│   ├── server.py                       # FastMCP SSE 服务，自动注入高德 API Key
│   ├── openapi.json                    # 高德天气 API 的 OpenAPI 规范
│   └── 如何接入.md                      # 接入指南（stdio / SSE / LangChain 1.x 三种场景）
│
└── plan-doc-dir/                       # 设计文档与技术分析
```

## 🔧 Prompt 架构说明

后端采用 Jinja2 模板 + XML tags 构建 Prompt，遵循 OpenAI / Anthropic 最佳实践：

```
messages 数组（发送给 LLM）
├── {"role": "system",    "content": chat_system.j2 渲染结果}
│                                    ├── 角色设定 + 语言指令
│                                    ├── KB 信息（条件渲染）
│                                    └── XML 输出格式约束（始终包含）
├── {"role": "user",      "content": "历史第 1 轮问题"}   ← 原样保留
├── {"role": "assistant", "content": "历史第 1 轮回答"}   ← 原样保留
│   ... 更多历史轮次 ...
└── {"role": "user",      "content": chat_query.j2 渲染结果}
                                      ├── <documents> RAG XML（按文件分组，| e 转义）</documents>
                                      ├── <web_search_results> ... </web_search_results>
                                      └── <query> 用户当前问题（| e 转义）</query>
```

LLM 输出格式（始终要求）：
```xml
<content>
回答正文，知识库模式下在引用处插入 <ref>N</ref>（N 为文件级 index，非 chunk 级）。
</content>
<recommend>
<rec>追问问题1</rec>
<rec>追问问题2</rec>
</recommend>
```

- 历史对话通过标准 messages 数组传递（符合 OpenAI Chat Completion API 规范）
- RAG 结果按源文件分组注入，同一文件的所有 chunk 共享一个 `<document index="N">`，LLM 只需引用一个文件一个编号
- 文档内容通过 Jinja2 `| e` 过滤器做 XML 转义，防止特殊字符破坏 XML 结构
- LLM 输出 XML 由 `xml_parser.py` 解析：sloppy-xml 容错解析 → 正则兜底 → 纯文本兜底

---

## 📡 主要 API 端点

### 对话

| 方法 | 路径 | 说明 |
|------|------|------|
| `POST` | `/api/chat/completions` | Classic 模式：开关驱动的线性流水线（意图识别 → RAG / 联网 / 天气 / 思考） |
| `POST` | `/api/chat/solo` | Solo 模式：LangGraph ReAct 图，Agent 自主决定工具调用；SSE 事件增加 `stage` / `tool_call` / `reasoning`（复用 classic 的 `content` / `parsed` / `title_update` / `[DONE]`） |

### 知识库文档

| 方法 | 路径 | 说明 |
|------|------|------|
| `POST` | `/api/upload` | 上传文档，立即返回，后台异步向量化 |
| `GET` | `/api/documents` | 获取所有文档列表（含向量化状态） |
| `GET` | `/api/documents/{file_id}/status` | 轮询单个文档的向量化状态 |
| `DELETE` | `/api/documents/{file_id}` | 删除文档（向量 → MongoDB → 磁盘，保证一致性） |
| `POST` | `/api/documents/{file_id}/revectorize` | 重新向量化指定文档 |

### Embedding 管理

| 方法 | 路径 | 说明 |
|------|------|------|
| `GET` | `/api/embedding/system-info` | GPU 状态、模型缓存、当前配置、`embedding_ready` 与 `reranker_loaded` |
| `GET` | `/api/embedding/config` | 获取当前 Embedding 配置 |
| `PUT` | `/api/embedding/config` | 更新配置（切换模型维度时自动重建 Qdrant 集合） |
| `POST` | `/api/embedding/download` | 开始下载 BGE-M3 模型（支持断点续传） |
| `POST` | `/api/embedding/download/cancel` | 取消正在进行的下载 |
| `GET` | `/api/embedding/download/status` | 查询下载进度（SSE 轮询） |
| `GET` | `/api/embedding/rag-strategy` | 查询当前检索策略（`recall_only` / `recall+rerank`） |
| `GET` | `/api/embedding/search-mode` | 查询当前召回模式（`dense` / `hybrid`）及 `sparse_supported` |
| `PUT` | `/api/embedding/search-mode` | 运行时切换召回模式；非 BGE-M3 模型自动降级为 dense |
| `GET` | `/api/embedding/multi-query` | 查询 Multi-Query 多路召回开关状态 |
| `PUT` | `/api/embedding/multi-query` | 运行时切换 Multi-Query（body `{enabled: bool}`；持久化到 `embedding_config.json`） |
| `POST` | `/api/embedding/activate` | 激活并加载 Embedding 模型到内存（不触发 Reranker 加载） |
| `POST` | `/api/embedding/reranker/load` | **显式加载 BGE-Reranker 到显存**（Embedding 未就绪 503，模型未下载 400） |
| `POST` | `/api/embedding/reranker/unload` | **卸载 Reranker 并 `torch.cuda.empty_cache()` / `torch.mps.empty_cache()` 释放显存** |

### 向量存储（Qdrant）调试

| 方法 | 路径 | 说明 |
|------|------|------|
| `GET` | `/api/vs/health` | Qdrant 连接状态 + 集合统计（points 数、维度、`sparse_enabled`、named vectors 配置） |
| `GET` | `/api/vs/search?q=...&mode=dense\|sparse\|hybrid&k=N` | 不经 Reranker 直接返回原始召回 top-N，用于评估各通道召回质量 |
| `GET` | `/api/vs/test-retrieval?query=...` | 走完整链路（含 Reranker）的调试端点 |

### Graph RAG（LightRAG）

| 方法 | 路径 | 说明 |
|------|------|------|
| `GET` | `/api/embedding/graph-rag` | 查询 Graph RAG 开关 + 当前 query mode（naive/local/global/hybrid/mix）|
| `PUT` | `/api/embedding/graph-rag` | 切换开关 / 查询模式（body `{enabled?, query_mode?}`）；启用时覆盖 Agentic + Multi-Query |
| `POST` | `/api/embedding/graph-rag/build` | 启动 LightRAG 索引构建（后台任务）|
| `GET` | `/api/embedding/graph-rag/build/status` | 轮询构建进度（phase / total / processed / current_doc）|
| `POST` | `/api/embedding/graph-rag/clear` | 清空图索引目录（需 `{confirm: true}`，不影响 Qdrant）|
| `GET` | `/api/embedding/graph-rag/stats` | 图统计（节点数 / 边数 / 文档数 / 路径）|

### Context Engine v2（长对话记忆 / 上下文审计）

| 方法 | 路径 | 说明 |
|------|------|------|
| `GET` | `/api/memory` | 列出 durable memory（`user_id` / `include_invalidated` / `limit`）|
| `PUT` | `/api/memory/{memory_id}` | 手工编辑 memory.object 文本（Mongo 直改，raw_metadata.manually_edited=true；mem0 侧暂不同步）|
| `DELETE` | `/api/memory/{memory_id}` | 软删：打 `invalidated_at`，不从 mem0 Qdrant 真删（保留溯源）|
| `POST` | `/api/memory/reflect` | 手工触发一次后台反思（force=True 绕过 debounce；`{conversation_id, current_turn_id?, user_id?}`）|
| `GET` | `/api/conversations/{conversation_id}/context-view` | 当前会话上下文快照：recent events 预览 / rolling summary / memory hits（供 Context Viewer 抽屉读取）|

---

## 🗺️ 开发路线图

### 近期计划（AI 核心升级）

| 优先级 | 功能 | 核心价值 | 状态 |
|--------|------|---------|------|
| ✅ 已完成 | **三分类意图识别路由** | DeepSeek JSON 三分类（code/weather/general），同步提取 city，代码路由 Doubao，天气走 MCP 短路路径 | 已上线 |
| ✅ 已完成 | **实时天气查询（MCP）** | 高德天气 MCP Server（SSE 协议），langchain-mcp-adapters 接入，四级漏斗地名解析，同名多地并行查询 | 已上线 |
| ✅ 已完成 | **Qdrant 原生混合检索（Hybrid Search）** | dense + learned sparse（BGE-M3 lexical_weights）+ 服务端 RRF 融合；`Modifier.IDF` 内置 IDF 调整；自研 sparse 头复用 HF 已加载模型节省 ~2GB VRAM | 已上线 |
| ✅ 已完成 | **向量存储抽象层** | `VectorStoreBackend` 接口屏蔽 Qdrant 原生 API，业务代码不直接 import qdrant_client | 已上线 |
| ✅ 已完成 | **Reranker 动态加载/卸载** | 前端开关真正控制 VRAM 占用；关闭时 `torch.cuda.empty_cache()` / `torch.mps.empty_cache()` 立即释放 ~2.4GB | 已上线 |
| 🔴 P0 | **RAG 质量评测集 + Recall@K 对比** | 20 条 query 标注集 + 脚本化对比 dense-only / hybrid / hybrid+rerank / multi-query 四条曲线，量化收益 | 规划中 |
| ✅ 已完成 | **LangGraph Agentic ReAct（Solo 模式）** | `/api/chat/solo` 端点 + StateGraph（classify_complexity → planner ⇄ tools）+ 5 个 @tool + 前端 AgentTrace 可视化；classic 路径零改动 | 已上线 |
| ✅ 已完成 | **Query Rewriting（狭义改写）** | classic 路径前置节点：启发式门控（代词/过短触发） + DeepSeek-chat 基于最近 2 轮改写；Solo 走 system prompt 自治改写（不暴露 tool，避免双层 Agent） | 已上线 |
| ✅ 已完成 | **Multi-Query 多路召回** | 前端可选开关（默认关）：LLM 生成 3 个 variant 并行召回；Reranker 在则 CrossEncoder 对合并池用原 query 精排，不在则标准 RRF 融合；与 Rewrite 互斥 | 已上线 |
| ✅ 已完成 | **文档级 summary/topics + 目录查询** | 向量化后异步生成 100-150 字摘要 + 3-8 个主题标签入 Mongo（`$text` 索引）；`query_knowledge_base_catalog(topic=...)` 用 `$regex` 在 topics/summary/filename 匹配，闭合 "和 X 相关的书" 类 document-level 查询 | 已上线 |
| ✅ 已完成 | **Solo 目录路由规则** | Planner 首轮对 query 做纯规则检测（列举动词 + 文档指代），命中则注入强路由 hint 让 Planner 优先调 `query_knowledge_base_catalog`；事件日志 + 分析脚本已配套 | 已上线 |
| ✅ 已完成 | **LangGraph Agentic RAG（CRAG）**| classic 路径补齐 Document Grading + Rewrite-and-retry Loop + Hallucination Check 三件套，前端 `/knowledge` 加 4 档控件 `off / grading_only / grading_rewrite / full` 可一键对比 classical；默认 off 向后兼容；失败软着陆降级到 classical | 已上线 |
| 🟡 POC | **Graph RAG（LightRAG 后端）** | classic 路径最高优先级分支：LightRAG 本地 JSON + NetworkX 图谱（不引入独立 KG DB），5 档查询模式 `naive / local / global / hybrid / mix`；前端一键构建 / 增量更新 / 清空索引；启用时覆盖 Agentic + Multi-Query；fail-soft 索引空或查询异常降级到 classical；默认 off | 已上线 |
| ✅ 已完成 | **RAG 策略评测框架（CRUD-mini + RAGAS）** | 从 CRUD-RAG 抽 60 条中文 query × 10 策略配置（off / multi_query / agentic×3 / graph×5）= 600 trials；`run_rag_bench.py` SSE runner + `score_rag_bench.py`（Recall@K 客观 + RAGAS DeepSeek judge），产出 markdown 对比矩阵；首轮实测 `agentic_grading` 跨类别最稳（Correctness 0.702）；完整数据和方法见 `RAG评测/` | 已上线 |
| ✅ 已完成 | **Context Engine v2（长上下文 / 记忆）** | 7 层上下文模型（Identity / Recent Buffer / Rolling Summary / Durable Memory / Retrieval / Runtime / View）+ Event Stream（Mongo `events` 集合为真相源）+ Condenser Pipeline（OpenHands 递归 rolling summary + Recent Buffer 保护）+ Mem0 durable memory（ADD/UPDATE/DELETE judge + Zep 式双时间镜像）+ Context Router + Assembler + ToolOutputCondenser + TaskContext 隔离；前端 `/settings/memory` 审计页 + Context Viewer 抽屉。P1-P5 五阶段全落地；所有开关默认 off 可独立翻启。架构详见 `analysis-for-backend/context-engine.md`，设计与选型过程见 `plan-doc-dir/长上下文机制设计v2·集百家之长.md` | 已上线 |
| ✅ 已完成 | **LangSmith 可观测性** | 全链路 LLM 调用追踪（延迟、Token、成本）；统一 `get_openai()` 工厂 + `@traceable` 边界函数 + Solo config metadata；关闭时零开销空转 | 已上线 |
| ✅ 已完成 | **Celery + Redis 异步向量化（默认 off）** | 运行时可开关，开启时上传走 Redis 队列 + Docker worker 消费（concurrency=2 削峰），关闭时走原 `asyncio.to_thread` 零破坏。Worker 容器 ~100MB 不加载 BGE-M3，仅 HTTP 转发回 backend；配套 Flower dashboard + Redis AOF 一键脚本 + `/admin/infra` 健康监控页。见 `analysis-for-backend/celery-module.md` | 已上线 |
| 📋 待办 | **长上下文记忆 Benchmark 评测**（LongMemEval-S） | 用业界公认 500 QA × 5 能力的开源数据集量化 Context Engine v2 三档开关的增量收益：`baseline_off` → `condenser_only` → `condenser_reflect` → `full` → `full_graph` 5 配置矩阵。方案已完整设计（数据下载 / runner / scorer / 报告格式），推荐 B 档 oracle 250 QA × 5 配置，DeepSeek judge，总成本 ~$50 / ¥360、耗时 ~3.5h；当前阻塞于预算。详见 [`plan-doc-dir/长上下文记忆评测·LongMemEval集成计划.md`](plan-doc-dir/长上下文记忆评测·LongMemEval集成计划.md) | 待预算 |
| 🟠 P1 | **JWT 认证 + 多用户支持** | 用户注册/登录，对话和知识库按 `user_id` 隔离，当前无认证是生产化硬伤 | 规划中 |
| 🟡 P2 | **Docker + docker-compose** | 一键启动全部服务（后端 / 前端 / MongoDB / Qdrant / Redis / Celery Worker） | 规划中 |
| 🟡 P2 | **Guardrails 安全防护** | Prompt Injection 检测、PII 过滤，生产系统必要安全层 | 规划中 |
| 🟡 P2 | **后台管理界面接入后端** | 将现有前端 UI Demo 与真实后端对接，支持模型参数持久化配置 | 规划中 |

### 中期方向（架构演进）

- **LangGraph 任务分解图**：复杂多子问题查询自动拆解为并行子任务，各自检索后综合回答，对标 Perplexity Deep Research
- **LangGraph Human-in-the-Loop**：查询意图模糊时暂停执行，向用户反问澄清，再继续
- **长对话记忆 Benchmark 评测循环**：Context Engine v2 已落地；下一步按 `plan-doc-dir/长上下文机制设计v2·集百家之长.md` §14 里程碑（M0-M5）搭自造 memory-mini-set（30 对话 × 180 probe），量化每个 P 阶段上线前后的 recall@turn_gap / update_fidelity / abstention_rate 变化
- **文档入库智能流水线**：根据文档类型（学术 PDF / 财报表格 / 长书籍）动态选择最优分块策略

### 已知局限

- **后台管理界面**：当前仅为前端 UI Demo，所有数据均为 mock，页面配置不影响实际系统行为
- **无认证机制**：任何人可访问所有对话和知识库，不适合多用户生产环境
- **RAG 一击即中**：Classical 路径检索后直接生成；Agentic RAG 档位（见路线图）已提供 grading + rewrite-loop + hallucination-check 自我纠错闭环，需前端开关启用
- **Context Engine v2 默认关**：长对话记忆 / rolling summary / durable memory 三个主开关默认 off（soak 未完成），`CONTEXT_ENGINE_ENABLED` / `MEMORY_REFLECT_ENABLED` / `MEMORY_RETRIEVAL_ENABLED` 按里程碑顺序翻启；只有"服务端 events 真相源"（P1）已翻默认 true。量化 soak 的 LongMemEval-S 评测方案已设计完毕，待预算 ~$50 实跑（见路线图"待办"）
- **Celery 默认关闭**：新特性已落地（`/admin/infra` toggle），但默认 off 保持零破坏；未开启时仍走 `asyncio.to_thread`

---

## 📝 注意事项

- **Embedding 模型**：默认使用 BGE-M3（约 2.27 GB），可在知识库页面的"Embedding 模型配置"中下载并激活。首次使用前需先下载模型，未就绪时上传功能自动禁用。
- **混合检索启用条件**：`VECTOR_STORE_SEARCH_MODE=hybrid`（默认）仅在 Embedding 为 **BGE-M3** 时生效；切到其它模型（bge-base-zh / minilm 等）会**自动降级为 dense-only**（后端会打 warning 日志），无需手动配置。
- **模型切换警告**：切换 Embedding 模型（如 MiniLM → BGE-M3）会因向量维度变化导致 Qdrant 集合自动重建（`QdrantBackend._ensure_collection` 在 init 时检测 dim mismatch 并重建），所有文档需重新向量化。
- **Qdrant 数据保留**：`backend/Qdrant-config-data/storage/` 为 Qdrant 的持久化目录，删除相当于清空知识库。历史遗留的 `backend/data/chroma/` 为 Chroma 迁移前的存档，不再被业务代码读写，可保留也可删除。
- **GPU 加速**：BGE-M3 在 GPU 下推理速度约为 CPU 的 12 倍。需 CUDA 驱动 ≥ 12.4，PyTorch ≥ 2.6.0（cu124 版）。
- **HuggingFace 镜像**：默认通过 `hf-mirror.com` 下载，可在 `.env` 中修改 `HF_ENDPOINT`。
- **支持的文档格式**：PDF、TXT、Markdown (.md)、Word (.docx)、CSV、Excel (.xlsx/.xls)、PowerPoint (.pptx)、EPUB。旧版 `.doc` 格式不支持，请转换为 `.docx` 后上传。
- **联网搜索**：需在 `.env` 中配置有效的 `SERPAPI_API_KEY`，可在 [serpapi.com](https://serpapi.com) 注册获取。
- **代码路由模型**：代码相关问题会切换到 Doubao 代码模型，需在 `.env` 中配置 `ARK_API_KEY`。
- **MongoDB**：请确保 MongoDB 服务已启动，默认连接 `mongodb://localhost:27017`。
- **DeepSeek 思考模式**：仅在选择 DeepSeek 模型时可用，通过 `extra_body` 参数启用原生思考链，不切换模型名称。
- **XML 容错解析**：仅当响应包含 `<content>/<recommend>/<ref>` 等结构标签时才进入 XML 解析；普通 Markdown 响应（含代码块）不做 XML 清洗，避免破坏 fenced code block。XML 解析内部仍保留 sloppy-xml → 正则 → 纯文本的多级降级链路。
- **引用刷新持久化**：`refs` 数据存入 MongoDB，刷新页面后引用角标和参考来源面板完整恢复；`recommend`（推荐追问）为临时态，刷新后不保留。
- **后台管理（Demo）**：后台管理界面当前仅为 UI 预览，所有数据为 mock，页面配置不会影响实际对话行为。
- **天气查询**：需在后端启动前先用 `$env:PORT=8001; python server.py` 启动 `Gaode-weather-MCP-server/`。若未启动则天气查询不可用，其他功能正常。城市编码表（`backend/data/AMap_adcode_citycode.xlsx`）在后端 lifespan 启动时自动加载为内存 dict，无需额外配置。
- **同名多地查询**：输入"朝阳"等存在多个同名行政区的地名时，系统会并行查询所有匹配地区（北京朝阳区、辽宁朝阳市等）并逐一列出天气，无需用户手动消歧义。
