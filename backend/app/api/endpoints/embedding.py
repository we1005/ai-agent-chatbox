"""
Embedding 管理 API 端点。
"""
import asyncio
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.services import embedding_service as svc

router = APIRouter()


# ── Request / Response 模型 ───────────────────────────────────────────

class EmbeddingConfigUpdate(BaseModel):
    mode: str | None = None
    local_model: str | None = None
    use_gpu: bool | None = None
    online_provider: str | None = None
    online_api_key: str | None = None


# ── 接口 ─────────────────────────────────────────────────────────────

@router.get("/embedding/system-info")
async def get_system_info():
    """返回 GPU 硬件状态、PyTorch CUDA 状态、本地模型下载状态、当前配置、模型是否已加载。"""
    from app.services.rag_service import get_rag_service
    gpu = await asyncio.to_thread(svc.get_gpu_info)
    models = await asyncio.to_thread(svc.get_model_status)
    config = svc.get_config()
    rag = get_rag_service()
    return {
        "gpu": gpu,
        "local_models": models,
        "current_config": {
            "mode": config.mode,
            "local_model": config.local_model,
            "use_gpu": config.use_gpu,
            "online_provider": config.online_provider,
        },
        "embedding_ready": rag.is_ready(),
        "reranker_loaded": rag.is_ready() and rag.reranker is not None,
    }


@router.get("/embedding/config")
async def get_config():
    """获取当前 Embedding 配置。"""
    from dataclasses import asdict
    return asdict(svc.get_config())


@router.put("/embedding/config")
async def update_config(body: EmbeddingConfigUpdate):
    """
    更新 Embedding 配置，并重新初始化 RagService。
    注意：切换模型时如果维度变化，会自动清空 ChromaDB 并重置所有文档状态。
    """
    from app.services.rag_service import get_rag_service

    old_config = svc.get_config()
    new_config = svc.get_config()

    if body.mode is not None:
        new_config.mode = body.mode
    if body.local_model is not None:
        new_config.local_model = body.local_model
    if body.use_gpu is not None:
        new_config.use_gpu = body.use_gpu
    if body.online_provider is not None:
        new_config.online_provider = body.online_provider
    if body.online_api_key is not None:
        new_config.online_api_key = body.online_api_key

    # 检查是否需要清空 ChromaDB（维度变化时）
    old_dim = svc.MODEL_DIMENSIONS.get(old_config.local_model, 0)
    new_dim = svc.MODEL_DIMENSIONS.get(new_config.local_model, 0)
    needs_reset = (old_dim != new_dim and old_dim != 0 and new_dim != 0)

    svc.save_config(new_config)

    rag = get_rag_service()

    if needs_reset:
        await rag.reset_for_model_switch()

    try:
        await asyncio.to_thread(rag.initialize, new_config)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"初始化 Embedding 失败：{e}")

    return {
        "message": "配置已更新",
        "needs_revectorize": needs_reset,
        "config": {
            "mode": new_config.mode,
            "local_model": new_config.local_model,
            "use_gpu": new_config.use_gpu,
        },
    }


@router.post("/embedding/download")
async def start_download(resume: bool = True):
    """
    触发 BGE-M3 后台下载，立即返回，进度通过 /download/status 轮询。
    resume=true（默认）：断点续传；resume=false：清空重新下载。
    """
    result = await svc.start_download_bge_m3(resume=resume)
    return result


@router.post("/embedding/download/cancel")
async def cancel_download():
    """请求停止下载（完成当前文件后暂停，状态变为 paused）。"""
    return svc.cancel_download()


@router.get("/embedding/download/status")
async def download_status():
    """查询模型下载进度（含速度、已下载大小、状态）。"""
    return svc.get_download_state()


@router.get("/embedding/rag-strategy")
async def get_rag_strategy():
    """
    返回当前 RAG 检索策略：
      - reranker_downloaded: Reranker 模型是否已下载到本地
      - reranker_loaded: Reranker 是否已加载到内存（RagService.reranker is not None）
      - strategy: "recall+rerank" | "recall_only"
      - recall_k: 向量召回数量
      - rerank_top_n: Reranker 精排后输出数量
    """
    from app.services.rag_service import get_rag_service
    reranker_downloaded = svc._is_reranker_cached()
    rag = get_rag_service()
    reranker_loaded = rag.is_ready() and rag.reranker is not None
    strategy = "recall+rerank" if reranker_loaded else "recall_only"
    recall_k = 20 if reranker_loaded else 4
    return {
        "reranker_downloaded": reranker_downloaded,
        "reranker_loaded": reranker_loaded,
        "strategy": strategy,
        "recall_k": recall_k,
        "rerank_top_n": 4,
    }


class SearchModeUpdate(BaseModel):
    mode: str  # "dense" | "hybrid"


@router.get("/embedding/search-mode")
async def get_search_mode():
    """查询当前运行时的召回模式（dense / hybrid），以及当前 embedding 是否支持 sparse。"""
    from app.services.rag_service import get_rag_service

    rag = get_rag_service()
    sparse_supported = bool(rag.backend and rag.backend.supports_sparse()) if rag.is_ready() else False
    return {
        "mode": rag.search_mode,
        "sparse_supported": sparse_supported,
        "embedding_ready": rag.is_ready(),
    }


@router.put("/embedding/search-mode")
async def update_search_mode(body: SearchModeUpdate):
    """运行时切换召回模式。默认 dense（传统 RAG）；切到 hybrid 时若模型不支持 sparse 会自动降级。"""
    from app.services.rag_service import get_rag_service

    if body.mode not in ("dense", "hybrid"):
        raise HTTPException(status_code=400, detail=f"Invalid mode: {body.mode!r}，可选 dense | hybrid")

    rag = get_rag_service()
    rag.set_search_mode(body.mode)

    sparse_supported = bool(rag.backend and rag.backend.supports_sparse()) if rag.is_ready() else False
    effective_mode = body.mode if sparse_supported else "dense"
    return {
        "mode": rag.search_mode,
        "effective_mode": effective_mode,
        "sparse_supported": sparse_supported,
        "message": (
            f"检索模式已切换为 {body.mode}"
            + ("（当前模型不支持 sparse，实际仍走 dense）" if body.mode == "hybrid" and not sparse_supported else "")
        ),
    }


class MultiQueryUpdate(BaseModel):
    enabled: bool


@router.get("/embedding/multi-query")
async def get_multi_query():
    """查询 Multi-Query 多路召回开关状态。"""
    from app.services.rag_service import get_rag_service
    rag = get_rag_service()
    return {
        "enabled": rag.multi_query_enabled,
        "embedding_ready": rag.is_ready(),
    }


@router.put("/embedding/multi-query")
async def update_multi_query(body: MultiQueryUpdate):
    """运行时切换 Multi-Query 多路召回。开启后每次检索额外一次 LLM 调用生成 3 个 variant。"""
    from app.services.rag_service import get_rag_service
    rag = get_rag_service()
    rag.set_multi_query_enabled(body.enabled)
    return {
        "enabled": rag.multi_query_enabled,
        "message": "Multi-Query 已启用" if body.enabled else "Multi-Query 已关闭",
    }


class AgenticRagUpdate(BaseModel):
    mode: str  # "off" | "grading_only" | "grading_rewrite" | "full"


_AGENTIC_MODE_DESCRIPTIONS = {
    "off": "关闭，走现有 classical RAG（含启发式 rewrite 或 Multi-Query，不变）",
    "grading_only": "仅 Document Grading：检索后 LLM 评分过滤不相关文档",
    "grading_rewrite": "Grading + Rewrite-and-retry：通过率低时改写 query 重试（最多 2 次）",
    "full": "完整 CRAG：Grading + Rewrite + Hallucination Check（答案缺支撑时挂警告）",
}


@router.get("/embedding/agentic-rag")
async def get_agentic_rag_mode():
    """查询 Agentic RAG 档位。仅 classic 路径生效，Solo 模式自带 agentic 行为不受此开关影响。"""
    from app.services.rag_service import get_rag_service
    rag = get_rag_service()
    return {
        "mode": rag.agentic_rag_mode,
        "allowed_modes": list(_AGENTIC_MODE_DESCRIPTIONS.keys()),
        "descriptions": _AGENTIC_MODE_DESCRIPTIONS,
        "embedding_ready": rag.is_ready(),
    }


@router.put("/embedding/agentic-rag")
async def update_agentic_rag_mode(body: AgenticRagUpdate):
    """运行时切换 Agentic RAG 档位并持久化。非法 mode 返回 400。
    详见 plan-doc-dir/本项目是否真的实现了Agentic-RAG.md。"""
    from app.services.rag_service import get_rag_service
    if body.mode not in _AGENTIC_MODE_DESCRIPTIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid mode: {body.mode!r}. Allowed: {list(_AGENTIC_MODE_DESCRIPTIONS.keys())}",
        )
    rag = get_rag_service()
    rag.set_agentic_rag_mode(body.mode)
    return {
        "mode": rag.agentic_rag_mode,
        "message": f"Agentic RAG 档位切换为：{body.mode}（{_AGENTIC_MODE_DESCRIPTIONS[body.mode]}）",
    }


_GRAPH_RAG_QUERY_MODE_DESCRIPTIONS = {
    "naive": "纯向量检索（LightRAG 内置 vector search，不走图）",
    "local": "从单实体邻域展开，适合聚焦具体对象的多跳查询",
    "global": "社区级聚合，适合跨文档主题性 / 趋势性问题",
    "hybrid": "local + global 合并，推荐默认档",
    "mix": "naive + hybrid 融合，最高覆盖率但成本最大",
}


class GraphRagUpdate(BaseModel):
    enabled: bool | None = None
    query_mode: str | None = None


@router.get("/embedding/graph-rag")
async def get_graph_rag():
    """查询 Graph RAG（LightRAG）开关与查询模式。默认 off。"""
    from app.services.rag_service import get_rag_service
    rag = get_rag_service()
    return {
        "enabled": rag.graph_rag_enabled,
        "query_mode": rag.graph_rag_query_mode,
        "allowed_modes": list(_GRAPH_RAG_QUERY_MODE_DESCRIPTIONS.keys()),
        "descriptions": _GRAPH_RAG_QUERY_MODE_DESCRIPTIONS,
        "embedding_ready": rag.is_ready(),
    }


@router.put("/embedding/graph-rag")
async def update_graph_rag(body: GraphRagUpdate):
    """运行时切换 Graph RAG 开关与查询模式并持久化。启用时覆盖 Agentic / Multi-Query。

    详见 plan-doc-dir/LightRAG集成落地.md。
    """
    from app.services.rag_service import get_rag_service
    rag = get_rag_service()
    if body.query_mode is not None:
        if body.query_mode not in _GRAPH_RAG_QUERY_MODE_DESCRIPTIONS:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"Invalid query_mode: {body.query_mode!r}. "
                    f"Allowed: {list(_GRAPH_RAG_QUERY_MODE_DESCRIPTIONS.keys())}"
                ),
            )
        rag.set_graph_rag_query_mode(body.query_mode)
    if body.enabled is not None:
        rag.set_graph_rag_enabled(body.enabled)
    return {
        "enabled": rag.graph_rag_enabled,
        "query_mode": rag.graph_rag_query_mode,
        "message": (
            f"Graph RAG 已{'启用' if rag.graph_rag_enabled else '关闭'}"
            f"（模式：{rag.graph_rag_query_mode}）"
        ),
    }


# ── Graph RAG 索引构建 / 统计 / 清空 ────────────────────────────────

# 进程内简单状态字典（单实例够用；多 worker 时由 --workers 1 兜底）
_graph_rag_build_state: dict[str, object] = {
    "status": "idle",          # idle | running | done | error
    "phase": None,             # start | processing | done | error
    "total": 0,
    "processed": 0,
    "current_doc": None,
    "errors": [],
    "started_at": None,
    "finished_at": None,
    "message": None,
}


class GraphRagClearBody(BaseModel):
    confirm: bool = False


async def _run_build_task():
    """后台任务体：推进度到 _graph_rag_build_state。"""
    import time
    from app.services import graph_rag as gr
    from app.services.rag_service import get_rag_service

    rag = get_rag_service()
    _graph_rag_build_state.update(
        status="running", phase="start", processed=0, total=0,
        current_doc=None, errors=[], started_at=time.time(),
        finished_at=None, message=None,
    )

    async def _cb(evt: dict):
        _graph_rag_build_state.update(
            phase=evt.get("phase"),
            total=evt.get("total", _graph_rag_build_state["total"]),
            processed=evt.get("processed", _graph_rag_build_state["processed"]),
            current_doc=evt.get("current_doc", _graph_rag_build_state.get("current_doc")),
        )
        if evt.get("errors") is not None:
            _graph_rag_build_state["errors"] = evt["errors"]

    try:
        result = await gr.build_graph_index(rag, progress_callback=_cb)
        _graph_rag_build_state.update(
            status="done", phase="done", finished_at=time.time(),
            message=f"索引构建完成：处理 {result['processed']}/{result['total']}，错误 {len(result['errors'])} 项",
        )
    except Exception as e:
        logger = __import__("logging").getLogger(__name__)
        logger.exception("Graph RAG build task failed")
        _graph_rag_build_state.update(
            status="error", phase="error", finished_at=time.time(),
            message=f"构建失败：{e}",
        )


@router.post("/embedding/graph-rag/build")
async def start_graph_rag_build():
    """触发 LightRAG 索引构建（后台执行）。进度通过 /graph-rag/build/status 轮询。

    Embedding 未激活返回 503；已有任务运行中返回 409。
    """
    from app.services.rag_service import get_rag_service
    rag = get_rag_service()
    if not rag.is_ready():
        raise HTTPException(
            status_code=503,
            detail={"code": "EMBEDDING_NOT_READY", "message": "请先激活 Embedding 模型"},
        )
    if _graph_rag_build_state.get("status") == "running":
        raise HTTPException(
            status_code=409,
            detail={"code": "ALREADY_RUNNING", "message": "Graph RAG 构建任务已在运行"},
        )
    asyncio.create_task(_run_build_task())
    return {"status": "started", "message": "Graph RAG 索引构建已启动，请轮询进度"}


@router.get("/embedding/graph-rag/build/status")
async def graph_rag_build_status():
    """查询 Graph RAG 构建进度。"""
    return dict(_graph_rag_build_state)


@router.get("/embedding/graph-rag/stats")
async def graph_rag_stats():
    """返回 LightRAG 图统计：节点数 / 边数 / 文档数 / 索引目录路径。"""
    from app.services import graph_rag as gr
    return gr.get_graph_stats()


@router.post("/embedding/graph-rag/clear")
async def clear_graph_rag(body: GraphRagClearBody):
    """清空 Graph RAG 索引目录。必须 confirm=true。不影响 Qdrant / Mongo。"""
    if not body.confirm:
        raise HTTPException(
            status_code=400,
            detail={"code": "CONFIRM_REQUIRED", "message": "清空操作需要显式 confirm=true"},
        )
    if _graph_rag_build_state.get("status") == "running":
        raise HTTPException(
            status_code=409,
            detail={"code": "BUILD_RUNNING", "message": "正在构建，无法清空"},
        )
    from app.services import graph_rag as gr
    result = await gr.clear_graph_index()
    _graph_rag_build_state.update(
        status="idle", phase=None, total=0, processed=0,
        current_doc=None, errors=[], started_at=None, finished_at=None,
        message="索引已清空",
    )
    return result


@router.post("/embedding/reranker/load")
async def load_reranker():
    """显式加载 BGE-Reranker-v2-m3 到显存。Embedding 未就绪或模型未下载时返回 4xx。"""
    from app.services.rag_service import get_rag_service

    rag = get_rag_service()
    if not rag.is_ready():
        raise HTTPException(
            status_code=503,
            detail={
                "code": "EMBEDDING_NOT_READY",
                "message": "Embedding 模型未加载，请先加载 Embedding 模型。",
            },
        )
    if not svc._is_reranker_cached():
        raise HTTPException(
            status_code=400,
            detail="BGE-Reranker 模型未下载，无法加载。",
        )

    config = svc.get_config()
    ok = await asyncio.to_thread(rag.load_reranker, config.use_gpu)
    if not ok:
        raise HTTPException(status_code=500, detail="Reranker 加载失败，详见后端日志。")
    return {"message": "Reranker 已加载", "reranker_loaded": True}


@router.post("/embedding/reranker/unload")
async def unload_reranker():
    """卸载 Reranker 并释放显存。"""
    from app.services.rag_service import get_rag_service

    rag = get_rag_service()
    await asyncio.to_thread(rag.unload_reranker)
    return {"message": "Reranker 已卸载", "reranker_loaded": False}


# ═══════════════════════════════════════════════════════════════════
# Celery 异步向量化开关（默认 off · 本地 Redis + Docker worker）
# ═══════════════════════════════════════════════════════════════════

class CeleryUpdate(BaseModel):
    enabled: bool


def _check_celery_health() -> dict:
    """探测 Redis ping + Celery worker 是否就绪。

    返回结构：
      {
        "redis":  {"ok": bool, "ping_ms": float, "error": str|None},
        "celery": {"ok": bool, "workers": int, "worker_names": list[str], "error": str|None},
        "flower": {"ok": bool, "url": str, "error": str|None}
      }
    纯诊断，不改任何配置。
    """
    import time
    health = {
        "redis": {"ok": False, "ping_ms": None, "error": None},
        "celery": {"ok": False, "workers": 0, "worker_names": [], "error": None},
        "flower": {"ok": False, "url": "http://localhost:5555", "error": None},
    }

    # ── Redis ping ──────────────────────────────────
    try:
        import redis as _redis
        from app.workers.celery_app import BROKER_URL
        r = _redis.Redis.from_url(BROKER_URL, socket_connect_timeout=2)
        t0 = time.monotonic()
        r.ping()
        health["redis"]["ping_ms"] = round((time.monotonic() - t0) * 1000, 1)
        health["redis"]["ok"] = True
    except Exception as e:
        health["redis"]["error"] = f"{type(e).__name__}: {e}"

    # ── Celery worker inspect ──────────────────────────
    try:
        from app.workers.celery_app import celery_app
        insp = celery_app.control.inspect(timeout=2)
        pong = insp.ping() or {}
        worker_names = list(pong.keys())
        health["celery"]["workers"] = len(worker_names)
        health["celery"]["worker_names"] = worker_names
        health["celery"]["ok"] = len(worker_names) > 0
        if not worker_names:
            health["celery"]["error"] = "no workers alive"
    except Exception as e:
        health["celery"]["error"] = f"{type(e).__name__}: {e}"

    # ── Flower HTTP（docker 开启时可达 5555）────────
    try:
        import requests
        resp = requests.get("http://localhost:5555/api/workers",
                            auth=("admin", "xuanjian"), timeout=1)
        health["flower"]["ok"] = resp.status_code == 200
        if resp.status_code != 200:
            health["flower"]["error"] = f"HTTP {resp.status_code}"
    except Exception as e:
        health["flower"]["error"] = f"{type(e).__name__}: {e}"

    return health


@router.get("/embedding/celery/health")
async def celery_health():
    """前端 AdminInfra 页定期刷新显示 Redis / Worker / Flower 绿灯用。"""
    return _check_celery_health()


@router.get("/embedding/celery")
async def get_celery_enabled():
    """查询 Celery 异步向量化开关状态。"""
    cfg = svc.get_config()
    return {
        "enabled": cfg.celery_enabled,
        "description": "开启后上传文档走 Celery 队列（Redis 持久化 + Docker worker 消费），削峰填谷。",
    }


@router.put("/embedding/celery")
async def update_celery_enabled(body: CeleryUpdate):
    """运行时切换 Celery 异步向量化。

    开启前预检查：Redis ping + Celery worker inspect 都必须 OK，否则返回 503 + 不持久化。
    关闭直接生效，不做检查。
    """
    cfg = svc.get_config()
    if body.enabled:
        health = _check_celery_health()
        if not health["redis"]["ok"] or not health["celery"]["ok"]:
            raise HTTPException(
                status_code=503,
                detail={
                    "message": "Celery 未就绪，无法开启",
                    "health": health,
                    "hint": "1. 确认本机 Redis 已启动（brew services start redis）"
                            " 2. 确认 worker 容器已启动（docker compose -f backend/docker-compose.celery.yml up -d）",
                },
            )
    cfg.celery_enabled = body.enabled
    svc.save_config(cfg)
    return {
        "enabled": cfg.celery_enabled,
        "message": "Celery 异步向量化已启用" if body.enabled else "Celery 已关闭（走 asyncio 原路径）",
    }


@router.post("/embedding/activate")
async def activate_model():
    """
    下载完成后调用：使用当前配置初始化 RagService。
    若模型未下载会返回 400。
    """
    from app.services.rag_service import get_rag_service

    config = svc.get_config()
    if config.mode == "local" and not svc._is_bge_m3_cached():
        raise HTTPException(status_code=400, detail="BGE-M3 模型未下载，无法激活。")

    rag = get_rag_service()
    try:
        await asyncio.to_thread(rag.initialize, config)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"模型加载失败：{e}")

    return {"message": "Embedding 服务已就绪", "ready": rag.is_ready()}
