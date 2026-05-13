"""Celery 任务定义 · 仅 ~30 行。

核心设计：worker **不加载 ML 模型**，只做 HTTP 转发到 backend 内部端点。
backend 已持有 BGE-M3 单例，真正的向量化工作在 backend 主进程里做。
这是"削峰填谷"架构：worker concurrency=N 是阀门，限制同时打进 backend 的请求数。

HTTP 失败会自动重试：autoretry_for + 指数退避 + max_retries=3。
backend 偶发 503 / 连接重置 / 网络闪断都能被兜住。
"""
import os
import logging
import requests

from app.workers.celery_app import celery_app

logger = logging.getLogger(__name__)

BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8000")
# worker 容器里 docker-compose 会注入 BACKEND_URL=http://host.docker.internal:8000


@celery_app.task(
    name="xuanjian.vectorize_document",
    bind=True,
    autoretry_for=(requests.RequestException,),
    retry_backoff=True,            # 指数退避：1s, 2s, 4s, 8s
    retry_backoff_max=60,
    retry_jitter=True,
    max_retries=3,
)
def vectorize_document(self, file_id: str) -> dict:
    """异步向量化任务 · 仅转发 HTTP 到 backend。

    backend 端的 /api/internal/vectorize/{file_id} 内部走现有的
    `rag_service._vectorize_document_sync_wrapper` → `_do_vectorize_sync`，
    并写 Mongo 的 vectorize_status 状态。
    """
    url = f"{BACKEND_URL}/api/internal/vectorize/{file_id}"
    logger.info(f"[celery task {self.request.id}] POST {url}")

    # 文档向量化可能很慢（BGE-M3 CPU 几分钟），timeout 设大一些
    # backend 侧有自己的 asyncio.to_thread + _do_vectorize_sync 保证请求最终返回
    resp = requests.post(url, timeout=1500)
    resp.raise_for_status()

    result = resp.json()
    logger.info(
        f"[celery task {self.request.id}] done: "
        f"file_id={file_id} status={result.get('status')} "
        f"chunks={result.get('chunk_count')}"
    )
    return result
