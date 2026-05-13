"""
向量存储工厂。业务层只 import get_vector_store()。
"""
from __future__ import annotations

import logging

from app.core.config import get_settings

from .base import VectorStoreBackend
from .qdrant_backend import QdrantBackend

logger = logging.getLogger(__name__)

_instance: VectorStoreBackend | None = None


def get_vector_store() -> VectorStoreBackend:
    """返回全局向量存储后端单例（当前固定为 Qdrant）。"""
    global _instance
    if _instance is None:
        settings = get_settings()
        _instance = QdrantBackend(
            url=settings.QDRANT_URL,
            collection=settings.QDRANT_COLLECTION,
            api_key=settings.QDRANT_API_KEY or None,
        )
        logger.info(
            f"VectorStore backend created: qdrant @ {settings.QDRANT_URL} / {settings.QDRANT_COLLECTION}"
        )
    return _instance


__all__ = ["VectorStoreBackend", "get_vector_store"]
