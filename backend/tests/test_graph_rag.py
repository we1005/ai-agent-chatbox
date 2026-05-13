"""
Graph RAG（LightRAG）适配层单测。

测试策略：
  - `get_graph_stats` / `_context_to_documents` / `_index_has_data`：纯函数，直接打入
  - `graph_rag_retrieve`：mock _get_lightrag_instance + _index_has_data 覆盖 happy / empty-index
    / timeout / query-error / empty-context 五条 fail-soft 路径
  - `clear_graph_index`：在临时目录验证幂等

用法：
  cd backend && venv/bin/python -m pytest tests/test_graph_rag.py -v
"""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services import graph_rag as gr  # noqa: E402


# ── _context_to_documents ─────────────────────────────────────────────


def test_context_to_documents_empty():
    assert gr._context_to_documents(None, mode="hybrid") == []
    assert gr._context_to_documents("", mode="hybrid") == []
    assert gr._context_to_documents("   \n\t ", mode="hybrid") == []


def test_context_to_documents_wraps_text():
    docs = gr._context_to_documents(
        "---Entities---\nAlice\n---Sources---\nchunk-1", mode="local"
    )
    assert len(docs) == 1
    assert "Alice" in docs[0].page_content
    assert docs[0].metadata["graph_rag_mode"] == "local"
    assert docs[0].metadata["source"] == "graph_rag:local"


# ── LightRAG 1.4.x 新格式解析 ─────────────────────────────────────────


_LIGHTRAG_1_4_CONTEXT = """Knowledge Graph Data (Entity):

```json
{"entity_name": "花丝云起", "type": "artifact", "description": "..."}
{"entity_name": "MING DESIGN STUDIO", "type": "org", "description": "..."}
```

Knowledge Graph Data (Relationship):

```json
{"source": "花丝云起", "target": "MING DESIGN STUDIO", "description": "..."}
```

Document Chunks (Each entry has a reference_id refer to the `Reference Document List`):

```json
{"reference_id": 1, "content": "潮宏基珠宝联合 MING DESIGN STUDIO..."}
{"reference_id": 2, "content": "花丝云起系列灵感来自云..."}
```

Reference Document List (Each entry starts with a [reference_id] ...):

```
[1] crud-0089.txt
[2] crud-0045.txt
```
"""


def test_split_by_reference_list_happy():
    docs = gr._split_by_reference_list(_LIGHTRAG_1_4_CONTEXT, mode="hybrid")
    assert len(docs) == 2
    sources = {d.metadata["source"] for d in docs}
    assert sources == {"crud-0089.txt", "crud-0045.txt"}
    # page_content 是真实 chunk 内容，不是聚合 context
    assert "潮宏基" in docs[0].page_content or "潮宏基" in docs[1].page_content


def test_split_by_reference_list_no_chunks_section():
    """global mode 偶尔只有 Reference List，没有 Document Chunks 段。
    预期：每个 ref file 发一个 placeholder Document + 最后聚合 Document。"""
    text = """Knowledge Graph Data (Entity):

```json
{"entity_name": "foo"}
```

Reference Document List:

```
[1] crud-0001.txt
[2] crud-0002.txt
```
"""
    docs = gr._split_by_reference_list(text, mode="global")
    # 2 个 placeholder + 1 个聚合
    assert len(docs) == 3
    placeholder_sources = {d.metadata["source"] for d in docs[:-1]}
    assert placeholder_sources == {"crud-0001.txt", "crud-0002.txt"}
    # 最后一个是聚合，source 是 graph_rag:global
    assert docs[-1].metadata["source"] == "graph_rag:global"


def test_split_by_reference_list_missing_returns_empty():
    """没有 Reference List 段 → 返回 []（让主 dispatcher 走下一条路径）"""
    text = "Knowledge Graph Data (Entity):\n```json\n{}\n```\n"
    assert gr._split_by_reference_list(text, mode="naive") == []


def test_context_to_documents_prefers_14x_over_old_sources():
    """同时有 1.4.x 和老 ---Sources--- 时，用 1.4.x 路径。"""
    docs = gr._context_to_documents(_LIGHTRAG_1_4_CONTEXT, mode="hybrid")
    assert len(docs) == 2
    sources = {d.metadata["source"] for d in docs}
    assert sources == {"crud-0089.txt", "crud-0045.txt"}


def test_context_to_documents_fallback_to_aggregate_when_unparseable():
    """完全不认识的格式 → 单 Document，source=graph_rag:mode。"""
    docs = gr._context_to_documents("just some random text with no structure", mode="local")
    assert len(docs) == 1
    assert docs[0].metadata["source"] == "graph_rag:local"


# ── _index_has_data / get_graph_stats / clear_graph_index ─────────────


def test_index_has_data_false_when_missing(tmp_path, monkeypatch):
    monkeypatch.setattr(gr, "LIGHTRAG_DIR", str(tmp_path / "empty"))
    assert gr._index_has_data() is False


def test_index_has_data_true_with_graphml(tmp_path, monkeypatch):
    d = tmp_path / "lightrag"
    d.mkdir()
    (d / "graph_chunk_entity_relation.graphml").write_text("<graphml/>")
    monkeypatch.setattr(gr, "LIGHTRAG_DIR", str(d))
    assert gr._index_has_data() is True


def test_get_graph_stats_empty_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(gr, "LIGHTRAG_DIR", str(tmp_path / "does_not_exist"))
    s = gr.get_graph_stats()
    assert s["exists"] is False
    assert s["nodes"] == 0 and s["edges"] == 0 and s["documents"] == 0


def test_get_graph_stats_reads_graphml(tmp_path, monkeypatch):
    d = tmp_path / "lightrag"
    d.mkdir()
    monkeypatch.setattr(gr, "LIGHTRAG_DIR", str(d))

    import networkx as nx
    g = nx.DiGraph()
    g.add_edge("A", "B")
    g.add_edge("B", "C")
    nx.write_graphml(g, d / "graph_chunk_entity_relation.graphml")
    (d / "kv_store_doc_status.json").write_text('{"doc-1": {}, "doc-2": {}}')

    s = gr.get_graph_stats()
    assert s["exists"] is True
    assert s["nodes"] == 3
    assert s["edges"] == 2
    assert s["documents"] == 2


@pytest.mark.asyncio
async def test_clear_graph_index_idempotent(tmp_path, monkeypatch):
    d = tmp_path / "lightrag"
    d.mkdir()
    (d / "junk.json").write_text("{}")
    monkeypatch.setattr(gr, "LIGHTRAG_DIR", str(d))

    r1 = await gr.clear_graph_index()
    assert r1["cleared"] is True
    assert not (d / "junk.json").exists()
    # 再次清空：目录被重建，仍可调用
    r2 = await gr.clear_graph_index()
    assert r2["cleared"] is True


# ── graph_rag_retrieve fail-soft ──────────────────────────────────────


@pytest.mark.asyncio
async def test_graph_rag_retrieve_empty_index(monkeypatch):
    monkeypatch.setattr(gr, "_index_has_data", lambda: False)
    docs, trace = await gr.graph_rag_retrieve("q", "hybrid", rag_service=MagicMock())
    assert docs == []
    assert trace["degraded"] is True
    assert trace["reason"] == "index_empty"


@pytest.mark.asyncio
async def test_graph_rag_retrieve_init_error(monkeypatch):
    monkeypatch.setattr(gr, "_index_has_data", lambda: True)

    async def _raise(*a, **k):
        raise RuntimeError("boom")

    monkeypatch.setattr(gr, "_get_lightrag_instance", _raise)
    docs, trace = await gr.graph_rag_retrieve("q", "hybrid", rag_service=MagicMock())
    assert docs == []
    assert trace["degraded"] is True
    assert "init_error" in trace["reason"]


@pytest.mark.asyncio
async def test_graph_rag_retrieve_timeout(monkeypatch):
    monkeypatch.setattr(gr, "_index_has_data", lambda: True)
    fake_inst = MagicMock()

    async def _slow(*a, **k):
        await asyncio.sleep(10)
        return "never"

    fake_inst.aquery = _slow

    async def _get(*a, **k):
        return fake_inst

    monkeypatch.setattr(gr, "_get_lightrag_instance", _get)
    docs, trace = await gr.graph_rag_retrieve(
        "q", "hybrid", rag_service=MagicMock(), timeout=0.05
    )
    assert docs == []
    assert trace["degraded"] is True
    assert trace["reason"] == "timeout"


@pytest.mark.asyncio
async def test_graph_rag_retrieve_query_error(monkeypatch):
    monkeypatch.setattr(gr, "_index_has_data", lambda: True)
    fake_inst = MagicMock()
    fake_inst.aquery = AsyncMock(side_effect=ValueError("kaboom"))

    async def _get(*a, **k):
        return fake_inst

    monkeypatch.setattr(gr, "_get_lightrag_instance", _get)
    docs, trace = await gr.graph_rag_retrieve("q", "hybrid", rag_service=MagicMock())
    assert docs == []
    assert trace["degraded"] is True
    assert "query_error" in trace["reason"]


@pytest.mark.asyncio
async def test_graph_rag_retrieve_empty_context(monkeypatch):
    monkeypatch.setattr(gr, "_index_has_data", lambda: True)
    fake_inst = MagicMock()
    fake_inst.aquery = AsyncMock(return_value="")

    async def _get(*a, **k):
        return fake_inst

    monkeypatch.setattr(gr, "_get_lightrag_instance", _get)
    docs, trace = await gr.graph_rag_retrieve("q", "hybrid", rag_service=MagicMock())
    assert docs == []
    assert trace["degraded"] is True
    assert trace["reason"] == "empty_context"


@pytest.mark.asyncio
async def test_graph_rag_retrieve_happy(monkeypatch):
    monkeypatch.setattr(gr, "_index_has_data", lambda: True)
    fake_inst = MagicMock()
    fake_inst.aquery = AsyncMock(return_value="---Entities---\nA\n---Sources---\nchunk")

    async def _get(*a, **k):
        return fake_inst

    monkeypatch.setattr(gr, "_get_lightrag_instance", _get)
    docs, trace = await gr.graph_rag_retrieve("q", "local", rag_service=MagicMock())
    assert len(docs) == 1
    assert trace["degraded"] is False
    assert trace["mode"] == "local"
    assert trace["docs_count"] == 1


# ── RagService setters 契约 ───────────────────────────────────────────


def test_rag_service_graph_rag_setters():
    from app.services.rag_service import (  # noqa: E402
        RagService,
        _GRAPH_RAG_QUERY_MODES,
    )

    rag = RagService.__new__(RagService)
    rag.graph_rag_enabled = False
    rag.graph_rag_query_mode = "hybrid"

    # 合法 mode
    for m in _GRAPH_RAG_QUERY_MODES:
        rag.set_graph_rag_query_mode(m)
        assert rag.graph_rag_query_mode == m

    # 非法 mode 抛 ValueError
    with pytest.raises(ValueError):
        rag.set_graph_rag_query_mode("not_a_mode")

    # 开关
    rag.set_graph_rag_enabled(True)
    assert rag.graph_rag_enabled is True
    rag.set_graph_rag_enabled(False)
    assert rag.graph_rag_enabled is False
