"""
Qdrant 后端实现。

特性：
- named vectors：一个集合同时存 dense（1024 维，Cosine）+ sparse（IDF modifier）
- BGE-M3 lazy-loaded 用于 sparse（仅当模型为 bge-m3 时）；dense 仍复用 embedding_service 的 HF 实例
- payload 索引加速 source_file_id 过滤
- 原生 Query API + Prefetch + RRF 融合，无需外接 BM25
"""
from __future__ import annotations

import logging
import os
import uuid
from typing import Literal

from langchain_core.documents import Document

from .base import FilterDict, VectorStoreBackend

logger = logging.getLogger(__name__)

# 仅 bge-m3 系列原生产 sparse。其它模型走降级（仅 dense）。
_SPARSE_CAPABLE_MODELS = {"bge-m3"}


class QdrantBackend(VectorStoreBackend):
    def __init__(
        self,
        url: str,
        collection: str,
        api_key: str | None = None,
        upsert_batch: int = 256,
    ):
        self._url = url
        self._collection = collection
        self._api_key = api_key or None
        self._upsert_batch = upsert_batch

        self._client = None              # qdrant_client.QdrantClient
        self._embedding_fn = None        # LangChain Embeddings（出 dense）
        self._dim: int | None = None
        self._model_name: str | None = None
        self._sparse_model = None        # BGEM3FlagModel（lazy）

    # ── 初始化 ────────────────────────────────────────────────────────

    def init(self, embedding_fn, dim: int, model_name: str) -> None:
        from qdrant_client import QdrantClient

        self._embedding_fn = embedding_fn
        self._dim = dim
        self._model_name = model_name
        self._client = QdrantClient(url=self._url, api_key=self._api_key, timeout=30)

        self._ensure_collection()
        logger.info(
            f"QdrantBackend initialized: url={self._url}, collection={self._collection}, "
            f"dim={dim}, model={model_name}, sparse={self.supports_sparse()}"
        )

    def _ensure_collection(self) -> None:
        """幂等创建集合（dense + sparse 命名向量 + payload index）。维度不匹配时重建。"""
        from qdrant_client.models import (
            Distance,
            Modifier,
            SparseVectorParams,
            VectorParams,
        )

        exists = self._client.collection_exists(self._collection)
        if exists:
            info = self._client.get_collection(self._collection)
            existing_dim = info.config.params.vectors["dense"].size
            if existing_dim != self._dim:
                logger.warning(
                    f"Collection dim mismatch (existing={existing_dim}, expected={self._dim}), "
                    f"recreating collection."
                )
                self._client.delete_collection(self._collection)
                exists = False

        if not exists:
            self._client.create_collection(
                collection_name=self._collection,
                vectors_config={
                    "dense": VectorParams(size=self._dim, distance=Distance.COSINE),
                },
                sparse_vectors_config={
                    "sparse": SparseVectorParams(modifier=Modifier.IDF),
                },
            )
            logger.info(f"Created Qdrant collection '{self._collection}'")

        # Payload 索引：按 source_file_id 过滤是高频操作
        try:
            self._client.create_payload_index(
                collection_name=self._collection,
                field_name="source_file_id",
                field_schema="keyword",
            )
        except Exception:
            pass  # 已存在则忽略

    def supports_sparse(self) -> bool:
        return self._model_name in _SPARSE_CAPABLE_MODELS

    # ── BGE-M3 sparse lazy loader ─────────────────────────────────────

    def _get_sparse_model(self):
        """
        Lazy-load BGE-M3 sparse encoder. 优先复用 HuggingFaceEmbeddings 已加载的
        底层 transformer（SentenceTransformer → Transformer 模块 → auto_model），
        避免二次占用约 2GB 显存。
        """
        if self._sparse_model is not None:
            return self._sparse_model
        if not self.supports_sparse():
            raise NotImplementedError(
                f"Model '{self._model_name}' does not support sparse; only bge-m3 is supported."
            )
        from app.services.embedding_service import BGE_M3_LOCAL_PATH, _resolve_device
        from .bge_m3_sparse import BGEM3SparseEncoder

        device = _resolve_device(True)

        # 尝试从 HuggingFaceEmbeddings 中取出已加载的 encoder 和 tokenizer 复用。
        # langchain_huggingface 当前版本使用 self._client（带下划线）持有 SentenceTransformer；
        # 老版本可能暴露为 self.client。两个都试一次，拿到哪个用哪个。
        reuse_model = None
        reuse_tokenizer = None
        try:
            st = (
                getattr(self._embedding_fn, "_client", None)
                or getattr(self._embedding_fn, "client", None)
            )
            if st is not None and len(st) > 0:
                first_module = st[0]  # sentence_transformers.models.Transformer
                reuse_model = getattr(first_module, "auto_model", None)
                reuse_tokenizer = getattr(first_module, "tokenizer", None)
        except Exception as e:
            logger.warning(f"Could not locate SentenceTransformer's underlying model for reuse: {e}")

        self._sparse_model = BGEM3SparseEncoder(
            model_path=BGE_M3_LOCAL_PATH,
            reuse_model=reuse_model,
            reuse_tokenizer=reuse_tokenizer,
            device=device,
            use_fp16=(device == "cuda"),
        )
        return self._sparse_model

    def _encode_sparse(self, texts: list[str]) -> list[dict[int, float]]:
        """返回 list[dict[token_id, weight]]。"""
        return self._get_sparse_model().encode_sparse(texts)

    def _sparse_vec(self, query: str):
        from qdrant_client.models import SparseVector

        weights = self._encode_sparse([query])[0]
        if not weights:
            # 极端情况：query 切词后无有效 token
            return SparseVector(indices=[], values=[])
        indices = list(weights.keys())
        values = [weights[i] for i in indices]
        return SparseVector(indices=indices, values=values)

    # ── 写入 ──────────────────────────────────────────────────────────

    def upsert_documents(self, docs: list[Document]) -> list[str]:
        if not docs:
            return []
        from qdrant_client.models import PointStruct, SparseVector

        texts = [d.page_content for d in docs]
        # dense：LangChain Embeddings 接口
        dense_vecs = self._embedding_fn.embed_documents(texts)

        sparse_weights: list[dict[int, float]] | None = None
        if self.supports_sparse():
            sparse_weights = self._encode_sparse(texts)

        ids: list[str] = []
        points: list[PointStruct] = []
        for i, doc in enumerate(docs):
            pid = uuid.uuid4().hex
            ids.append(pid)
            vector: dict = {"dense": dense_vecs[i]}
            if sparse_weights is not None:
                w = sparse_weights[i]
                vector["sparse"] = SparseVector(
                    indices=list(w.keys()),
                    values=list(w.values()),
                )
            payload = dict(doc.metadata) if doc.metadata else {}
            payload["text"] = doc.page_content
            points.append(PointStruct(id=pid, vector=vector, payload=payload))

        for i in range(0, len(points), self._upsert_batch):
            batch = points[i:i + self._upsert_batch]
            self._client.upsert(
                collection_name=self._collection,
                points=batch,
                wait=True,
            )
            logger.info(
                f"Qdrant upsert batch {i // self._upsert_batch + 1} "
                f"({min(i + self._upsert_batch, len(points))}/{len(points)} points)"
            )
        return ids

    # ── 删除 ──────────────────────────────────────────────────────────

    def delete_by_file_id(self, file_id: str) -> int:
        from qdrant_client.models import FilterSelector

        f = self._make_filter({"source_file_id": file_id})
        # 先数一下，方便返回删除数量
        count = self.count({"source_file_id": file_id})
        if count == 0:
            return 0
        self._client.delete(
            collection_name=self._collection,
            points_selector=FilterSelector(filter=f),
            wait=True,
        )
        logger.info(f"Deleted {count} points for source_file_id={file_id}")
        return count

    def reset_collection(self) -> None:
        if self._client is None:
            from qdrant_client import QdrantClient
            self._client = QdrantClient(url=self._url, api_key=self._api_key, timeout=30)
        try:
            if self._client.collection_exists(self._collection):
                self._client.delete_collection(self._collection)
                logger.info(f"Dropped Qdrant collection '{self._collection}'")
        except Exception as e:
            logger.error(f"Failed to drop collection: {e}")
        # 重新 init 时会建回；也可以在这里立即建回，但维度依赖后续 init 提供
        # 丢弃缓存的 sparse 模型引用，让 init 时重新按新模型决定是否加载
        self._sparse_model = None

    # ── 检索 ──────────────────────────────────────────────────────────

    def search_dense(self, query: str, k: int, filter: FilterDict = None) -> list[Document]:
        dense = self._embedding_fn.embed_query(query)
        res = self._client.query_points(
            collection_name=self._collection,
            query=dense,
            using="dense",
            query_filter=self._make_filter(filter),
            limit=k,
            with_payload=True,
        )
        return self._points_to_docs(res.points)

    def search_sparse(self, query: str, k: int, filter: FilterDict = None) -> list[Document]:
        if not self.supports_sparse():
            raise NotImplementedError(
                f"Sparse search not supported for model '{self._model_name}'."
            )
        sv = self._sparse_vec(query)
        res = self._client.query_points(
            collection_name=self._collection,
            query=sv,
            using="sparse",
            query_filter=self._make_filter(filter),
            limit=k,
            with_payload=True,
        )
        return self._points_to_docs(res.points)

    def search_hybrid(
        self,
        query: str,
        k: int,
        filter: FilterDict = None,
        fusion: Literal["rrf", "dbsf"] = "rrf",
    ) -> list[Document]:
        if not self.supports_sparse():
            logger.debug(
                f"search_hybrid degraded to search_dense (model={self._model_name})"
            )
            return self.search_dense(query, k, filter)

        from qdrant_client.models import Fusion, FusionQuery, Prefetch

        dense = self._embedding_fn.embed_query(query)
        sparse = self._sparse_vec(query)

        prefetch_limit = max(k * 2, 40)
        fusion_enum = Fusion.RRF if fusion == "rrf" else Fusion.DBSF

        res = self._client.query_points(
            collection_name=self._collection,
            prefetch=[
                Prefetch(query=dense, using="dense", limit=prefetch_limit),
                Prefetch(query=sparse, using="sparse", limit=prefetch_limit),
            ],
            query=FusionQuery(fusion=fusion_enum),
            query_filter=self._make_filter(filter),
            limit=k,
            with_payload=True,
        )
        return self._points_to_docs(res.points)

    # ── 辅助 ──────────────────────────────────────────────────────────

    def count(self, filter: FilterDict = None) -> int:
        res = self._client.count(
            collection_name=self._collection,
            count_filter=self._make_filter(filter),
            exact=True,
        )
        return res.count

    def health(self) -> dict:
        try:
            exists = self._client.collection_exists(self._collection)
            info = self._client.get_collection(self._collection) if exists else None
            points = self.count() if exists else 0
            return {
                "backend": "qdrant",
                "url": self._url,
                "collection": self._collection,
                "exists": exists,
                "points": points,
                "dim": self._dim,
                "model": self._model_name,
                "sparse_enabled": self.supports_sparse(),
                "vectors_config": (
                    {k: {"size": v.size, "distance": str(v.distance)}
                     for k, v in info.config.params.vectors.items()}
                    if info else None
                ),
            }
        except Exception as e:
            return {"backend": "qdrant", "error": str(e)}

    def _make_filter(self, filter: FilterDict):
        if not filter:
            return None
        from qdrant_client.models import FieldCondition, Filter, MatchValue

        conditions = [
            FieldCondition(key=k, match=MatchValue(value=v))
            for k, v in filter.items()
        ]
        return Filter(must=conditions)

    @staticmethod
    def _points_to_docs(points) -> list[Document]:
        docs: list[Document] = []
        for p in points:
            payload = p.payload or {}
            text = payload.pop("text", "")
            docs.append(Document(page_content=text, metadata=payload))
        return docs
