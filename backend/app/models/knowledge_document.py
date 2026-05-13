from beanie import Document
from pydantic import Field
from pymongo import IndexModel, TEXT
from datetime import datetime, timezone


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class KnowledgeDocument(Document):
    file_id: str
    original_name: str
    extension: str
    file_size: int = 0
    chunk_count: int = 0
    vectorize_status: str = "pending"
    error_message: str = ""
    uploaded_at: datetime = Field(default_factory=_utcnow)
    vectorized_at: datetime | None = None

    # ── 文档级语义元数据（LLM 在向量化完成后自动生成）────────────────
    # 用于回答"和 X 相关的书有哪些"这类 document-level 主题匹配 query
    # 详见 plan-doc-dir/某些query无法精确匹配.md 方案 ①
    summary: str = ""                           # 100-150 字中文概要
    topics: list[str] = []                      # 3-8 个主题标签
    summary_generated_at: datetime | None = None  # 生成时间；None = 未生成

    # ── Celery 异步向量化（默认 off；仅开启时写入）────────────────
    # 存 Celery task id，重启时用 AsyncResult 查状态决定是否 re-enqueue
    celery_task_id: str | None = None

    class Settings:
        name = "knowledge_documents"
        indexes = [
            "file_id",
            "vectorize_status",
            "topics",                           # 按标签过滤（$elemMatch）
            # 跨字段文本索引：让 $text 同时命中 summary / topics / original_name。
            # default_language="none" 关闭英文 stemming，对中文更友好（Mongo 对
            # 中文没有分词器，但"政治学"这类连续字符串仍可命中）。
            IndexModel(
                [("summary", TEXT), ("topics", TEXT), ("original_name", TEXT)],
                name="doc_text_idx",
                default_language="none",
            ),
        ]
