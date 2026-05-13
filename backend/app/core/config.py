from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache


class Settings(BaseSettings):
    MOONSHOT_API_KEY: str
    DEEPSEEK_API_KEY: str
    ARK_API_KEY: str = ""
    # 阿里云百炼（DashScope）—— OpenAI 兼容端点；用于接入 Qwen 系列
    # base_url: https://dashscope.aliyuncs.com/compatible-mode/v1
    DASHSCOPE_API_KEY: str = ""
    SERPAPI_API_KEY: str = ""
    HF_ENDPOINT: str = "https://hf-mirror.com"
    MONGODB_URL: str = "mongodb://localhost:27017"
    MONGODB_DB_NAME: str = "chatbox"

    # Vector store (Qdrant)
    QDRANT_URL: str = "http://localhost:6333"
    QDRANT_COLLECTION: str = "kb_main"
    QDRANT_API_KEY: str = ""
    VECTOR_STORE_SEARCH_MODE: str = "dense"        # dense | hybrid（默认 dense，即传统 RAG；运行时可通过前端开关或 /api/embedding/search-mode 切换）
    VECTOR_STORE_HYBRID_FUSION: str = "rrf"        # rrf | dbsf
    VECTOR_STORE_RECALL_K: int = 20                # reranker 前候选数
    VECTOR_STORE_TOP_K: int = 4                    # 无 reranker 时直接返回的数量

    # Context Engine v2 · P1.2/P1.3 · 服务端上下文主权 feature flag
    # 开启后 chat_stream 按 conversation_id 从 events 集合重建 history，
    # 忽略前端 request.messages[:-1]；当前轮 user query 仍从 messages 末尾取。
    # **默认 true**：P1.3 已 backfill 所有存量 conversations 到 events 集合
    # （见 backend/scripts/backfill_events_from_messages.py）。
    # 留开关是为了紧急回滚——万一 events 读路径出 bug 可设 false 暂时降级。
    # 见 plan-doc-dir/长上下文机制设计v2·集百家之长.md §7 P1.3 / §4 原则 9。
    CHAT_REBUILD_HISTORY_FROM_EVENTS: bool = True

    # Context Engine v2 · P2.3 · Condenser Pipeline 开关
    # 开启后：chat_stream 调 Condenser Pipeline（Recent Buffer + LLM Summary）
    # 对 events 做投影，而不是直接全量喂 LLM。默认 off —— LLM summary 每次
    # compaction 会额外调一次 DeepSeek-chat（~$0.002），先跑一段 soak
    # 验证效果再翻默认值。关闭此开关时 chat_stream 仍走 P1.2 的朴素 rebuild 路径。
    # 见 plan-doc-dir/长上下文机制设计v2·集百家之长.md §7 P2。
    CONTEXT_ENGINE_ENABLED: bool = False

    # 上下文窗口参数（供 Condenser Pipeline 使用，CONTEXT_ENGINE_ENABLED=true 生效）
    CONTEXT_RECENT_TURNS: int = 5            # 最近 N 轮原文保护
    CONTEXT_SUMMARY_MAX_SIZE: int = 20       # body > 该值触发 LLM 摘要
    CONTEXT_SUMMARY_KEEP_FIRST: int = 1      # 始终保头几条（锚定任务）

    # Context Engine v2 · P3 · Durable Memory 开关
    # 开启后：chat_stream 流完、向用户返回 [DONE] 之后，后台 asyncio.create_task
    # 调用 memory_service.reflect_and_write 让 mem0 做 LLM-mediated 的
    # ADD/UPDATE/DELETE judge。每 N 轮 debounce（避免每轮都烧 LLM）。
    # 默认 off —— mem0 装好但运行时开关，先跑 soak 再翻默认值。
    # 见 plan-doc-dir/长上下文机制设计v2·集百家之长.md §7 P3.2 / §6.3。
    MEMORY_REFLECT_ENABLED: bool = False
    MEMORY_REFLECT_DEBOUNCE_TURNS: int = 3
    MEMORY_REFLECT_BG_QUEUE_LIMIT: int = 50

    # P3.3 · Memory 检索注入（启用后 Context Router 规则命中时把 top-K memory
    # 作为 system message 注入 View）。默认 off；需 MEMORY_REFLECT_ENABLED=true
    # 才有意义（没写入就检索不到）。
    MEMORY_RETRIEVAL_ENABLED: bool = False
    MEMORY_RETRIEVAL_TOP_K: int = 5

    # 工具链 LLM（意图识别 / 改写 / Condenser / Agentic RAG / Multi-Query / Solo 复杂度）
    # 默认 fallback 到 DeepSeek；改为 DashScope URL + DASHSCOPE_API_KEY + qwen3.5-flash 可整体切换
    UTILITY_LLM_BASE_URL: str = "https://api.deepseek.com/v1"
    UTILITY_LLM_API_KEY: str = ""    # 空时 fallback 到 DEEPSEEK_API_KEY
    UTILITY_LLM_MODEL: str = "deepseek-chat"

    # LangSmith 可观测性（默认关闭）
    # 设计见 plan-doc-dir/集成LangSmith可观测性.md
    LANGSMITH_TRACING: bool = False
    LANGSMITH_API_KEY: str = ""
    LANGSMITH_PROJECT: str = "chatbox-dev"
    LANGSMITH_ENDPOINT: str = "https://api.smith.langchain.com"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


@lru_cache()
def get_settings():
    return Settings()
