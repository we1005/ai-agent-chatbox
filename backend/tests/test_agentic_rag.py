"""
Agentic RAG 三节点 + orchestrator 的单元测试。

测试策略：
  - 三个叶子函数（grade / rewrite / hallucination）：mock `get_openai`
    返回的客户端，断言 JSON 解析、fallback 行为、边界输入处理
  - orchestrator：mock `RagService` 和叶子函数，覆盖四档 × 两种 multi_query
    × fail-soft 共若干路径

用法：
  cd backend && venv/bin/python -m pytest tests/test_agentic_rag.py -v
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# 保证 "app.*" 能被 import（测试文件不在 src layout 下）
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from langchain_core.documents import Document  # noqa: E402

from app.services.agentic_rag import (  # noqa: E402
    _GRADING_PASS_THRESHOLD,
    agentic_rag_retrieve,
    check_hallucination,
    grade_documents,
    rewrite_query_for_retry,
)


# ── 工具：构造假的 OpenAI 响应 ─────────────────────────────────────────

def _mock_openai_response(content: str):
    """伪造 `client.chat.completions.create(...)` 返回的对象。"""
    msg = MagicMock()
    msg.content = content
    choice = MagicMock()
    choice.message = msg
    resp = MagicMock()
    resp.choices = [choice]
    return resp


def _patch_get_openai(content: str):
    """返回一个 context manager，用于 monkey-patch `agentic_rag._make_client`。"""
    client = MagicMock()
    client.chat.completions.create = AsyncMock(return_value=_mock_openai_response(content))
    return patch("app.services.agentic_rag._make_client", return_value=client)


def _patch_get_openai_raises(exc: Exception):
    client = MagicMock()
    client.chat.completions.create = AsyncMock(side_effect=exc)
    return patch("app.services.agentic_rag._make_client", return_value=client)


# ── 节点 1：grade_documents ────────────────────────────────────────────

class TestGradeDocuments:
    @pytest.mark.asyncio
    async def test_empty_docs(self):
        """空列表 → 空结果，不调 LLM。"""
        result = await grade_documents("query", [])
        assert result == []

    @pytest.mark.asyncio
    async def test_happy_path_full_grades(self):
        fake_json = json.dumps({
            "grades": [
                {"index": 0, "relevant": True, "reason": "直接命中"},
                {"index": 1, "relevant": False, "reason": "偏题"},
            ]
        })
        docs = [
            Document(page_content="a", metadata={}),
            Document(page_content="b", metadata={}),
        ]
        with _patch_get_openai(fake_json):
            result = await grade_documents("q", docs)
        assert len(result) == 2
        assert result[0][1] is True and result[1][1] is False
        assert result[0][2] == "直接命中"

    @pytest.mark.asyncio
    async def test_partial_grades_missing_index_defaults_relevant(self):
        """LLM 漏返某个 index → 该 doc 默认 relevant=True（fail-open）。"""
        fake_json = json.dumps({"grades": [{"index": 0, "relevant": False, "reason": "x"}]})
        docs = [
            Document(page_content="a", metadata={}),
            Document(page_content="b", metadata={}),
        ]
        with _patch_get_openai(fake_json):
            result = await grade_documents("q", docs)
        assert result[0][1] is False
        assert result[1][1] is True  # 漏返，保守判相关
        assert "fallback" in result[1][2].lower() or "no_grade" in result[1][2]

    @pytest.mark.asyncio
    async def test_llm_exception_fallback_all_relevant(self):
        """LLM 抛异常 → 全部默认 relevant（保守不过滤）。"""
        docs = [Document(page_content="a", metadata={})]
        with _patch_get_openai_raises(TimeoutError("slow")):
            result = await grade_documents("q", docs)
        assert len(result) == 1
        assert result[0][1] is True
        assert "TimeoutError" in result[0][2]

    @pytest.mark.asyncio
    async def test_malformed_json_fallback(self):
        with _patch_get_openai("not json at all"):
            result = await grade_documents("q", [Document(page_content="a", metadata={})])
        assert result[0][1] is True  # fallback all-relevant


# ── 节点 2：rewrite_query_for_retry ───────────────────────────────────

class TestRewriteQuery:
    @pytest.mark.asyncio
    async def test_empty_query(self):
        assert await rewrite_query_for_retry("", []) == ""

    @pytest.mark.asyncio
    async def test_happy_path(self):
        fake = json.dumps({"rewritten": "新的更具体的 query"})
        with _patch_get_openai(fake):
            out = await rewrite_query_for_retry("原 q", ["太宽泛"])
        assert out == "新的更具体的 query"

    @pytest.mark.asyncio
    async def test_llm_returns_same_query_returns_original(self):
        fake = json.dumps({"rewritten": "原 q"})
        with _patch_get_openai(fake):
            out = await rewrite_query_for_retry("原 q", ["..."])
        assert out == "原 q"  # 调用方据此判断为"不再改写"

    @pytest.mark.asyncio
    async def test_llm_exception_returns_original(self):
        with _patch_get_openai_raises(RuntimeError("net")):
            out = await rewrite_query_for_retry("原 q", ["..."])
        assert out == "原 q"

    @pytest.mark.asyncio
    async def test_empty_rewrite_returns_original(self):
        with _patch_get_openai(json.dumps({"rewritten": "   "})):
            out = await rewrite_query_for_retry("原 q", ["..."])
        assert out == "原 q"


# ── 节点 3：check_hallucination ───────────────────────────────────────

class TestCheckHallucination:
    @pytest.mark.asyncio
    async def test_empty_answer(self):
        r = await check_hallucination("", [Document(page_content="a", metadata={})])
        assert r["grounded"] is True
        assert r["reason"] == "empty_answer"

    @pytest.mark.asyncio
    async def test_no_docs(self):
        r = await check_hallucination("some answer", [])
        assert r["grounded"] is True
        assert r["reason"] == "no_docs_skipped"

    @pytest.mark.asyncio
    async def test_grounded_true(self):
        fake = json.dumps({"grounded": True, "reason": "完整支撑"})
        with _patch_get_openai(fake):
            r = await check_hallucination("ans", [Document(page_content="a", metadata={})])
        assert r["grounded"] is True

    @pytest.mark.asyncio
    async def test_not_grounded_with_claims(self):
        fake = json.dumps({
            "grounded": False,
            "unsupported_claims": ["声明A", "声明B", "声明C", "声明D"],
            "reason": "三处编造",
        })
        with _patch_get_openai(fake):
            r = await check_hallucination("ans", [Document(page_content="a", metadata={})])
        assert r["grounded"] is False
        assert len(r["unsupported_claims"]) == 3  # 限 3 条

    @pytest.mark.asyncio
    async def test_llm_exception_fallback_grounded(self):
        """LLM 异常 → 默认 grounded=True，避免误报警扰民。"""
        with _patch_get_openai_raises(Exception("boom")):
            r = await check_hallucination("ans", [Document(page_content="a", metadata={})])
        assert r["grounded"] is True
        assert "fallback" in r["reason"]


# ── Orchestrator：agentic_rag_retrieve ────────────────────────────────

def _mock_rag(docs_first: list[Document], docs_retry: list[Document] | None = None,
              multi_query_enabled: bool = False):
    """构造 RagService mock。"""
    rag = MagicMock()
    rag.multi_query_enabled = multi_query_enabled

    # 单 query 入口
    retriever = MagicMock()
    call_count = {"n": 0}

    async def _ainvoke(q):
        call_count["n"] += 1
        if call_count["n"] == 1:
            return docs_first
        return docs_retry if docs_retry is not None else docs_first

    retriever.ainvoke = AsyncMock(side_effect=_ainvoke)
    rag.get_retriever = MagicMock(return_value=retriever)
    # Multi-query 入口
    rag.retrieve_with_multi_query = AsyncMock(return_value=docs_first)
    return rag


class TestOrchestrator:
    @pytest.mark.asyncio
    async def test_grading_only_pass_rate_high_returns_passed(self):
        """grading_only: 通过率 ≥ 阈值，返回通过 docs，不 rewrite。"""
        docs = [
            Document(page_content=f"d{i}", metadata={"original_filename": "x.txt"})
            for i in range(5)
        ]
        rag = _mock_rag(docs)
        # mock grade_documents：3/5 通过
        with patch("app.services.agentic_rag.grade_documents",
                   new=AsyncMock(return_value=[(d, i < 3, "r") for i, d in enumerate(docs)])):
            result_docs, trace = await agentic_rag_retrieve("q", rag, False, "grading_only")
        assert len(result_docs) == 3
        assert trace["rounds"] == 1
        assert trace["pass_rate"] == 0.6
        assert trace["rewrite_history"] == ["q"]
        assert trace["degraded"] is False

    @pytest.mark.asyncio
    async def test_grading_rewrite_triggers_rewrite_on_low_pass_rate(self):
        """grading_rewrite：首轮通过率低 → 走 rewrite → 第二轮命中。"""
        docs_first = [Document(page_content="d1", metadata={})]
        docs_retry = [Document(page_content="d2", metadata={})]
        rag = _mock_rag(docs_first, docs_retry)
        # 首轮全部不通过，第二轮全部通过
        grade_calls = {"n": 0}

        async def grade_side_effect(q, docs):
            grade_calls["n"] += 1
            if grade_calls["n"] == 1:
                return [(d, False, "fail") for d in docs]
            return [(d, True, "ok") for d in docs]

        with patch("app.services.agentic_rag.grade_documents",
                   new=AsyncMock(side_effect=grade_side_effect)), \
             patch("app.services.agentic_rag.rewrite_query_for_retry",
                   new=AsyncMock(return_value="改写后 q")):
            result_docs, trace = await agentic_rag_retrieve("原 q", rag, False, "grading_rewrite")
        assert trace["rounds"] == 2
        assert trace["rewrite_history"] == ["原 q", "改写后 q"]
        assert len(result_docs) == 1
        assert result_docs[0].page_content == "d2"

    @pytest.mark.asyncio
    async def test_rewrite_max_rounds_respects_multi_query_on(self):
        """Multi-Query ON 时最多 1 次 rewrite（multi-query 已覆盖多角度）。"""
        docs = [Document(page_content="d", metadata={})]
        rag = _mock_rag(docs, multi_query_enabled=True)
        # 所有轮都通不过
        with patch("app.services.agentic_rag.grade_documents",
                   new=AsyncMock(return_value=[(d, False, "fail") for d in docs])), \
             patch("app.services.agentic_rag.rewrite_query_for_retry",
                   new=AsyncMock(return_value="new")):
            _docs, trace = await agentic_rag_retrieve("q", rag, False, "grading_rewrite")
        # multi-query on → max_rewrites=1 → rounds=2（首轮 + 1 次重试）
        assert trace["rounds"] == 2

    @pytest.mark.asyncio
    async def test_rewrite_unchanged_breaks_loop(self):
        """rewrite 返回原 query → 提前结束循环。"""
        docs = [Document(page_content="d", metadata={})]
        rag = _mock_rag(docs, multi_query_enabled=False)
        with patch("app.services.agentic_rag.grade_documents",
                   new=AsyncMock(return_value=[(d, False, "f") for d in docs])), \
             patch("app.services.agentic_rag.rewrite_query_for_retry",
                   new=AsyncMock(return_value="原 q")):  # rewriter 放弃
            _docs, trace = await agentic_rag_retrieve("原 q", rag, False, "grading_rewrite")
        assert trace["rounds"] == 1  # 没进重试

    @pytest.mark.asyncio
    async def test_empty_retrieve_returns_empty(self):
        rag = _mock_rag(docs_first=[])
        _docs, trace = await agentic_rag_retrieve("q", rag, False, "grading_only")
        assert _docs == []
        assert trace["rounds"] == 1
        assert trace["pass_rate"] == 0.0

    @pytest.mark.asyncio
    async def test_retriever_exception_degrades(self):
        """retriever 抛异常 → trace['degraded']=True，返回空不抛异常。"""
        rag = MagicMock()
        rag.multi_query_enabled = False
        retriever = MagicMock()
        retriever.ainvoke = AsyncMock(side_effect=ConnectionError("qdrant down"))
        rag.get_retriever = MagicMock(return_value=retriever)
        docs, trace = await agentic_rag_retrieve("q", rag, False, "grading_rewrite")
        assert trace["degraded"] is True
        assert docs == []

    @pytest.mark.asyncio
    async def test_threshold_constant_sanity(self):
        """保证阈值常量可控（改动时 test 会提示）。"""
        assert 0.2 <= _GRADING_PASS_THRESHOLD <= 0.5
