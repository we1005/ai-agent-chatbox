# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

> README.md 是详尽的功能与 API 说明，本文件只记"读多份文件才能拼出的全局规则 / 容易踩的坑"，不重复 README。

## 启动 / 停止

项目是**同时支持 Windows 与 macOS 的双配置**模式。两套互不覆盖。

**macOS（当前主力环境）**
- 一键启动：`bash start-all.sh`（顺序：MongoDB → Qdrant → 天气 MCP → Backend → Frontend，日志聚合到 `logs/`，PID 写入 `logs/pids/`）
- 一键停止：`bash stop-all.sh`（读 PID 文件 → TERM → 6s 超时 KILL → 端口兜底扫描 → 清理 `tail -F` 日志聚合进程）
- 单独启动：`backend/start-mongodb.sh`、`backend/Qdrant-config-data/start-qdrant.sh`、`Gaode-weather-MCP-server/start-mcp-server.sh`
- MongoDB **版本必须匹配数据目录 FCV**：Windows 实测 mongod **8.2.6**（写入 `mongo-data/`，FCV=8.2），macOS Homebrew mongod **8.0.21**（写入 `mongo-data-macos/`，FCV=8.0）。**高版本写的数据低版本打不开**（exitCode 62 "Wrong mongod version"），所以 macOS 独立一份配置 + 独立数据目录。不要共用 `mongo-data/`；要跨平台迁数据就用 `mongodump`/`mongorestore`。
- Qdrant 用独立 `config-macos.yaml`（路径是 POSIX 绝对路径；原 `config.yaml` 是 Windows 的反斜杠路径，**不要改**）

**Windows**：原有 `.bat` / `.ps1` 脚本未动，继续用 `start-all.ps1`、`config.yaml`、`mongo.conf`、`mongo-data/`。

**单个后端开发重启**：直接 `source backend/venv/bin/activate && cd backend && uvicorn main:app --reload --reload-dir app`。`--reload-dir app` 不可省 —— 否则 `data/`、`venv/` 的无关变更也会触发重载。

## 测试

- `backend/tests/test_xml_parser.py`：XML 解析单测。`cd backend && venv/bin/python -m pytest tests/test_xml_parser.py`。
- `tests/e2e-macos/smoke.mjs`：端到端冒烟（Playwright，headless，打 5173 + 浏览器内 fetch 8000）。需服务已起，然后 `node tests/e2e-macos/smoke.mjs`。截图落 `tests/e2e-macos/home.png`。
- 没有 frontend 单测；UI 验证靠 Playwright MCP 或 smoke 脚本。

## 两条聊天路径并存

| 端点 | 模式 | 编排 |
|---|---|---|
| `POST /api/chat/completions` | Classic | `chat_service.py` 里线性流水线：意图识别 → RAG/联网/天气/思考 |
| `POST /api/chat/solo` | Solo（Agentic） | `services/solo/graph.py` LangGraph：`classify_complexity → planner ⇄ tools → END` |

**两条路径完全独立**。Solo 只能开启时走 `/api/chat/solo`（前端顶栏 "Solo" 开关），classic 完全不感知。改动 classic 时不要顺手改 Solo，反之亦然。

**Classic 路径的 intent 路由必须在 `chat.py` 端点层完成，不能下沉到 chat_stream**。原因：`enable_thinking=true` 走 `chat_stream_with_thinking` 这条 parallel 分支会绕过 chat_stream 内部的所有逻辑。intent 路由顺序（`chat.py:event_generator`）：
- `intent=="weather"` → `_handle_weather_query`（无视 thinking，永远走真 MCP）
- `intent=="code" + enable_thinking` → **保 thinking 走 DeepSeek**（沉默地不切 Doubao；语义决定，因 Doubao 代码模型不支持 thinking）
- `enable_thinking + deepseek` → `chat_stream_with_thinking`
- 其它 → `chat_stream(precomputed_intent=...)` 复用前置 intent 结果免二次调用

未来想给 thinking 分支补上 RAG / web / memory 注入，留给 P4 Context Engine Assembler 收敛（v2 §7 P4），别再在 `chat_stream_with_thinking` 里现加。

Solo 下模型被强制切到 DeepSeek（Kimi function calling 稳定性不够）。Solo 的工具定义在 `services/solo/tools.py`，一共 5 个：`search_knowledge_base` / `query_knowledge_base_catalog` / `search_web` / `get_weather` / `request_thinking`。Embedding 未就绪时 `search_knowledge_base` 会从工具列表里剔除并在 prompt 追加 "RAG 不可用"。

## 向量检索架构红线

- **业务代码禁止直接 `import qdrant_client`**。所有向量库操作走 `services/vector_store/base.py` 的抽象层。目前唯一实现是 `qdrant_backend.py`；新增后端只需实现 `VectorStoreBackend` 的 10 个方法。
- **Hybrid 混合检索只在 BGE-M3 下生效**。切到 MiniLM / bge-base-zh 等会**自动降级 dense-only**（`QdrantBackend` 自检），不要手动设 `VECTOR_STORE_SEARCH_MODE=hybrid` 去"强制启用"—— 没有 learned sparse。
- **切换 Embedding 模型会触发 Qdrant 集合重建**（维度变了）。所有已入库文档需要重新向量化。`QdrantBackend._ensure_collection` 在 init 时检测 dim mismatch 自动重建。
- **Sparse 编码器复用 HF 已加载的 transformer**：`bge_m3_sparse.py` 只额外加载 `sparse_linear.pt`（~2KB），不要改成重新实例化 FlagEmbedding（会白占 ~2GB VRAM）。

## 模型生命周期（容易被忽视的 UX 合同）

- **启动时 embedding 模型不自动加载**，即使已缓存。用户必须在 `/knowledge` 页手动点"加载模型"，后端收到 `POST /api/embedding/activate` 才加载到内存。改动 startup 流程时不要"顺手优化"成自动激活 —— 这是产品故意的。
- **Reranker 按需加载/卸载**。`POST /api/embedding/reranker/load` 加载到显存，`/unload` 调用 `torch.cuda.empty_cache()` 释放 ~2.4GB。默认关闭。加载 embedding 时**不会**同时加载 reranker。
- **BGE-M3 下载有断点续传和取消机制**（`embedding_service.py`），前端 SSE 轮询进度。不要改成同步下载。

## Platform-aware 代码点

改这些地方记得覆盖 3 条分支（darwin / win32 / linux）：

- `backend/app/services/embedding_service.py` 的 `get_gpu_info()`：macOS 走 `torch.backends.mps.is_available()`，其它走 `nvidia-smi`。
- `backend/main.py` 的 `MongoUnavailableError` 排查清单：按平台打印不同命令（`bash start-mongodb.sh` vs `start-mongodb.bat`；`lsof -i :27017` vs `netstat -ano | findstr`）。
- `backend/main.py` 里 `_silence_windows_10054` 只在 `sys.platform == "win32"` 下压 `ConnectionResetError`，macOS 无此问题但守卫存在即可。

## 依赖 / 环境坑

- **`beanie >= 2.0` 抛弃了 motor**，数据库层用 `pymongo.AsyncMongoClient`（`backend/app/db/database.py`）。全 backend 只有 `database.py` 里碰 Mongo 驱动；不要再把 `AsyncIOMotorClient` 写回来。
- Python 3.13.13 + venv 在 `backend/venv/`。所有 `.sh` 脚本都 `source backend/venv/bin/activate`。
- `.env` 在 `backend/.env`（git 忽略，不要提交）。关键变量：`MOONSHOT_API_KEY` / `DEEPSEEK_API_KEY` / `ARK_API_KEY` / `SERPAPI_API_KEY` / `HF_ENDPOINT` / `MONGODB_URL` / `QDRANT_URL` / `VECTOR_STORE_SEARCH_MODE`。
- **`data/chroma/` 是历史遗留**（迁 Qdrant 前的存档），业务代码已不读写，别以为它还 live。

## Prompt / 输出格式

- System message 来自 `app/prompts/chat_system.j2`，user message 来自 `chat_query.j2`。RAG 结果 **按源文件分组**注入 `<document index="N">...</document>`，同一文件的多个 chunk 共享一个 index —— LLM 引用时用文件级角标 `<ref>N</ref>`，不是 chunk 级。
- LLM 输出要求包 `<content>...</content><recommend>...</recommend>` 结构。解析走 `services/xml_parser.py`：sloppy-xml → 正则 → 纯文本三级降级。**只在检测到结构标签时**才进入 XML 清洗；普通 Markdown（含 fenced code blocks）不做清洗，避免把 ```` ```python ```` 这种破坏掉。
- Jinja2 里用户内容走 `| e` 过滤器转义，防止 XML 结构被用户输入破坏。

## 会话 / 引用持久化

- `refs`（知识库引用数据）**存 MongoDB**，刷新后恢复角标。
- `recommend`（推荐追问）**不持久化**，刷新即丢 —— 这是故意的，别改。
- 切换/删除会话会 `_abortInFlight` 中止 SSE（前端 `store/chat.ts`），避免 token 污染新会话；running 的 stage/tool_call 被翻为 done。

## Agentic RAG 档位（classic 路径）

- **开关**：`EmbeddingConfig.agentic_rag_mode` 四档 `off / grading_only / grading_rewrite / full`，运行时通过 `/api/embedding/agentic-rag` 切换并持久化到 `backend/data/embedding_config.json`。**默认 off**，改代码时不要"顺手打开"——用户要的是可对比的显式开关。
- **只影响 classic 路径**且 `intent=general + use_knowledge_base=true`。weather/code 短路、Solo 路径完全不动。Solo 启用时前端控件置灰。
- **三节点都在 `backend/app/services/agentic_rag.py`**：`grade_documents` / `rewrite_query_for_retry` / `check_hallucination` + orchestrator `agentic_rag_retrieve`。所有 LLM 调用走 `get_openai()` + `@traceable`，默认关追踪时零开销。
- **失败软着陆是硬约束**：任何节点 LLM 异常 → `logger.warning` + `trace["degraded"]=True` + 降级到 classical 路径继续。**不要**把 fail-soft 改成 fail-hard（体验会崩）。
- **Hallucination check 首版不重生成**：判 unsupported 时在 stream 结尾追加警告 banner，不做 re-retrieve 或 stricter-prompt regenerate。改这个行为前先读 `plan-doc-dir/本项目是否真的实现了Agentic-RAG.md` §失败降级。
- **三件套与启发式 `rewrite_query_if_needed` 互斥**：Agentic 开档位时跳启发式，走 grading-driven 的内部 rewrite。与 Multi-Query 可并存但 rewrite 上限降 1。

## Graph RAG 开关（LightRAG，classic 路径最高优先级）

- **开关**：`EmbeddingConfig.graph_rag_enabled`（bool）+ `graph_rag_query_mode`（naive/local/global/hybrid/mix），通过 `/api/embedding/graph-rag` 运行时切换并持久化到 `backend/data/embedding_config.json`。**默认 off**。
- **启用时覆盖 Agentic + Multi-Query**。前端 `/knowledge` 里两者控件会自动置灰；`chat_service.chat_stream` 按 `if graph_rag_enabled: ... elif use_agentic: ... elif multi_query: ... else: ...` 排优先级。想改优先级顺序前先读 `plan-doc-dir/LightRAG集成落地.md`。
- **仅 retrieve 阶段接入 LightRAG**，生成仍走项目自己的 `self.llm.astream()`——保留 XML `<content>/<recommend>` 管道与引用注入。**不要**改成用 LightRAG 自己的 generate；那样会绕过系统 prompt 与解析器。
- **索引目录 `backend/data/lightrag/`**（已 gitignore）。构图代价大：每 chunk 跑 LLM 抽实体，单篇文档约 $2-5。前端构建按钮有二次确认 + 成本提示。LightRAG 原生有 LLM cache，重建几乎免费。
- **适配层硬约束**（`backend/app/services/graph_rag.py`）：embedding 维度硬编码 1024（BGE-M3 / bge-large-zh-v1.5），切其它模型要同步改 `_DEFAULT_EMBEDDING_DIM`。
- **失败软着陆**：索引空 / LightRAG 异常 / 超时 15s → `logger.warning` + `trace["degraded"]=True` → fall through 到 agentic / multi-query / classical。**不要**把 fail-soft 改成 raise。
- **Solo 路径不受影响**：Solo 走独立 `/api/chat/solo` 端点；前端 Solo ON 时 Graph RAG 控件同样置灰。
- **Hallucination check 跳过**：Graph RAG 接管时不跑 `check_hallucination`（LightRAG 的 context 已经是 entity/community 聚合结构，直接套语义对不上且双倍成本）。

## LangSmith 可观测性

- **默认关闭**：`backend/.env` 里 `LANGSMITH_TRACING=false` 时所有 `get_openai()` 工厂和 `@traceable` 装饰器**零开销空转**，不 import langsmith、不发网络调用。改代码时别"顺手"把它默认打开。
- **不要直接写 `AsyncOpenAI(...)`**。所有直连 DeepSeek 的地方统一走 `app/services/_langsmith.py:get_openai(...)` —— 这样未来 LangSmith 升级或换 observability 方案只改一处。AsyncArk（Doubao）例外，因为它不兼容 OpenAI SDK 接口，走 `@traceable` 路径。
- **metadata 注入**：classic 的 `chat_stream` 里用 `attach_run_metadata(...)` 挂 `model / intent / use_*` 等业务维度；Solo 在 `api/endpoints/solo.py` 的 `graph.astream_events(config=...)` 里通过 `config["metadata"]` 传 `conversation_id / model / mode` —— LangChain 的 config 会自动顺着 StateGraph 传播到每个节点。
- 详细设计见 `plan-doc-dir/集成LangSmith可观测性.md`。

## MCP

项目内 `.mcp.json` 配置了 Playwright MCP（`npx -y @playwright/mcp@latest`），用于前端可视化验证。首次会话需重启 Claude Code 加载其工具。浏览器内核已 `npx playwright install` 全套（~1.1 GB 缓存在 `~/Library/Caches/ms-playwright/`）。

天气 MCP 是业务依赖（`Gaode-weather-MCP-server/`，端口 8001，FastMCP SSE）。后端 lifespan 会连它；连不上只是天气查询不可用，后端照常启动。

## Cursor 规则（仅供参考）

`.cursor/rules/qa-log.mdc` 是 **Cursor Ask 模式专用规则**（写 `QA/问题浓缩.md` 问答记录），**Claude Code 不适用**。遇到用户在 Claude Code 里问概念性问题，不要主动往 `QA/` 写 —— 等用户明说再写。
