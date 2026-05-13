"""Graph RAG（LightRAG）适配层。

职责：
  1. 把项目的 BGE-M3 embedding + DeepSeek LLM 插到 LightRAG 的 llm_model_func / embedding_func；
  2. 懒加载单例 LightRAG 实例，存储在 backend/data/lightrag/；
  3. 提供三个入口供外层使用：
     - graph_rag_retrieve(query, mode, rag) -> (list[Document], trace)    查询（only_need_context）
     - build_graph_index(rag, progress_callback)                          增量构图
     - get_graph_stats() / clear_graph_index()                            运维

设计要点 / 硬约束：
  - 默认关闭：没开启开关时本模块不会被加载（chat_service 只在 rag.graph_rag_enabled 为 True 时 import）。
  - fail-soft：任何 LightRAG 异常 / 索引为空都返回 degraded trace，上层回退到 classical 检索。
  - 不复用 Qdrant：LightRAG 自带 nano-vectordb 存向量到 JSON；POC 阶段够用。
  - Embedding 维度硬编码 1024（BGE-M3 / bge-large-zh-v1.5），切其它模型前这里要同步改。
  - LLM 走 get_openai() + DeepSeek，与项目其它 LLM 入口一致；启用 LANGSMITH_TRACING 自动被包装。

见 plan-doc-dir/LightRAG集成落地.md。
"""

from __future__ import annotations

import asyncio
import logging
import os
import shutil
from typing import Any, Awaitable, Callable

from langchain_core.documents import Document

from app.core.config import get_settings
from app.services._langsmith import get_openai, traceable

logger = logging.getLogger(__name__)

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
LIGHTRAG_DIR = os.path.join(BACKEND_DIR, "data", "lightrag")

# 适配层硬约束：当前仅支持 1024 维 embedding（BGE-M3 / bge-large-zh-v1.5）。
# 其它维度要加到这里或改成动态读取。
_SUPPORTED_EMBEDDING_DIMS = (1024,)
_DEFAULT_EMBEDDING_DIM = 1024
_DEFAULT_MAX_TOKEN_SIZE = 8192

_instance_lock = asyncio.Lock()
_instance: Any = None  # LightRAG | None，懒加载


# ── LLM / Embedding 适配 ────────────────────────────────────────────


def _build_llm_func() -> Callable[..., Awaitable[str]]:
    """LightRAG 要求 llm_model_func(prompt, system_prompt=None, history_messages=[], **kw) -> str。"""
    settings = get_settings()
    if not settings.DEEPSEEK_API_KEY:
        raise RuntimeError("DEEPSEEK_API_KEY 未配置，无法构建 Graph RAG LLM 函数")

    client = get_openai(
        api_key=settings.DEEPSEEK_API_KEY,
        base_url="https://api.deepseek.com/v1",
    )

    async def llm_model_func(
        prompt: str,
        system_prompt: str | None = None,
        history_messages: list[dict[str, str]] | None = None,
        **kwargs: Any,
    ) -> str:
        messages: list[dict[str, str]] = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        if history_messages:
            messages.extend(history_messages)
        messages.append({"role": "user", "content": prompt})

        # LightRAG 可能传 keyword_extraction / hashing_kv 等内部字段，只挑 OpenAI 认识的
        model = kwargs.get("model") or "deepseek-chat"
        temperature = kwargs.get("temperature", 0.0)
        resp = await client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=temperature,
            timeout=60.0,
        )
        return resp.choices[0].message.content or ""

    return llm_model_func


def _build_embedding_func(rag_service) -> Any:
    """把项目已有的 BGE-M3 embeddings 包成 LightRAG 的 EmbeddingFunc。

    调用前提：rag_service.is_ready() 必须为真（embedding 已加载）。
    """
    from lightrag.utils import EmbeddingFunc

    if rag_service.embeddings is None:
        raise RuntimeError("Embedding 未加载，请先激活 embedding 模型")

    embeddings = rag_service.embeddings

    async def _embed(texts: list[str]):
        # HuggingFaceEmbeddings 只有同步接口；用 to_thread 保持非阻塞
        vectors = await asyncio.to_thread(embeddings.embed_documents, list(texts))
        # LightRAG 期望 numpy.ndarray（shape=(n, dim)）或等价嵌套列表
        try:
            import numpy as np
            return np.array(vectors, dtype="float32")
        except ImportError:
            return vectors

    return EmbeddingFunc(
        embedding_dim=_DEFAULT_EMBEDDING_DIM,
        max_token_size=_DEFAULT_MAX_TOKEN_SIZE,
        func=_embed,
    )


# ── 单例管理 ────────────────────────────────────────────────────────


async def _get_lightrag_instance(rag_service) -> Any:
    """懒加载 + 初始化 LightRAG 单例。调用前保证 rag_service.is_ready() 为真。"""
    global _instance
    if _instance is not None:
        return _instance

    async with _instance_lock:
        if _instance is not None:
            return _instance

        os.makedirs(LIGHTRAG_DIR, exist_ok=True)
        from lightrag import LightRAG
        from lightrag.kg.shared_storage import initialize_pipeline_status

        inst = LightRAG(
            working_dir=LIGHTRAG_DIR,
            llm_model_func=_build_llm_func(),
            llm_model_name="deepseek-chat",
            embedding_func=_build_embedding_func(rag_service),
            # 其余走 LightRAG 默认：JsonKVStorage + NanoVectorDBStorage + NetworkXStorage
        )
        await inst.initialize_storages()
        try:
            await initialize_pipeline_status()
        except Exception as e:
            # 某些版本不需要，吞异常
            logger.debug(f"initialize_pipeline_status skipped: {e}")

        _instance = inst
        logger.info(f"LightRAG instance initialized at {LIGHTRAG_DIR}")
        return _instance


async def _reset_instance() -> None:
    """清实例句柄（不删磁盘数据）。用于 clear_graph_index 之后强制重新初始化。"""
    global _instance
    async with _instance_lock:
        if _instance is not None:
            try:
                finalize = getattr(_instance, "finalize_storages", None)
                if callable(finalize):
                    await finalize()
            except Exception as e:
                logger.debug(f"LightRAG finalize skipped: {e}")
            _instance = None


# ── 查询（retrieve-only，生成仍走项目自己的 LLM）──────────────────


@traceable(run_type="retriever", name="graph_rag_retrieve")
async def graph_rag_retrieve(
    query: str,
    mode: str,
    rag_service,
    *,
    timeout: float = 15.0,
) -> tuple[list[Document], dict[str, Any]]:
    """用 LightRAG 的 only_need_context 拿上下文，再切成 Document 列表送给项目的生成管道。

    失败时永不 raise：返回 ([], {"degraded": True, "reason": ...})，上层回退 classical。
    """
    trace: dict[str, Any] = {"degraded": False, "mode": mode}

    # 索引目录为空直接 fail-soft，避免 LightRAG 在首次 aquery 时抛异常
    if not _index_has_data():
        logger.warning("Graph RAG index is empty, falling back to vector retrieval")
        trace.update(degraded=True, reason="index_empty")
        return [], trace

    try:
        inst = await _get_lightrag_instance(rag_service)
    except Exception as e:
        logger.warning(f"Graph RAG instance init failed: {e}")
        trace.update(degraded=True, reason=f"init_error: {e}")
        return [], trace

    try:
        from lightrag import QueryParam
        param = QueryParam(mode=mode, only_need_context=True)
        context = await asyncio.wait_for(inst.aquery(query, param=param), timeout=timeout)
    except asyncio.TimeoutError:
        logger.warning(f"Graph RAG query timeout after {timeout}s")
        trace.update(degraded=True, reason="timeout")
        return [], trace
    except Exception as e:
        logger.warning(f"Graph RAG query failed: {e}")
        trace.update(degraded=True, reason=f"query_error: {e}")
        return [], trace

    docs = _context_to_documents(context, mode=mode)
    trace["docs_count"] = len(docs)
    if not docs:
        trace.update(degraded=True, reason="empty_context")
    return docs, trace


def _context_to_documents(context: Any, *, mode: str) -> list[Document]:
    """把 LightRAG 返回的 context 切成项目统一的 Document 列表。

    LightRAG 1.4.x 的 `kg_query_context` / `naive_query_context` 模板格式（见
    `lightrag/prompt.py` 和 `operate.py`）：

        Knowledge Graph Data (Entity):
        ```json
        {"entity_name": ..., "description": ..., "file_path": "..."}
        ...
        ```

        Knowledge Graph Data (Relationship):
        ```json
        {...}
        ```

        Document Chunks (Each entry has a reference_id refer to the `Reference Document List`):
        ```json
        {"reference_id": 1, "content": "..."}
        {"reference_id": 2, "content": "..."}
        ```

        Reference Document List ...
        ```
        [1] crud-0001.txt
        [2] crud-0087.txt
        ```

    我们的解析策略：
      1. 优先解析 **Reference Document List** 得到 `ref_id -> file_path` 映射
      2. 再解析 **Document Chunks** 的 JSON 行，用 reference_id 查回 file_path
      3. 每个 chunk 生成一个 Document（source=file_path）
      4. 如果只拿到 Reference Document List（mode=global 偶尔 chunks 空），仍返回一个
         聚合 Document 但 metadata 带上 file_paths 列表，Recall@K 可以算
      5. 全部失败回退到"整段一个聚合 Document"（无 file_path → Recall@K 标 None）

    同时兼容老的 `---Sources---` Markdown/CSV 格式以防 LightRAG 版本回滚。
    """
    if context is None:
        return []
    text = context if isinstance(context, str) else str(context)
    if not text.strip():
        return []

    # 路径 1：LightRAG 1.4.x 的 Reference List + Document Chunks（主路径）
    docs = _split_by_reference_list(text, mode=mode)
    if docs:
        return docs

    # 路径 2：老的 ---Sources--- Markdown/CSV 格式
    docs = _split_by_sources(text, mode=mode)
    if docs:
        return docs

    # 拆分失败：整段当一个 Document
    return [
        Document(
            page_content=text,
            metadata={
                "source": f"graph_rag:{mode}",
                "original_filename": f"graph_rag:{mode}",
                "source_file_id": "graph_rag",
                "graph_rag_mode": mode,
            },
        )
    ]


# ── LightRAG 1.4.x 路径 ──────────────────────────────────────────


# NOTE: 两处坑——
# (1) 模板里的 "Document Chunks (Each entry has a reference_id refer to the
#     `Reference Document List`)" 包含行内反引号，所以 `[^`]*?` 会提前截断。
# (2) "Reference Document List" 在 Document Chunks 的 header 里也出现过一次，
#     若不加行首锚点 `^`，lazy 匹配会从第一个误匹配的位置开始，捕获到错内容。
# 解决：(?ms) + `^` 锚定章节标题必须行首出现。
_REFERENCE_LIST_RE = __import__("re").compile(
    r"(?ms)^Reference Document List.*?\n```\s*\n(.+?)\n```"
)
_CHUNKS_BLOCK_RE = __import__("re").compile(
    r"(?ms)^Document Chunks.*?\n```json\s*\n(.+?)\n```"
)
_REF_LINE_RE = __import__("re").compile(r"^\s*\[(\d+)\]\s+(.+?)\s*$")


def _split_by_reference_list(text: str, *, mode: str) -> list[Document]:
    """解析 LightRAG 1.4.x `Reference Document List` + `Document Chunks` 格式。"""
    import json as _json

    # 1. Reference List: [1] crud-0001.txt → {1: "crud-0001.txt"}
    ref_match = _REFERENCE_LIST_RE.search(text)
    if not ref_match:
        return []
    ref_map: dict[int, str] = {}
    for ln in ref_match.group(1).splitlines():
        m = _REF_LINE_RE.match(ln)
        if m:
            try:
                ref_map[int(m.group(1))] = m.group(2).strip()
            except ValueError:
                continue
    if not ref_map:
        return []

    # 2. Document Chunks: 逐行解析 JSON（每行一个 chunk）
    chunks_match = _CHUNKS_BLOCK_RE.search(text)
    if chunks_match:
        docs: list[Document] = []
        for ln in chunks_match.group(1).splitlines():
            ln = ln.strip().rstrip(",")
            if not ln or not ln.startswith("{"):
                continue
            try:
                obj = _json.loads(ln)
            except _json.JSONDecodeError:
                continue
            ref_id = obj.get("reference_id")
            content = obj.get("content", "") or obj.get("chunk", "")
            if ref_id is None or not content:
                continue
            file_path = ref_map.get(int(ref_id))
            if not file_path:
                continue
            docs.append(_mk_doc(str(content), file_path, mode))
        if docs:
            return docs

    # 3. 没有 chunks 段（global-only 偶尔这样）：对每个 reference file 发一个
    #    micro Document（小 placeholder 内容 + 真实 file_path），让 xml_parser 产出
    #    N 个 refs、Recall@K 可以算。真正的上下文仍在 text 里送给 LLM（作为最后一个
    #    Document，source 保持 graph_rag:mode 避免与 placeholder 竞争）。
    docs_out: list[Document] = [
        Document(
            page_content=f"[LightRAG {mode} 聚合引用 · {fp}]",
            metadata={
                "source": fp,
                "original_filename": fp,
                "source_file_id": fp,
                "graph_rag_mode": mode,
            },
        )
        for fp in ref_map.values()
    ]
    docs_out.append(
        Document(
            page_content=text,
            metadata={
                "source": f"graph_rag:{mode}",
                "original_filename": f"graph_rag:{mode}",
                "source_file_id": "graph_rag",
                "graph_rag_mode": mode,
            },
        )
    )
    return docs_out


# ── 老的 ---Sources--- Markdown/CSV 路径（兼容保留）─────────────


_SOURCES_HEADER_RE = __import__("re").compile(
    r"(?ms)^\s*(?:---\s*Sources\s*---|#+\s*Sources).*?$"
)


def _split_by_sources(text: str, *, mode: str) -> list[Document]:
    """老格式：`---Sources---` 段里的 Markdown 表或 CSV，含 file_path + content。"""
    import re

    m = _SOURCES_HEADER_RE.search(text)
    if not m:
        return []
    sources_block = text[m.end():]
    lines = [ln for ln in sources_block.splitlines() if ln.strip()]
    if not lines:
        return []

    docs: list[Document] = []
    if lines[0].startswith("|"):
        header = [c.strip().lower() for c in lines[0].strip("|").split("|")]
        try:
            fpath_col = next(
                i for i, c in enumerate(header)
                if c in ("file_path", "file", "filepath", "source", "file_name")
            )
            content_col = next(
                i for i, c in enumerate(header) if c in ("content", "chunk", "text")
            )
        except StopIteration:
            return []
        for ln in lines[2:]:
            if not ln.startswith("|"):
                break
            cells = [c.strip() for c in ln.strip("|").split("|")]
            if len(cells) <= max(fpath_col, content_col):
                continue
            fp = cells[fpath_col]
            ct = cells[content_col]
            if not fp or not ct:
                continue
            docs.append(_mk_doc(ct, fp, mode))
        return docs

    import csv
    import io
    for sep in ("\t", ","):
        try:
            reader = list(csv.reader(io.StringIO("\n".join(lines)), delimiter=sep))
            if len(reader) < 2:
                continue
            header = [c.strip().lower() for c in reader[0]]
            if "file_path" not in header and "file" not in header:
                continue
            fpath_col = header.index("file_path" if "file_path" in header else "file")
            content_col = (header.index("content") if "content" in header
                           else (header.index("chunk") if "chunk" in header else -1))
            if content_col < 0:
                continue
            for row in reader[1:]:
                if len(row) <= max(fpath_col, content_col):
                    continue
                fp, ct = row[fpath_col].strip(), row[content_col].strip()
                if fp and ct:
                    docs.append(_mk_doc(ct, fp, mode))
            if docs:
                return docs
        except Exception:
            continue
    return []


def _mk_doc(content: str, file_path: str, mode: str) -> Document:
    return Document(
        page_content=content,
        metadata={
            "source": file_path,
            "original_filename": file_path,
            "source_file_id": file_path,
            "graph_rag_mode": mode,
        },
    )


# ── 索引构建 / 统计 / 清空 ──────────────────────────────────────────


async def build_graph_index(
    rag_service,
    *,
    progress_callback: Callable[[dict[str, Any]], Awaitable[None]] | None = None,
) -> dict[str, Any]:
    """增量构建 Graph RAG 索引。

    遍历 backend/data/uploads/ 下所有已向量化文档（通过 MongoDB KnowledgeDocument 查询），
    对每个文档调用 LightRAG.ainsert；LightRAG 原生会跳过已入图的 doc_id（kv_store_doc_status）。

    progress_callback 在每份文档开始/完成时被调用，推入 SSE 流。
    """
    from app.models.knowledge_document import KnowledgeDocument

    inst = await _get_lightrag_instance(rag_service)

    # 注意：KnowledgeDocument.vectorize_status 取值是 pending / processing / done / failed
    # （见 rag_service.py），不是 "completed"
    docs = await KnowledgeDocument.find(
        {"vectorize_status": "done"}
    ).to_list()

    total = len(docs)
    if progress_callback:
        await progress_callback({"phase": "start", "total": total, "processed": 0})

    processed = 0
    errors: list[dict[str, str]] = []

    for doc in docs:
        # upload 目录里的文件名是 "{file_id}{ext}"
        file_path = _find_upload_file(doc.file_id)
        if not file_path:
            errors.append({"file_id": doc.file_id, "error": "file missing on disk"})
            processed += 1
            continue

        if progress_callback:
            await progress_callback({
                "phase": "processing",
                "total": total,
                "processed": processed,
                "current_doc": doc.original_name,
            })

        try:
            text = _extract_text(file_path)
            if text.strip():
                await inst.ainsert(
                    text,
                    ids=[doc.file_id],
                    file_paths=[doc.original_name],
                )
        except Exception as e:
            logger.warning(f"LightRAG insert failed for {doc.original_name}: {e}")
            errors.append({"file_id": doc.file_id, "error": str(e)})

        processed += 1

    if progress_callback:
        await progress_callback({
            "phase": "done",
            "total": total,
            "processed": processed,
            "errors": errors,
        })

    return {"total": total, "processed": processed, "errors": errors}


def _find_upload_file(file_id: str) -> str | None:
    upload_dir = os.path.join(BACKEND_DIR, "data", "uploads")
    if not os.path.isdir(upload_dir):
        return None
    for name in os.listdir(upload_dir):
        if name.startswith(file_id):
            return os.path.join(upload_dir, name)
    return None


def _extract_text(file_path: str) -> str:
    """复用项目的文档加载器把任意格式扁平化成纯文本。"""
    try:
        from app.services.rag_service import _load_documents
    except ImportError:
        return ""
    ext = os.path.splitext(file_path)[1].lower()
    documents = _load_documents(file_path, ext, os.path.basename(file_path))
    return "\n\n".join(d.page_content for d in documents if d.page_content)


def get_graph_stats() -> dict[str, Any]:
    """读本地 graphml + kv_store_doc_status.json 返回统计，不强制实例存在。"""
    stats: dict[str, Any] = {
        "exists": False,
        "nodes": 0,
        "edges": 0,
        "documents": 0,
        "path": LIGHTRAG_DIR,
    }
    if not os.path.isdir(LIGHTRAG_DIR):
        return stats

    stats["exists"] = True

    graphml_path = os.path.join(LIGHTRAG_DIR, "graph_chunk_entity_relation.graphml")
    if os.path.exists(graphml_path):
        try:
            import networkx as nx
            g = nx.read_graphml(graphml_path)
            stats["nodes"] = g.number_of_nodes()
            stats["edges"] = g.number_of_edges()
        except Exception as e:
            logger.debug(f"read graphml failed: {e}")

    doc_status = os.path.join(LIGHTRAG_DIR, "kv_store_doc_status.json")
    if os.path.exists(doc_status):
        try:
            import json
            with open(doc_status, "r", encoding="utf-8") as f:
                data = json.load(f)
            stats["documents"] = len(data) if isinstance(data, dict) else 0
        except Exception as e:
            logger.debug(f"read doc_status failed: {e}")

    return stats


def _index_has_data() -> bool:
    """判断 LightRAG 目录是否有可用数据。没有就直接 fail-soft，不初始化实例。"""
    graphml = os.path.join(LIGHTRAG_DIR, "graph_chunk_entity_relation.graphml")
    vdb = os.path.join(LIGHTRAG_DIR, "vdb_chunks.json")
    return os.path.exists(graphml) or os.path.exists(vdb)


async def clear_graph_index() -> dict[str, Any]:
    """清空 backend/data/lightrag/ 下所有 LightRAG 状态文件。幂等。"""
    await _reset_instance()
    if os.path.isdir(LIGHTRAG_DIR):
        shutil.rmtree(LIGHTRAG_DIR)
    os.makedirs(LIGHTRAG_DIR, exist_ok=True)
    logger.warning(f"Graph RAG index cleared: {LIGHTRAG_DIR}")
    return {"cleared": True, "path": LIGHTRAG_DIR}
