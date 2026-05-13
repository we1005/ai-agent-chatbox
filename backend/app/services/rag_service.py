import asyncio
import os
import shutil
import logging
import warnings
from datetime import datetime, timezone
from fastapi import UploadFile
import uuid
from app.core.config import get_settings
from app.services._langsmith import traceable
from app.services.vector_store import get_vector_store

warnings.filterwarnings("ignore", message=".*fix_mistral_regex.*")

settings = get_settings()
os.environ["HF_ENDPOINT"] = settings.HF_ENDPOINT
logger = logging.getLogger(__name__)

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DATA_DIR = os.path.join(BACKEND_DIR, "data")
UPLOAD_DIR = os.path.join(DATA_DIR, "uploads")
MODELS_DIR = os.path.join(DATA_DIR, "models")

SUPPORTED_EXTENSIONS = {
    ".pdf", ".txt", ".md",
    ".docx",
    ".csv",
    ".xlsx", ".xls",
    ".pptx",
    ".epub",
}

os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(MODELS_DIR, exist_ok=True)


def _load_documents(file_path: str, file_ext: str, original_name: str):
    """加载文档并返回 LangChain Document 列表（同步阻塞）"""
    from langchain_community.document_loaders import (
        UnstructuredMarkdownLoader,
        Docx2txtLoader,
        TextLoader,
    )
    from langchain_core.documents import Document

    meta = {"original_filename": original_name}

    if file_ext == ".pdf":
        from langchain_community.document_loaders import PDFPlumberLoader
        documents = PDFPlumberLoader(file_path).load()

    elif file_ext == ".md":
        documents = UnstructuredMarkdownLoader(file_path).load()

    elif file_ext == ".docx":
        documents = Docx2txtLoader(file_path).load()

    elif file_ext == ".csv":
        from langchain_community.document_loaders.csv_loader import CSVLoader
        for enc in ("utf-8", "gbk", "latin-1"):
            try:
                documents = CSVLoader(file_path, encoding=enc).load()
                break
            except (UnicodeDecodeError, Exception):
                continue
        else:
            raise ValueError(f"无法解码 CSV 文件 {original_name}，已尝试 utf-8/gbk/latin-1。")

    elif file_ext in (".xlsx", ".xls"):
        from langchain_community.document_loaders import UnstructuredExcelLoader
        documents = UnstructuredExcelLoader(file_path, mode="elements").load()

    elif file_ext == ".pptx":
        from langchain_community.document_loaders import UnstructuredPowerPointLoader
        documents = UnstructuredPowerPointLoader(file_path, mode="elements").load()

    elif file_ext == ".epub":
        import ebooklib
        from ebooklib import epub
        from bs4 import BeautifulSoup
        book = epub.read_epub(file_path, options={"ignore_ncx": True})
        documents = []
        for item in book.get_items_of_type(ebooklib.ITEM_DOCUMENT):
            soup = BeautifulSoup(item.get_content(), "html.parser")
            text = soup.get_text(separator="\n", strip=True)
            if text:
                documents.append(Document(page_content=text, metadata=meta))
        if not documents:
            raise ValueError(f"EPUB 文件 {original_name} 中未提取到任何文本内容。")
        return documents

    elif file_ext == ".txt":
        for enc in ("utf-8", "gbk", "latin-1"):
            try:
                documents = TextLoader(file_path, encoding=enc).load()
                break
            except UnicodeDecodeError:
                continue
        else:
            raise ValueError(f"Cannot decode {original_name}: tried utf-8/gbk/latin-1")

    else:
        raise ValueError(f"Unsupported file type: {file_ext}")

    if not documents or all(not doc.page_content.strip() for doc in documents):
        raise ValueError(
            f"文档 {original_name} 内容为空，可能是扫描版或格式异常，请检查后重新上传。"
        )

    for doc in documents:
        doc.metadata["original_filename"] = original_name

    return documents


from langchain_core.retrievers import BaseRetriever
from langchain_core.documents import Document as _LCDocument
from typing import Any


class _BackendRetriever(BaseRetriever):
    """
    LangChain BaseRetriever 适配器：把 VectorStoreBackend.search_* 包装成
    ContextualCompressionRetriever 能接受的 base_retriever。

    召回模式（dense | hybrid）从 RagService 的运行时字段 `search_mode` 读取
    （默认从 settings 初始化，但可以通过前端开关或 API 热切换）。
    hybrid 下若模型不支持 sparse，backend 内部会自动降级为 dense，无需上层判断。
    """

    backend: Any
    k: int
    get_mode: Any    # 可调用对象，返回当前 search_mode 字符串

    model_config = {"arbitrary_types_allowed": True}

    def _do_search(self, query: str) -> list[_LCDocument]:
        mode = self.get_mode()
        if mode == "hybrid":
            return self.backend.search_hybrid(
                query=query,
                k=self.k,
                fusion=settings.VECTOR_STORE_HYBRID_FUSION,
            )
        return self.backend.search_dense(query=query, k=self.k)

    def _get_relevant_documents(self, query: str, *, run_manager=None) -> list[_LCDocument]:
        return self._do_search(query)

    async def _aget_relevant_documents(self, query: str, *, run_manager=None) -> list[_LCDocument]:
        return await asyncio.to_thread(self._do_search, query)


# Agentic RAG 档位（见 plan-doc-dir/本项目是否真的实现了Agentic-RAG.md）
# 顺序决定强度：后面的档位包含前面的能力
_AGENTIC_RAG_MODES: tuple[str, ...] = ("off", "grading_only", "grading_rewrite", "full")

# Graph RAG（LightRAG）查询模式白名单，对齐 LightRAG 原生 QueryParam.mode
_GRAPH_RAG_QUERY_MODES: tuple[str, ...] = ("naive", "local", "global", "hybrid", "mix")


def _mode_at_least(current: str, target: str) -> bool:
    """current 档位是否 >= target（按 _AGENTIC_RAG_MODES 的顺序）。"""
    try:
        return _AGENTIC_RAG_MODES.index(current) >= _AGENTIC_RAG_MODES.index(target)
    except ValueError:
        return False


class RagService:
    def __init__(self):
        # ── 延迟初始化：不在构造函数中加载模型 ──────────────────
        self.embeddings = None
        self.backend = None          # VectorStoreBackend
        self.reranker = None
        self._model_name: str | None = None
        self._initialized = False
        # 运行时可热切换：dense（传统 RAG）| hybrid（dense + learned sparse）
        # 默认从 settings 读一次，之后由 /api/embedding/search-mode 修改
        self.search_mode: str = settings.VECTOR_STORE_SEARCH_MODE
        # Multi-Query 开关：默认从 EmbeddingConfig 读取（持久化），运行时可热切换
        from app.services.embedding_service import get_config as _get_embedding_config
        try:
            self.multi_query_enabled: bool = bool(_get_embedding_config().multi_query_enabled)
        except Exception:
            self.multi_query_enabled = False
        # Agentic RAG 档位（classic 路径）：off / grading_only / grading_rewrite / full
        # 默认 "off"，从 EmbeddingConfig 读取持久化值
        try:
            raw_mode = str(_get_embedding_config().agentic_rag_mode or "off")
            self.agentic_rag_mode: str = raw_mode if raw_mode in _AGENTIC_RAG_MODES else "off"
        except Exception:
            self.agentic_rag_mode = "off"
        # Graph RAG（LightRAG）开关 + 查询模式（默认 hybrid）
        # 启用后在 chat_service 中拥有最高优先级，覆盖 Agentic / Multi-Query。
        try:
            cfg = _get_embedding_config()
            self.graph_rag_enabled: bool = bool(cfg.graph_rag_enabled)
            raw_graph_mode = str(cfg.graph_rag_query_mode or "hybrid")
            self.graph_rag_query_mode: str = (
                raw_graph_mode if raw_graph_mode in _GRAPH_RAG_QUERY_MODES else "hybrid"
            )
        except Exception:
            self.graph_rag_enabled = False
            self.graph_rag_query_mode = "hybrid"

    def set_search_mode(self, mode: str) -> None:
        """运行时切换召回模式。mode 必须是 'dense' 或 'hybrid'。"""
        if mode not in ("dense", "hybrid"):
            raise ValueError(f"Invalid search mode: {mode!r}")
        self.search_mode = mode
        logger.info(f"Search mode switched to: {mode}")

    def set_multi_query_enabled(self, enabled: bool) -> None:
        """运行时切换 Multi-Query 多路召回。同时持久化到 embedding_config.json。"""
        from app.services.embedding_service import get_config as _gc, save_config as _sc
        self.multi_query_enabled = bool(enabled)
        try:
            cfg = _gc()
            cfg.multi_query_enabled = self.multi_query_enabled
            _sc(cfg)
        except Exception as e:
            logger.warning(f"Persisting multi_query_enabled failed (non-fatal): {e}")
        logger.info(f"Multi-Query enabled switched to: {self.multi_query_enabled}")

    def set_agentic_rag_mode(self, mode: str) -> None:
        """运行时切换 Agentic RAG 档位。合法值：off / grading_only / grading_rewrite / full。
        同时持久化到 embedding_config.json。非法值抛 ValueError。"""
        if mode not in _AGENTIC_RAG_MODES:
            raise ValueError(
                f"Invalid agentic_rag_mode: {mode!r}. Allowed: {_AGENTIC_RAG_MODES}"
            )
        from app.services.embedding_service import get_config as _gc, save_config as _sc
        self.agentic_rag_mode = mode
        try:
            cfg = _gc()
            cfg.agentic_rag_mode = mode
            _sc(cfg)
        except Exception as e:
            logger.warning(f"Persisting agentic_rag_mode failed (non-fatal): {e}")
        logger.info(f"Agentic RAG mode switched to: {mode}")

    def agentic_rag_at_least(self, target: str) -> bool:
        """便捷方法：当前 mode 是否 >= target（用于分流判断）。"""
        return _mode_at_least(self.agentic_rag_mode, target)

    def set_graph_rag_enabled(self, enabled: bool) -> None:
        """运行时切换 Graph RAG（LightRAG）开关并持久化。"""
        from app.services.embedding_service import get_config as _gc, save_config as _sc
        self.graph_rag_enabled = bool(enabled)
        try:
            cfg = _gc()
            cfg.graph_rag_enabled = self.graph_rag_enabled
            _sc(cfg)
        except Exception as e:
            logger.warning(f"Persisting graph_rag_enabled failed (non-fatal): {e}")
        logger.info(f"Graph RAG enabled switched to: {self.graph_rag_enabled}")

    def set_graph_rag_query_mode(self, mode: str) -> None:
        """运行时切换 LightRAG 查询模式。合法值：naive / local / global / hybrid / mix。"""
        if mode not in _GRAPH_RAG_QUERY_MODES:
            raise ValueError(
                f"Invalid graph_rag_query_mode: {mode!r}. Allowed: {_GRAPH_RAG_QUERY_MODES}"
            )
        from app.services.embedding_service import get_config as _gc, save_config as _sc
        self.graph_rag_query_mode = mode
        try:
            cfg = _gc()
            cfg.graph_rag_query_mode = mode
            _sc(cfg)
        except Exception as e:
            logger.warning(f"Persisting graph_rag_query_mode failed (non-fatal): {e}")
        logger.info(f"Graph RAG query mode switched to: {mode}")

    # ── 初始化状态管理 ────────────────────────────────────────────

    def is_ready(self) -> bool:
        """Embedding 服务是否就绪（模型已加载）。"""
        return self._initialized

    def initialize(self, config=None) -> None:
        """
        根据配置加载 Embedding 模型并初始化向量库。
        同步阻塞，应通过 asyncio.to_thread 调用。
        """
        from app.services.embedding_service import build_embeddings, get_config, MODEL_DIMENSIONS
        if config is None:
            config = get_config()

        logger.info(
            f"Initializing RagService: mode={config.mode}, "
            f"model={config.local_model}, use_gpu={config.use_gpu}"
        )
        self.embeddings = build_embeddings(config)
        self._model_name = config.local_model
        dim = MODEL_DIMENSIONS.get(config.local_model, 1024)

        self.backend = get_vector_store()
        self.backend.init(embedding_fn=self.embeddings, dim=dim, model_name=config.local_model)

        # 注意：不再自动加载 reranker。由前端"启用 Reranker"开关显式触发
        # load_reranker() / unload_reranker()，避免在不用时白占 ~2.4GB 显存。
        self._initialized = True
        logger.info("RagService initialized successfully.")

    def load_reranker(self, use_gpu: bool = True) -> bool:
        """
        显式加载 BGE-Reranker-v2-m3 到显存。返回是否加载成功。
        已加载时直接返回 True；模型未下载时返回 False。
        """
        if self.reranker is not None:
            return True

        from app.services.embedding_service import BGE_RERANKER_LOCAL_PATH, _resolve_device
        if not os.path.isdir(BGE_RERANKER_LOCAL_PATH):
            logger.warning("Reranker model not found locally; cannot load.")
            return False
        try:
            from langchain_classic.retrievers.document_compressors import CrossEncoderReranker
            from langchain_community.cross_encoders import HuggingFaceCrossEncoder
            device = _resolve_device(use_gpu)
            logger.info(f"Loading BGE-Reranker on device={device}")
            cross_encoder = HuggingFaceCrossEncoder(
                model_name=BGE_RERANKER_LOCAL_PATH,
                model_kwargs={"device": device},
            )
            self.reranker = CrossEncoderReranker(model=cross_encoder, top_n=4)
            logger.info("BGE-Reranker loaded successfully.")
            return True
        except Exception as e:
            logger.warning(f"Failed to load reranker: {e}")
            self.reranker = None
            return False

    def unload_reranker(self) -> None:
        """
        卸载 reranker 并尝试释放显存。下次开启开关时重新加载。
        """
        if self.reranker is None:
            return
        logger.info("Unloading BGE-Reranker from VRAM")
        self.reranker = None
        try:
            import torch
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
            elif hasattr(torch, "mps") and hasattr(torch.mps, "empty_cache") \
                    and torch.backends.mps.is_available():
                torch.mps.empty_cache()
        except Exception as e:
            logger.debug(f"empty_cache failed (non-fatal): {e}")

    async def reset_for_model_switch(self) -> None:
        """
        模型切换时清空向量库 Collection 并重置所有文档向量化状态。
        向量维度变化时必须调用。
        """
        from app.models.knowledge_document import KnowledgeDocument

        logger.warning("Resetting vector store for model switch...")

        self.embeddings = None
        self._initialized = False

        try:
            if self.backend is None:
                self.backend = get_vector_store()
            await asyncio.to_thread(self.backend.reset_collection)
        except Exception as e:
            logger.error(f"Failed to reset vector store: {e}")

        # 重置 MongoDB 所有文档状态
        await KnowledgeDocument.find_all().update(
            {"$set": {
                "vectorize_status": "pending",
                "chunk_count": 0,
                "vectorized_at": None,
                "error_message": "模型已切换，需要重新向量化。",
            }}
        )
        logger.info("All KnowledgeDocuments reset to 'pending'.")

    # ── 同步阻塞辅助方法（在线程池中执行，不阻塞 event loop）──────

    def _do_vectorize_sync(self, file_id: str, file_path: str,
                           extension: str, original_name: str) -> tuple[int, list[str]]:
        """
        同步执行：文档加载 → 分块 → 写入向量库。
        chunk_size=500（适配 BGE-M3，比原来 1000 更精准）。

        返回 (chunk_count, sample_chunks)；sample_chunks 是前若干段的纯文本，
        用于后续 LLM 摘要生成，避免摘要任务再次读盘解析。
        """
        from langchain_text_splitters import RecursiveCharacterTextSplitter
        documents = _load_documents(file_path, extension, original_name)
        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=500,    # 原为 1000，降低以提升检索精准度
            chunk_overlap=80,  # 原为 200
            separators=[
                "\n\n",   # 段落
                "\n",     # 换行
                "。", "！", "？", "；",   # 中文句末标点
                ".", "!", "?", ";",       # 英文句末标点
                "，", "、",               # 中文短停顿
                " ",                     # 空格（英文词边界）
                "",                      # 兜底：逐字符
            ],
        )
        splits = text_splitter.split_documents(documents)
        for split in splits:
            split.metadata["source_file_id"] = file_id
        if splits:
            self.backend.upsert_documents(splits)

        # 取前 5 块作为摘要输入样本（~2500 字）。给足 LLM 判断文档主题的信息，
        # 又不至于 prompt 爆炸。空文档时返回空 list。
        sample_chunks = [s.page_content for s in splits[:5]]
        return len(splits), sample_chunks

    def _delete_vectors_sync(self, file_id: str) -> None:
        """同步从向量库中精确删除指定文件的向量。"""
        if self.backend is None:
            raise RuntimeError("向量库未初始化，请先在知识库设置中加载 Embedding 模型。")
        self.backend.delete_by_file_id(file_id)

    # ── 上传：先保存文件+MongoDB记录，立即返回，后台向量化 ──────────

    async def upload_document(self, file: UploadFile) -> dict:
        from app.models.knowledge_document import KnowledgeDocument

        file_ext = os.path.splitext(file.filename)[1].lower()
        if file_ext not in SUPPORTED_EXTENSIONS:
            raise ValueError(
                f"不支持的文件格式 '{file_ext}'，"
                f"请上传 {', '.join(sorted(SUPPORTED_EXTENSIONS))} 格式的文件。"
            )

        file_id = str(uuid.uuid4())
        filename_on_disk = f"{file_id}{file_ext}"
        file_path = os.path.join(UPLOAD_DIR, filename_on_disk)

        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        file_size = os.path.getsize(file_path)

        doc_record = KnowledgeDocument(
            file_id=filename_on_disk,
            original_name=file.filename,
            extension=file_ext,
            file_size=file_size,
            vectorize_status="pending",
        )
        await doc_record.insert()

        # ── Celery 异步向量化分支（默认 off）──────────────────────────
        # 开启时：投递任务到 Redis，worker 容器按 concurrency=2 消费；状态仍经
        # _do_vectorize_sync 写 Mongo，前端轮询不变。
        # 关闭时：走原有 asyncio.create_task 路径（100% 向后兼容）。
        from app.services import embedding_service as _emb
        _cfg = _emb.get_config()
        if _cfg.celery_enabled:
            try:
                from app.workers.tasks import vectorize_document as _celery_task
                async_result = _celery_task.delay(filename_on_disk)
                # 记录 task id 便于重启恢复时 AsyncResult 查询
                doc_record.celery_task_id = async_result.id
                await doc_record.save()
                logger.info(
                    f"[upload] enqueued celery task {async_result.id} "
                    f"for file_id={filename_on_disk}"
                )
            except Exception as e:
                logger.warning(
                    f"[upload] celery enqueue failed ({e}), "
                    f"fallback to asyncio.to_thread"
                )
                asyncio.create_task(self._vectorize_document(filename_on_disk))
        else:
            asyncio.create_task(self._vectorize_document(filename_on_disk))

        return {
            "filename": file.filename,
            "file_id": filename_on_disk,
            "status": "pending",
        }

    async def _vectorize_document(self, file_id: str):
        """后台向量化任务，更新 MongoDB 中的状态。"""
        from app.models.knowledge_document import KnowledgeDocument

        doc_record = await KnowledgeDocument.find_one(
            KnowledgeDocument.file_id == file_id
        )
        if not doc_record:
            logger.error(f"KnowledgeDocument not found for vectorization: {file_id}")
            return

        doc_record.vectorize_status = "processing"
        await doc_record.save()

        try:
            file_path = os.path.join(UPLOAD_DIR, file_id)
            chunk_count, sample_chunks = await asyncio.to_thread(
                self._do_vectorize_sync,
                file_id, file_path, doc_record.extension, doc_record.original_name,
            )

            doc_record.vectorize_status = "done"
            doc_record.chunk_count = chunk_count
            doc_record.vectorized_at = datetime.now(timezone.utc)
            doc_record.error_message = ""
            await doc_record.save()
            logger.info(f"Vectorized {file_id}: {chunk_count} chunks")

            # 异步生成 document-level summary + topics，不阻塞 vectorize 主流程
            if sample_chunks:
                asyncio.create_task(
                    self._generate_summary(file_id, doc_record.original_name, sample_chunks)
                )

        except Exception as e:
            logger.error(f"Vectorization failed for {file_id}: {e}", exc_info=True)
            doc_record.vectorize_status = "failed"
            doc_record.error_message = str(e)
            await doc_record.save()

    # ── 文档级摘要 / 主题标签生成（异步，向量化完成后触发）──────────
    #
    # 目标：为每个文档生成 100-150 字 summary + 3-8 个 topics 标签，写入 MongoDB。
    # 用途：回答"和 X 相关的书有哪些"这类 document-level 主题匹配 query，
    #      supply data for query_knowledge_base_catalog Tool 的 topic 过滤。
    # 详见 plan-doc-dir/某些query无法精确匹配.md 方案 ①。
    #
    # 失败策略：吞掉异常只打 warning，绝不影响向量化主流程或用户上传体验。

    @traceable(name="generate_doc_summary", run_type="chain")
    async def _generate_summary(
        self,
        file_id: str,
        original_name: str,
        sample_chunks: list[str],
    ) -> None:
        import json_repair
        from app.models.knowledge_document import KnowledgeDocument
        from app.services._langsmith import get_openai

        if not sample_chunks:
            return

        # 拼接采样文本，限长避免 prompt 爆炸（~3000 字上限）
        body = "\n\n".join(sample_chunks)[:3000]

        system_prompt = (
            "你是文档元数据生成器。根据给定的文档片段，输出 JSON："
            '{"summary": "100-150 字中文概要，说明文档主题和核心内容", '
            '"topics": ["主题标签1", "主题标签2", ...]}。'
            "topics 要求：3-8 个 2-6 字的中文短词，覆盖文档涉及的领域 / 概念 / 关键主题；"
            "不要复述文件名，不要泛泛而谈（如'文章'、'书籍'）。"
        )
        user_content = f"文件名：{original_name}\n\n文档片段：\n{body}"

        try:
            client = get_openai(
                api_key=settings.DEEPSEEK_API_KEY,
                base_url="https://api.deepseek.com",
                timeout=20.0,
            )
            resp = await client.chat.completions.create(
                model="deepseek-chat",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_content},
                ],
                response_format={"type": "json_object"},
                max_tokens=300,
                temperature=0.2,
            )
            raw = resp.choices[0].message.content or ""
            parsed = json_repair.loads(raw)
            if not isinstance(parsed, dict):
                logger.warning(
                    f"[Summary] Unexpected json_repair result for {file_id}: {type(parsed).__name__}"
                )
                return

            summary = str(parsed.get("summary") or "").strip()[:500]
            raw_topics = parsed.get("topics") or []
            topics: list[str] = []
            if isinstance(raw_topics, list):
                # 去重 + 长度裁剪 + 空值过滤，最多保留 8 个
                seen = set()
                for t in raw_topics:
                    if not isinstance(t, str):
                        continue
                    t = t.strip()[:20]
                    if t and t not in seen:
                        seen.add(t)
                        topics.append(t)
                    if len(topics) >= 8:
                        break

            if not summary and not topics:
                logger.warning(f"[Summary] Empty result for {file_id}, skip writing")
                return

            doc_record = await KnowledgeDocument.find_one(
                KnowledgeDocument.file_id == file_id
            )
            if not doc_record:
                logger.warning(f"[Summary] Doc record gone for {file_id}, skip")
                return
            doc_record.summary = summary
            doc_record.topics = topics
            doc_record.summary_generated_at = datetime.now(timezone.utc)
            await doc_record.save()
            logger.info(
                f"[Summary] Generated for {file_id} ({original_name}): "
                f"summary_len={len(summary)}, topics={topics}"
            )

        except Exception as e:
            logger.warning(f"[Summary] Failed for {file_id} ({original_name}): {e}")

    # ── 删除：先向量 → 再 MongoDB → 最后磁盘 ──────────────────────

    async def delete_document(self, file_id: str):
        from app.models.knowledge_document import KnowledgeDocument

        await asyncio.to_thread(self._delete_vectors_sync, file_id)

        await KnowledgeDocument.find_one(
            KnowledgeDocument.file_id == file_id
        ).delete()

        file_path = os.path.join(UPLOAD_DIR, file_id)
        if os.path.exists(file_path):
            os.remove(file_path)

    # ── 重新向量化 ─────────────────────────────────────────────────

    async def revectorize_document(self, file_id: str) -> dict:
        from app.models.knowledge_document import KnowledgeDocument

        doc_record = await KnowledgeDocument.find_one(
            KnowledgeDocument.file_id == file_id
        )
        if not doc_record:
            raise FileNotFoundError(f"Document record not found: {file_id}")

        file_path = os.path.join(UPLOAD_DIR, file_id)
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"File not found on disk: {file_id}")

        await asyncio.to_thread(self._delete_vectors_sync, file_id)

        doc_record.vectorize_status = "processing"
        await doc_record.save()

        try:
            chunk_count, sample_chunks = await asyncio.to_thread(
                self._do_vectorize_sync,
                file_id, file_path, doc_record.extension, doc_record.original_name,
            )

            doc_record.vectorize_status = "done"
            doc_record.chunk_count = chunk_count
            doc_record.vectorized_at = datetime.now(timezone.utc)
            doc_record.error_message = ""
            await doc_record.save()

            # 重新向量化也重新生成 summary（文档内容可能已变）
            if sample_chunks:
                asyncio.create_task(
                    self._generate_summary(file_id, doc_record.original_name, sample_chunks)
                )

            return {
                "filename": doc_record.original_name,
                "file_id": file_id,
                "chunks": chunk_count,
            }

        except Exception as e:
            logger.error(f"Revectorize failed for {file_id}: {e}", exc_info=True)
            doc_record.vectorize_status = "failed"
            doc_record.error_message = str(e)
            await doc_record.save()
            raise

    # ── 检索 ───────────────────────────────────────────────────────

    def get_retriever(self, use_reranker: bool = True):
        """
        返回检索器。
          use_reranker=True  且 reranker 已加载：向量召回 Top-K → Reranker 精排 → Top-N
          use_reranker=False 或 reranker 未加载：向量召回 Top-N（Recall-only）
        召回模式由 settings.VECTOR_STORE_SEARCH_MODE 控制：dense | hybrid。
        """
        if self.backend is None:
            raise RuntimeError("向量库未初始化，请先在知识库设置中加载 Embedding 模型。")

        recall_k = settings.VECTOR_STORE_RECALL_K
        top_k = settings.VECTOR_STORE_TOP_K

        get_mode = lambda: self.search_mode
        if use_reranker and self.reranker is not None:
            from langchain_classic.retrievers import ContextualCompressionRetriever
            base = _BackendRetriever(backend=self.backend, k=recall_k, get_mode=get_mode)
            return ContextualCompressionRetriever(
                base_compressor=self.reranker,
                base_retriever=base,
            )
        return _BackendRetriever(backend=self.backend, k=top_k, get_mode=get_mode)

    # ── Multi-Query 多路召回 ──────────────────────────────────────
    #
    # 设计见 plan-doc-dir/query改写方案汇总.md §九。
    # 流程：
    #   1) 用 DeepSeek 生成 N 个 variants（失败则降级为单 query 路径）
    #   2) queries = [original, *variants] 每条跑一次 hybrid（去重用 chunk_id / 指纹）
    #   3) 若 reranker 开启：CrossEncoder 对合并后的候选池按 **原 query** 打分，取 Top-N
    #      否则：RRF 融合 N 路结果取 Top-N
    #
    # 接口兼容：返回 list[Document]，调用方直接替换 retriever.ainvoke(query) 的结果即可。

    @traceable(name="multi_query_retrieve", run_type="retriever")
    async def retrieve_with_multi_query(
        self,
        original_query: str,
        use_reranker: bool = True,
        variant_count: int = 3,
    ) -> list:
        from app.services.multi_query import generate_variants, rrf_fuse

        if self.backend is None:
            raise RuntimeError("向量库未初始化，请先在知识库设置中加载 Embedding 模型。")

        recall_k = settings.VECTOR_STORE_RECALL_K
        top_k = settings.VECTOR_STORE_TOP_K

        variants = await generate_variants(original_query, n=variant_count)
        queries = [original_query] + variants
        logger.info(
            f"[MultiQuery] original={original_query!r} "
            f"variants={variants} → total {len(queries)} queries"
        )

        # 跑每一路 hybrid（并行）
        get_mode = lambda: self.search_mode

        def _search_one(q: str) -> list:
            mode = get_mode()
            k = recall_k if (use_reranker and self.reranker is not None) else top_k
            if mode == "hybrid":
                return self.backend.search_hybrid(
                    query=q, k=k, fusion=settings.VECTOR_STORE_HYBRID_FUSION,
                )
            return self.backend.search_dense(query=q, k=k)

        results_per_query: list[list] = await asyncio.gather(
            *[asyncio.to_thread(_search_one, q) for q in queries],
            return_exceptions=False,
        )

        # 去重 key：payload.chunk_id 优先；退而用 (source_file_id, page_content[:60])
        def _dedup_key(doc):
            md = getattr(doc, "metadata", {}) or {}
            cid = md.get("chunk_id") or md.get("_id") or md.get("id")
            if cid:
                return str(cid)
            return (md.get("source_file_id", ""), (doc.page_content or "")[:60])

        # 合并 & 去重
        seen: set = set()
        merged: list = []
        for rlist in results_per_query:
            for doc in rlist:
                k = _dedup_key(doc)
                if k in seen:
                    continue
                seen.add(k)
                merged.append(doc)
        logger.info(f"[MultiQuery] merged {sum(len(r) for r in results_per_query)} → {len(merged)} unique docs")

        # 分流：有 reranker 就直接精排；没有就 RRF 融合
        if use_reranker and self.reranker is not None:
            try:
                # CrossEncoderReranker.compress_documents(documents, query) —— 用 **原 query** 打分
                top_docs = await asyncio.to_thread(
                    self.reranker.compress_documents, merged, original_query
                )
                return list(top_docs)[:top_k]
            except Exception as e:
                logger.warning(f"[MultiQuery] rerank failed, falling back to RRF: {e}")

        # Fallback：RRF 融合 N 路原始排名
        top_docs = rrf_fuse(results_per_query, key_fn=_dedup_key, top_n=top_k)
        return top_docs


_rag_service_instance = None


def get_rag_service() -> RagService:
    global _rag_service_instance
    if _rag_service_instance is None:
        _rag_service_instance = RagService()
    return _rag_service_instance
