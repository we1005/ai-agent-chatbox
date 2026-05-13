"""
历史文档回填脚本：为 summary_generated_at is None 的老记录补齐 summary + topics。

背景：plan-doc-dir/某些query无法精确匹配.md 方案 ① 上线后，新上传的文档会在
向量化完成时自动生成 summary/topics 并写入 MongoDB；但此前已入库的老文档没有
这两个字段，会让 query_knowledge_base_catalog(topic=...) 漏召。

本脚本遍历所有 status=done 且 summary_generated_at 为 None 的 KnowledgeDocument，
从 Qdrant 取该文档前 5 个 chunk 的文本作为采样，调 DeepSeek 生成元数据并写回。

用法：
    cd backend
    source venv/bin/activate
    python -m scripts.backfill_summaries              # 干跑 + 执行
    python -m scripts.backfill_summaries --dry-run    # 只打印待回填清单，不调 LLM、不写 DB
    python -m scripts.backfill_summaries --limit 10   # 限量（先试跑 10 篇）

注意：
- 脚本独立运行，不依赖 backend 进程；内部自建 Mongo + Qdrant 客户端。
- 每篇文档一次 DeepSeek 调用（~200 tokens，DeepSeek-chat 价格可忽略）。
- 失败单篇不中断全量；尾部打印成功 / 跳过 / 失败统计。
- 幂等：已回填（summary_generated_at 非空）的记录自动跳过，重复执行安全。
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from pathlib import Path

# 让脚本能 import app.*（本文件位于 backend/scripts/，需把 backend/ 加入 sys.path）
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("backfill")


async def _init_db() -> None:
    from pymongo import AsyncMongoClient
    from beanie import init_beanie
    from app.core.config import get_settings
    from app.models.conversation import Conversation
    from app.models.knowledge_document import KnowledgeDocument

    settings = get_settings()
    client = AsyncMongoClient(settings.MONGODB_URL)
    await init_beanie(
        database=client[settings.MONGODB_DB_NAME],
        document_models=[Conversation, KnowledgeDocument],
    )


def _fetch_sample_chunks_from_qdrant(file_id: str, k: int = 5) -> list[str]:
    """从 Qdrant 取指定 file_id 的前 k 个 chunk 文本。"""
    from app.services.vector_store import get_vector_store

    backend = get_vector_store()
    # scroll 带 filter 拉前 k 条；QdrantBackend 未直接暴露 scroll，用底层 client。
    # 这里仅做一次只读查询，不改既有抽象层。
    client = backend._client  # type: ignore[attr-defined]
    collection = backend._collection  # type: ignore[attr-defined]
    from qdrant_client.http import models as qm

    try:
        points, _ = client.scroll(
            collection_name=collection,
            scroll_filter=qm.Filter(
                must=[qm.FieldCondition(
                    key="source_file_id", match=qm.MatchValue(value=file_id),
                )]
            ),
            limit=k,
            with_payload=True,
            with_vectors=False,
        )
        # QdrantBackend.upsert_documents 把 page_content 存到 payload["text"] 里
        return [p.payload.get("text") or "" for p in points if p.payload]
    except Exception as e:
        logger.warning(f"Qdrant scroll failed for {file_id}: {e}")
        return []


async def _backfill_one(file_id: str, original_name: str, dry_run: bool) -> str:
    """
    回填一篇文档。返回 'ok' / 'skip:<reason>' / 'fail:<reason>'。
    """
    chunks = _fetch_sample_chunks_from_qdrant(file_id, k=5)
    if not chunks:
        return "skip:no_chunks_in_qdrant"

    logger.info(f"  sample: {len(chunks)} chunks, total {sum(len(c) for c in chunks)} chars")

    if dry_run:
        return "ok"

    # 复用 RagService._generate_summary —— 保证生成逻辑与主流程一致
    from app.services.rag_service import get_rag_service
    rag = get_rag_service()
    try:
        await rag._generate_summary(file_id, original_name, chunks)
        return "ok"
    except Exception as e:
        return f"fail:{type(e).__name__}:{e}"


async def run(dry_run: bool, limit: int | None) -> None:
    await _init_db()

    from app.models.knowledge_document import KnowledgeDocument

    # 目标：向量化完成 + 没生成过摘要的
    pending = await KnowledgeDocument.find(
        KnowledgeDocument.vectorize_status == "done",
        KnowledgeDocument.summary_generated_at == None,  # noqa: E711
    ).to_list()

    if limit is not None and limit > 0:
        pending = pending[:limit]

    total_all = await KnowledgeDocument.find(
        KnowledgeDocument.vectorize_status == "done"
    ).count()
    logger.info(
        f"回填范围：待处理 {len(pending)} / 已完成向量化 {total_all}；"
        f"mode={'dry-run' if dry_run else 'execute'}"
    )
    if not pending:
        logger.info("没有需要回填的文档。")
        return

    stats = {"ok": 0, "skip": 0, "fail": 0}
    for i, doc in enumerate(pending, 1):
        logger.info(f"[{i}/{len(pending)}] {doc.original_name} (file_id={doc.file_id})")
        result = await _backfill_one(doc.file_id, doc.original_name, dry_run)
        if result == "ok":
            stats["ok"] += 1
        elif result.startswith("skip"):
            stats["skip"] += 1
            logger.warning(f"  → skip: {result}")
        else:
            stats["fail"] += 1
            logger.error(f"  → fail: {result}")

    logger.info(
        f"完成：ok={stats['ok']} skip={stats['skip']} fail={stats['fail']}"
        + ("（dry-run，未写入数据库）" if dry_run else "")
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="回填 KnowledgeDocument.summary / topics")
    parser.add_argument("--dry-run", action="store_true", help="只列出待回填文档，不调 LLM、不写库")
    parser.add_argument("--limit", type=int, default=None, help="限量回填前 N 篇")
    args = parser.parse_args()
    asyncio.run(run(args.dry_run, args.limit))


if __name__ == "__main__":
    main()
