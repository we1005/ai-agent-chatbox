"""
向量存储调试端点。不走 reranker，便于肉眼观察原始召回质量。
"""
import asyncio
import logging
from typing import Literal

from fastapi import APIRouter, HTTPException

from app.services.rag_service import get_rag_service
from app.services.vector_store import get_vector_store

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/vs/health")
async def vs_health():
    """返回当前向量存储后端的健康状态与集合统计。"""
    try:
        backend = get_vector_store()
        info = await asyncio.to_thread(backend.health)
        return info
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/vs/search")
async def vs_search(
    q: str,
    mode: Literal["dense", "sparse", "hybrid"] = "hybrid",
    k: int = 20,
):
    """不经 reranker 直接跑一次召回，返回 top-k 原始结果。"""
    rag = get_rag_service()
    if not rag.is_ready():
        raise HTTPException(
            status_code=503,
            detail={
                "code": "EMBEDDING_NOT_READY",
                "message": "Embedding 模型未加载，请先在知识库设置中加载模型。",
            },
        )
    backend = rag.backend

    def _run():
        if mode == "dense":
            return backend.search_dense(q, k=k)
        if mode == "sparse":
            return backend.search_sparse(q, k=k)
        return backend.search_hybrid(q, k=k)

    try:
        docs = await asyncio.to_thread(_run)
    except NotImplementedError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"/vs/search failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

    return {
        "query": q,
        "mode": mode,
        "k": k,
        "results_count": len(docs),
        "sparse_supported": backend.supports_sparse(),
        "results": [
            {
                "content": d.page_content.encode("utf-8", "ignore").decode("utf-8")[:200],
                "metadata": d.metadata,
            }
            for d in docs
        ],
    }


@router.get("/vs/compare")
async def vs_compare(q: str, k: int = 10):
    """
    并排对比 dense-only 与 hybrid 两种策略的原始召回结果（不走 reranker），用于前端策略对比页面。
    非 BGE-M3 模型时 hybrid 自动降级为 dense，返回体的 sparse_supported=false 会告知前端。
    """
    rag = get_rag_service()
    if not rag.is_ready():
        raise HTTPException(
            status_code=503,
            detail={
                "code": "EMBEDDING_NOT_READY",
                "message": "Embedding 模型未加载，请先在知识库设置中加载模型。",
            },
        )
    backend = rag.backend

    def _run_dense():
        return backend.search_dense(q, k=k)

    def _run_hybrid():
        return backend.search_hybrid(q, k=k)

    try:
        dense_docs, hybrid_docs = await asyncio.gather(
            asyncio.to_thread(_run_dense),
            asyncio.to_thread(_run_hybrid),
        )
    except Exception as e:
        logger.error(f"/vs/compare failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

    def _serialize(docs):
        return [
            {
                "rank": i + 1,
                "content": d.page_content.encode("utf-8", "ignore").decode("utf-8")[:500],
                "metadata": d.metadata,
                "source_file_id": d.metadata.get("source_file_id"),
            }
            for i, d in enumerate(docs)
        ]

    dense_serialized = _serialize(dense_docs)
    hybrid_serialized = _serialize(hybrid_docs)

    # 计算重合度：两种策略返回的 chunk 里（按 source_file_id + content 前 60 字的组合作为近似 id）有多少重合
    def _fingerprint(d):
        return (d["source_file_id"], d["content"][:60])

    dense_set = {_fingerprint(d) for d in dense_serialized}
    hybrid_set = {_fingerprint(d) for d in hybrid_serialized}
    overlap = len(dense_set & hybrid_set)

    return {
        "query": q,
        "k": k,
        "sparse_supported": backend.supports_sparse(),
        "dense": dense_serialized,
        "hybrid": hybrid_serialized,
        "overlap_count": overlap,
        "overlap_ratio": round(overlap / k, 3) if k > 0 else 0.0,
    }


@router.get("/vs/test-retrieval")
async def vs_test_retrieval(query: str = "计算所复试名单有哪些人？"):
    """走完整检索链路（含 reranker），保留原 /chroma/test-retrieval 的用法。"""
    try:
        retriever = get_rag_service().get_retriever()
        docs = await retriever.ainvoke(query)
        return {
            "query": query,
            "results_count": len(docs),
            "results": [
                {
                    "content": doc.page_content.encode("utf-8", "ignore").decode("utf-8")[:200],
                    "metadata": doc.metadata,
                }
                for doc in docs
            ],
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
