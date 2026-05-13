"""内部端点 · 仅本机 Celery worker 调用，不对外暴露。

绑定限制：main.py 中间件拒绝非本机 IP 访问 /api/internal/*（127.0.0.1 / ::1 /
docker gateway 172.17/16 等）。路由本身不做鉴权 —— 边界由中间件统一把守。

POST /api/internal/vectorize/{file_id}
  走现有 `rag_service._do_vectorize_sync`，实现与 `_vectorize_document` 异步版
  完全等价（内部状态更新一致），供 Celery worker 通过 HTTP 触发。
"""
import os
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException
from app.services.rag_service import get_rag_service, UPLOAD_DIR
from app.models.knowledge_document import KnowledgeDocument

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/vectorize/{file_id}")
async def internal_vectorize(file_id: str) -> dict:
    """Celery worker 触发的向量化端点。

    调用方：worker container 的 `requests.post(...)` 转发而来。
    行为：和 `rag_service._vectorize_document` 完全一致，只是走同步 HTTP 返回。
    """
    doc_record = await KnowledgeDocument.find_one(
        KnowledgeDocument.file_id == file_id
    )
    if not doc_record:
        raise HTTPException(status_code=404, detail=f"Document {file_id} not found")

    # 只有 pending / failed 才允许走向量化；processing 说明已有 worker 在跑
    if doc_record.vectorize_status not in ("pending", "failed"):
        logger.warning(
            f"[internal/vectorize] file_id={file_id} "
            f"status={doc_record.vectorize_status}, skip"
        )
        return {
            "file_id": file_id,
            "status": doc_record.vectorize_status,
            "skipped": True,
            "reason": "already in progress or done",
        }

    doc_record.vectorize_status = "processing"
    await doc_record.save()

    rag = get_rag_service()

    try:
        file_path = os.path.join(UPLOAD_DIR, file_id)
        # to_thread 避免阻塞 event loop；与 _vectorize_document 保持一致
        import asyncio
        chunk_count, sample_chunks = await asyncio.to_thread(
            rag._do_vectorize_sync,
            file_id, file_path, doc_record.extension, doc_record.original_name,
        )

        doc_record.vectorize_status = "done"
        doc_record.chunk_count = chunk_count
        doc_record.vectorized_at = datetime.now(timezone.utc)
        doc_record.error_message = ""
        await doc_record.save()
        logger.info(
            f"[internal/vectorize] done: file_id={file_id} chunks={chunk_count}"
        )

        # 异步生成 summary + topics，不阻塞 HTTP 响应
        if sample_chunks:
            asyncio.create_task(
                rag._generate_summary(
                    file_id, doc_record.original_name, sample_chunks
                )
            )

        return {
            "file_id": file_id,
            "status": "done",
            "chunk_count": chunk_count,
        }

    except Exception as e:
        logger.error(
            f"[internal/vectorize] failed file_id={file_id}: {e}",
            exc_info=True,
        )
        doc_record.vectorize_status = "failed"
        doc_record.error_message = str(e)
        await doc_record.save()
        raise HTTPException(
            status_code=500,
            detail=f"Vectorization failed: {e}",
        )
