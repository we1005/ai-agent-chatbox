"""Benchmark 专用管理端点（仅限 localhost）。

用于 run_memory_bench.py 在多 config 矩阵测评时，在不重启服务器的情况下动态切换
Context Engine 三个 feature flag。

原理：get_settings() 是 @lru_cache，直接改 os.environ 不生效；
调用 get_settings.cache_clear() + 设 os.environ 后，下一次 get_settings() 调用
会重新读 pydantic-settings，拿到新值。

端点均受 main.py 的 InternalOnlyMiddleware 保护（只允许 127.0.0.1）。
"""

import os
import logging
from pydantic import BaseModel
from fastapi import APIRouter

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/admin", tags=["admin-bench"])


class ContextEngineConfig(BaseModel):
    context_engine: bool
    memory_reflect: bool
    memory_retrieval: bool


@router.put("/context-engine-config")
async def set_context_engine_config(cfg: ContextEngineConfig):
    """动态切换 Context Engine / Memory 三个 feature flag（bench 专用）。"""
    os.environ["CONTEXT_ENGINE_ENABLED"] = str(cfg.context_engine).lower()
    os.environ["MEMORY_REFLECT_ENABLED"] = str(cfg.memory_reflect).lower()
    os.environ["MEMORY_RETRIEVAL_ENABLED"] = str(cfg.memory_retrieval).lower()
    from app.core.config import get_settings
    get_settings.cache_clear()
    new = get_settings()
    logger.info(
        f"[AdminBench] context_engine={new.CONTEXT_ENGINE_ENABLED} "
        f"memory_reflect={new.MEMORY_REFLECT_ENABLED} "
        f"memory_retrieval={new.MEMORY_RETRIEVAL_ENABLED}"
    )
    return {
        "ok": True,
        "context_engine": new.CONTEXT_ENGINE_ENABLED,
        "memory_reflect": new.MEMORY_REFLECT_ENABLED,
        "memory_retrieval": new.MEMORY_RETRIEVAL_ENABLED,
    }


@router.get("/context-engine-config")
async def get_context_engine_config():
    """返回当前 Context Engine feature flag 状态。"""
    from app.core.config import get_settings
    s = get_settings()
    return {
        "context_engine": s.CONTEXT_ENGINE_ENABLED,
        "memory_reflect": s.MEMORY_REFLECT_ENABLED,
        "memory_retrieval": s.MEMORY_RETRIEVAL_ENABLED,
    }
