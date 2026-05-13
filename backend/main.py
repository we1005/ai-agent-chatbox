import asyncio
import logging
import logging.config
import os
import sys
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.api import api_router
from app.db.database import init_db, MongoUnavailableError

# ── 全局日志配置 ──────────────────────────────────────────────────────
logging.config.dictConfig({
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "default": {
            "format": "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
            "datefmt": "%H:%M:%S",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "default",
            "stream": "ext://sys.stdout",
        },
    },
    "root": {
        "level": "INFO",
        "handlers": ["console"],
    },
    # 把自己项目的日志设为 DEBUG，方便排查
    "loggers": {
        "app": {"level": "DEBUG", "propagate": True},
        "main": {"level": "DEBUG", "propagate": True},
        "uvicorn.error": {"level": "INFO"},
        "uvicorn.access": {"level": "INFO"},
    },
})

logger = logging.getLogger(__name__)


def _silence_windows_10054(loop: asyncio.AbstractEventLoop, context: dict) -> None:
    exc = context.get("exception")
    if sys.platform == "win32" and isinstance(exc, ConnectionResetError):
        return
    loop.default_exception_handler(context)


async def _auto_initialize_rag() -> None:
    """
    启动时仅检查模型是否存在，不自动加载到 GPU/内存。
    用户需在知识库管理界面手动点击"加载模型"按钮来激活。
    """
    from app.services.embedding_service import _is_bge_m3_cached, get_config, BGE_M3_LOCAL_PATH

    config = get_config()
    logger.info(
        f"[startup] Embedding config: mode={config.mode}, "
        f"local_model={config.local_model}, use_gpu={config.use_gpu}"
    )

    if config.mode == "local":
        cached = _is_bge_m3_cached()
        logger.info(f"[startup] BGE-M3 cache check → {cached} (path: {BGE_M3_LOCAL_PATH})")
        if cached:
            logger.info(
                "[startup] BGE-M3 found but NOT loaded. "
                "User can activate it via Knowledge Base settings."
            )
        else:
            logger.warning(
                "[startup] BGE-M3 not cached locally. "
                "User needs to download it first via the Knowledge Base settings."
            )


async def _recover_stuck_vectorizations() -> None:
    """
    启动时检查 MongoDB 中处于 'processing' 状态的文档记录。
    只在 Embedding 服务就绪时才恢复（无法向量化则跳过）。
    """
    from app.models.knowledge_document import KnowledgeDocument
    from app.services.rag_service import get_rag_service, UPLOAD_DIR

    rag = get_rag_service()
    if not rag.is_ready():
        logger.info("Embedding service not ready, skipping vectorization recovery.")
        return

    stuck = await KnowledgeDocument.find(
        KnowledgeDocument.vectorize_status == "processing"
    ).to_list()

    if not stuck:
        return

    logger.warning(
        f"Found {len(stuck)} document(s) stuck in 'processing' state, recovering..."
    )

    # Celery 开启时，先查 Redis 队列里还在/已在跑的任务，不要重复入队
    from app.services import embedding_service as _emb
    celery_on = _emb.get_config().celery_enabled
    active_task_ids: set[str] = set()
    if celery_on:
        try:
            from app.workers.celery_app import celery_app
            insp = celery_app.control.inspect(timeout=2)
            for bucket in ("active", "reserved", "scheduled"):
                per_worker = getattr(insp, bucket)() or {}
                for tasks_on_worker in per_worker.values():
                    for t in tasks_on_worker:
                        tid = t.get("id")
                        if tid:
                            active_task_ids.add(tid)
            logger.info(
                f"[recovery] celery on · {len(active_task_ids)} task(s) still alive in queue"
            )
        except Exception as e:
            logger.warning(f"[recovery] celery inspect failed ({e}); fall back to re-enqueue all")

    for doc in stuck:
        file_path = os.path.join(UPLOAD_DIR, doc.file_id)
        if not os.path.exists(file_path):
            doc.vectorize_status = "failed"
            doc.error_message = "服务重启时文件已丢失，无法恢复向量化。"
            await doc.save()
            logger.warning(f"File missing on disk, marked failed: {doc.file_id}")
            continue

        # Celery 开启时：如果该 doc 的 celery_task_id 还在 queue/active，不要重复入队
        if celery_on and doc.celery_task_id and doc.celery_task_id in active_task_ids:
            logger.info(
                f"[recovery] skip {doc.file_id} · celery task {doc.celery_task_id} still alive"
            )
            continue

        doc.vectorize_status = "pending"
        doc.celery_task_id = None
        await doc.save()

        if celery_on:
            try:
                from app.workers.tasks import vectorize_document as _celery_task
                ar = _celery_task.delay(doc.file_id)
                doc.celery_task_id = ar.id
                await doc.save()
                logger.info(f"[recovery] re-enqueued to celery: {doc.file_id} task={ar.id}")
                continue
            except Exception as e:
                logger.warning(f"[recovery] celery enqueue failed ({e}); fallback asyncio")

        asyncio.create_task(rag._vectorize_document(doc.file_id))
        logger.info(f"Re-queued vectorization for: {doc.file_id} ({doc.original_name})")


def _setup_langsmith_env() -> None:
    """把 Settings.LANGSMITH_* 推到 os.environ，让 langsmith SDK / LangChain 自动追踪生效。

    仅当 LANGSMITH_TRACING 为真且 API key 非空时启用；否则**不**写任何 env，
    保证 fresh install 下 SDK 走静默路径、零网络调用。
    """
    from app.core.config import get_settings as _get_settings
    s = _get_settings()
    if not s.LANGSMITH_TRACING:
        logger.info("[startup] LangSmith tracing: disabled")
        return
    if not s.LANGSMITH_API_KEY:
        logger.warning(
            "[startup] LANGSMITH_TRACING=true 但 LANGSMITH_API_KEY 为空，已跳过启用。"
        )
        return
    os.environ["LANGSMITH_TRACING"] = "true"
    os.environ["LANGSMITH_API_KEY"] = s.LANGSMITH_API_KEY
    os.environ["LANGSMITH_PROJECT"] = s.LANGSMITH_PROJECT
    os.environ["LANGSMITH_ENDPOINT"] = s.LANGSMITH_ENDPOINT
    logger.info(
        f"[startup] LangSmith tracing: ENABLED → project={s.LANGSMITH_PROJECT} "
        f"endpoint={s.LANGSMITH_ENDPOINT}"
    )


@asynccontextmanager
async def lifespan(app: FastAPI):
    asyncio.get_running_loop().set_exception_handler(_silence_windows_10054)

    # 先设置 LangSmith 环境变量，让后续的 LangChain / langsmith SDK 初始化时读到
    _setup_langsmith_env()

    # MongoDB 是硬依赖——连不上就没必要继续启动，清晰报错后优雅退出
    try:
        await init_db()
    except MongoUnavailableError as e:
        logger.error("=" * 70)
        logger.error("[startup] MongoDB 连接失败，后端启动终止。")
        logger.error(f"          {e}")
        logger.error("          排查清单：")
        if sys.platform == "darwin":
            logger.error("            1. MongoDB 服务是否启动？（macOS: bash backend/start-mongodb.sh）")
            logger.error("            2. 进程是否监听 27017？（lsof -i :27017）")
        elif sys.platform == "win32":
            logger.error("            1. MongoDB 服务是否启动？（Windows: 双击 backend/start-mongodb.bat）")
            logger.error("            2. 进程是否监听 27017？（netstat -ano | findstr 27017）")
        else:
            logger.error("            1. MongoDB 服务是否启动？")
            logger.error("            2. 进程是否监听 27017？（ss -lntp | grep 27017）")
        logger.error("            3. .env 中 MONGODB_URL / MONGODB_DB_NAME 是否正确？")
        logger.error("=" * 70)
        # 直接 SystemExit 终止进程，避免 FastAPI 还起 HTTP 监听造成误导
        raise SystemExit(1)

    await _auto_initialize_rag()
    await _recover_stuck_vectorizations()

    # 加载城市编码表（内存 dict，一次性读取 Excel）
    from app.services.weather_service import init_city_data
    init_city_data("data/AMap_adcode_citycode.xlsx")

    # 连接天气 MCP Server（需提前以 PORT=8001 启动 Gaode-weather-MCP-server/server.py）
    # MCP 非硬依赖，连不上仅禁用天气查询，后端照常工作
    from app.services.weather_service import init_weather_mcp, shutdown_weather_mcp
    try:
        await init_weather_mcp("http://127.0.0.1:8001/sse")
    except Exception as e:
        logger.warning(f"[Weather] MCP Server 连接失败，天气查询功能暂不可用: {e}")

    yield

    await shutdown_weather_mcp()


app = FastAPI(title="Knowledge Base Chatbox", lifespan=lifespan)


origins = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Internal endpoint guard ─────────────────────────────────────────
# /api/internal/* 仅允许本机 + Docker gateway 访问，用于 Celery worker 容器回调。
# 不暴露给浏览器 / 公网；绑定 IP 即是安全边界，无需鉴权。
@app.middleware("http")
async def _guard_internal_endpoints(request, call_next):
    from fastapi.responses import JSONResponse
    if request.url.path.startswith("/api/internal"):
        client_ip = request.client.host if request.client else ""
        # macOS/Windows Docker Desktop 用 192.168.65.x / 172.x.x.x 作为 gateway；
        # Linux Docker 常见 172.17.0.x / 172.18.0.x。粗粒度白名单所有 172.x + 192.168.x。
        allowed = (
            client_ip in ("127.0.0.1", "::1", "localhost")
            or client_ip.startswith("172.")
            or client_ip.startswith("192.168.")
            or client_ip.startswith("10.")
        )
        if not allowed:
            return JSONResponse(
                status_code=403,
                content={"detail": f"Internal endpoint not accessible from {client_ip}"},
            )
    return await call_next(request)


app.include_router(api_router, prefix="/api")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
