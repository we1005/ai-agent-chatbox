"""
向量存储后端抽象基类。

业务层（RagService、ChatService 等）只依赖本接口，不直接 import qdrant_client / chroma。
当前仅有 QdrantBackend 一个实现，抽象层保留是为了：
1. 屏蔽底层 API 细节（named vectors / SparseVector / FusionQuery）
2. 便于 mock 测试
3. 为将来可能的替换（Milvus / 云托管）留出空间，不污染业务代码
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Literal

from langchain_core.documents import Document


FilterDict = dict | None


class VectorStoreBackend(ABC):
    """向量存储后端接口。所有方法均为同步阻塞，上层按需用 asyncio.to_thread 包装。"""

    @abstractmethod
    def init(self, embedding_fn, dim: int, model_name: str) -> None:
        """
        初始化后端（建立连接、创建集合/索引）。必须幂等。
        embedding_fn: LangChain Embeddings 实例，用于 dense 查询向量化
        dim:          dense 向量维度（与当前 embedding 模型一致）
        model_name:   当前 embedding 模型标识（如 bge-m3），用于判断是否具备 sparse 能力
        """

    @abstractmethod
    def upsert_documents(self, docs: list[Document]) -> list[str]:
        """写入文档（内部负责分批 + 双通道 encode）。返回写入的 chunk_id 列表。"""

    @abstractmethod
    def delete_by_file_id(self, file_id: str) -> int:
        """按 metadata.source_file_id 删除。返回删除数量。"""

    @abstractmethod
    def reset_collection(self) -> None:
        """清空并重建集合（模型切换、维度变化时调用）。"""

    @abstractmethod
    def search_dense(
        self, query: str, k: int, filter: FilterDict = None,
    ) -> list[Document]:
        """仅 dense 向量召回。"""

    @abstractmethod
    def search_sparse(
        self, query: str, k: int, filter: FilterDict = None,
    ) -> list[Document]:
        """仅 sparse（lexical）召回。模型不支持 sparse 时抛 NotImplementedError。"""

    @abstractmethod
    def search_hybrid(
        self,
        query: str,
        k: int,
        filter: FilterDict = None,
        fusion: Literal["rrf", "dbsf"] = "rrf",
    ) -> list[Document]:
        """dense + sparse 融合召回。模型不支持 sparse 时自动降级为 search_dense。"""

    @abstractmethod
    def count(self, filter: FilterDict = None) -> int:
        """集合内点数量（可带过滤）。"""

    @abstractmethod
    def health(self) -> dict:
        """健康检查 + 集合统计。"""

    @abstractmethod
    def supports_sparse(self) -> bool:
        """当前后端 + 当前模型是否支持 sparse 检索。"""
