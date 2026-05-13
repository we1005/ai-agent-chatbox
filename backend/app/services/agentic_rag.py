"""
Agentic RAG 三节点（classic 路径专用）+ orchestrator。

三节点对应业界 canonical Agentic RAG 的核心自我纠错闭环：
  - Document Grading：LLM 评分召回文档是否相关，过滤不相关的
  - Rewrite-and-retry Loop：通过率低时改写 query 重试（orchestrator 负责）
  - Hallucination Checker：生成完检查答案是否有文档支撑

只在 classic 路径、intent=general、use_knowledge_base=True 时触发；Solo 路径不使用。
设计见 plan-doc-dir/本项目是否真的实现了Agentic-RAG.md。

所有 LLM 调用走 get_openai() + @traceable，关闭 LangSmith 追踪时零开销。
失败软着陆：JSON 解析失败 / 超时 / 异常 → 返回保守默认值，绝不抛异常到调用方。
"""

from __future__ import annotations

import logging
import os
from typing import Any, Optional

import json_repair
from jinja2 import Environment, FileSystemLoader, select_autoescape
from langchain_core.documents import Document

from app.core.config import get_settings
from app.services._langsmith import get_utility_openai, traceable

logger = logging.getLogger(__name__)
settings = get_settings()

# ── Jinja 模板：独立 env 避免污染 chat_service 的模板缓存 ──────────────
_PROMPTS_DIR = os.path.join(os.path.dirname(__file__), "..", "prompts")
_jinja_env = Environment(
    loader=FileSystemLoader(_PROMPTS_DIR),
    autoescape=select_autoescape([]),  # 我们自己在模板里用 | e
    trim_blocks=True,
    lstrip_blocks=True,
)


# ── 工具：LLM 客户端（复用项目统一入口） ────────────────────────────
def _make_client(timeout: float):
    return get_utility_openai(timeout=timeout)


# ── 工具：Document → dict（供 Jinja 渲染） ───────────────────────────
def _docs_to_prompt_chunks(docs: list[Document]) -> list[dict]:
    out = []
    for d in docs:
        md = getattr(d, "metadata", {}) or {}
        out.append({
            "filename": md.get("original_filename") or md.get("source_file_id") or "未知文件",
            # 控长：Grading / Verify 里文档太长会拉爆 token；400 字符够 LLM 判语义
            "text": (d.page_content or "")[:400],
        })
    return out


# ─────────────────────────────────────────────────────────────────────
# 节点 1：Document Grading
# ─────────────────────────────────────────────────────────────────────

@traceable(name="agentic_grade_documents", run_type="parser")
async def grade_documents(
    query: str,
    docs: list[Document],
) -> list[tuple[Document, bool, str]]:
    """一次 LLM 批量评分所有 docs。

    返回 list[(doc, relevant, reason)]，顺序与输入一致。
    失败软着陆：LLM 异常 / JSON 解析失败 → 全部判 relevant=True（保守倾向不过滤）。
    """
    if not docs:
        return []

    chunks = _docs_to_prompt_chunks(docs)
    prompt = _jinja_env.get_template("agentic_grade.j2").render(query=query, chunks=chunks)

    try:
        client = _make_client(timeout=8.0)
        resp = await client.chat.completions.create(
            model=settings.UTILITY_LLM_MODEL,
            messages=[
                {"role": "system", "content": "You are a strict but fair relevance judge."},
                {"role": "user", "content": prompt},
            ],
            response_format={"type": "json_object"},
            max_tokens=60 * max(1, len(docs)),   # 每个 doc 留 ~60 tokens
            temperature=0.0,
        )
        raw = resp.choices[0].message.content or ""
        parsed = json_repair.loads(raw)
        grades = parsed.get("grades") if isinstance(parsed, dict) else None
        if not isinstance(grades, list):
            raise ValueError(f"invalid grades type: {type(grades).__name__}")

        # 对齐 index —— 如果 LLM 少返或多返，按输入顺序匹配，缺的默认 relevant=True
        grade_by_index: dict[int, tuple[bool, str]] = {}
        for g in grades:
            if not isinstance(g, dict):
                continue
            idx = g.get("index")
            if not isinstance(idx, int):
                continue
            grade_by_index[idx] = (bool(g.get("relevant", True)), str(g.get("reason") or "")[:80])

        result: list[tuple[Document, bool, str]] = []
        for i, d in enumerate(docs):
            rel, reason = grade_by_index.get(i, (True, "no_grade_fallback_relevant"))
            result.append((d, rel, reason))
        return result

    except Exception as e:
        logger.warning(f"[AgenticRAG/grade] failed, fallback all-relevant: {type(e).__name__}: {e}")
        return [(d, True, f"fallback:{type(e).__name__}") for d in docs]


# ─────────────────────────────────────────────────────────────────────
# 节点 2：Rewrite query for retry
# ─────────────────────────────────────────────────────────────────────

@traceable(name="agentic_rewrite_query", run_type="chain")
async def rewrite_query_for_retry(
    original_query: str,
    failure_reasons: list[str],
    history_messages: Optional[list[dict]] = None,
) -> str:
    """基于前一轮 grading 失败的理由改写 query。

    失败软着陆：LLM 异常 → 返回原 query（调用方判断为"没改写"，结束循环）。
    """
    if not original_query or not original_query.strip():
        return original_query

    # 格式化历史：取最近 2 轮 user/assistant 文本
    history_txt = ""
    if history_messages:
        lines: list[str] = []
        for m in history_messages[-4:]:
            role = m.get("role", "")
            content = (m.get("content") or "").strip()[:200]
            if role in ("user", "assistant") and content:
                lines.append(f"{role}: {content}")
        history_txt = "\n".join(lines)

    prompt = _jinja_env.get_template("agentic_rewrite.j2").render(
        original_query=original_query,
        failure_reasons=failure_reasons[:3],
        history=history_txt,
    )

    try:
        client = _make_client(timeout=5.0)
        resp = await client.chat.completions.create(
            model=settings.UTILITY_LLM_MODEL,
            messages=[
                {"role": "system", "content": "You are a query rewriter for RAG retrieval."},
                {"role": "user", "content": prompt},
            ],
            response_format={"type": "json_object"},
            max_tokens=120,
            temperature=0.3,
        )
        raw = resp.choices[0].message.content or ""
        parsed = json_repair.loads(raw)
        if isinstance(parsed, dict):
            rewritten = str(parsed.get("rewritten") or "").strip()[:100]
            if rewritten and rewritten != original_query.strip():
                return rewritten
        return original_query

    except Exception as e:
        logger.warning(f"[AgenticRAG/rewrite] failed, return original: {type(e).__name__}: {e}")
        return original_query


# ─────────────────────────────────────────────────────────────────────
# 节点 3：Hallucination Check
# ─────────────────────────────────────────────────────────────────────

@traceable(name="agentic_check_hallucination", run_type="parser")
async def check_hallucination(
    answer: str,
    docs: list[Document],
) -> dict[str, Any]:
    """检查答案里的事实性声明是否有文档支撑。

    返回：{"grounded": bool, "unsupported_claims": list[str], "reason": str}
    失败软着陆：任何异常 → 返回 grounded=True（避免误报警）+ reason 带标记。
    """
    if not answer or not answer.strip():
        return {"grounded": True, "unsupported_claims": [], "reason": "empty_answer"}
    if not docs:
        # 没有召回文档时不做校验（可能是意图识别判定没必要 RAG，或 KB 为空）
        return {"grounded": True, "unsupported_claims": [], "reason": "no_docs_skipped"}

    chunks = _docs_to_prompt_chunks(docs)
    prompt = _jinja_env.get_template("agentic_verify.j2").render(
        answer=answer[:3000],    # 答案太长也截断
        chunks=chunks,
    )

    try:
        client = _make_client(timeout=8.0)
        resp = await client.chat.completions.create(
            model=settings.UTILITY_LLM_MODEL,
            messages=[
                {"role": "system", "content": "You are a strict factual grounding verifier."},
                {"role": "user", "content": prompt},
            ],
            response_format={"type": "json_object"},
            max_tokens=200,
            temperature=0.0,
        )
        raw = resp.choices[0].message.content or ""
        parsed = json_repair.loads(raw)
        if not isinstance(parsed, dict):
            raise ValueError(f"invalid type: {type(parsed).__name__}")

        grounded = bool(parsed.get("grounded", True))
        raw_claims = parsed.get("unsupported_claims") or []
        claims: list[str] = []
        if isinstance(raw_claims, list):
            for c in raw_claims:
                if isinstance(c, str):
                    claims.append(c.strip()[:120])
                if len(claims) >= 3:
                    break
        reason = str(parsed.get("reason") or "")[:120]
        return {"grounded": grounded, "unsupported_claims": claims, "reason": reason or "model_json"}

    except Exception as e:
        logger.warning(f"[AgenticRAG/hallucination] failed, fallback grounded: {type(e).__name__}: {e}")
        return {"grounded": True, "unsupported_claims": [], "reason": f"fallback:{type(e).__name__}"}


# ─────────────────────────────────────────────────────────────────────
# Orchestrator：`agentic_rag_retrieve`（骨架版，暂不实现循环，留给 Commit 4）
# ─────────────────────────────────────────────────────────────────────

# Grading 通过率软阈值：高于此值直接用已通过的 docs 生成，不重写（partial pass）
# 低于此值才触发 rewrite 重试（如果当前 mode 允许）
_GRADING_PASS_THRESHOLD = 0.30


async def _retrieve_once(
    query: str,
    rag: Any,
    use_reranker: bool,
    use_multi_query: bool,
) -> list[Document]:
    """单轮检索：按 use_multi_query 决定走哪个入口。"""
    if use_multi_query:
        return await rag.retrieve_with_multi_query(
            original_query=query,
            use_reranker=use_reranker,
        )
    retriever = rag.get_retriever(use_reranker=use_reranker)
    return await retriever.ainvoke(query)


@traceable(name="agentic_rag_retrieve", run_type="chain")
async def agentic_rag_retrieve(
    query: str,
    rag: Any,                 # RagService 实例（避免循环 import 不显式标注类型）
    use_reranker: bool,
    mode: str,                # "grading_only" | "grading_rewrite" | "full"
    history_messages: Optional[list[dict]] = None,
) -> tuple[list[Document], dict[str, Any]]:
    """classic 路径的 Agentic RAG 入口（完整 loop 版）。

    流程：
      ┌── retrieve (首轮：可能 multi-query) ──┐
      │          ↓                            │
      │        grade                          │
      │          ↓                            │
      │   pass_rate >= 30%  → 用通过 docs →  generate
      │          ↓ else                       │
      │   rewrite_loop（上限 1-2 次）→ retrieve（单 query）→ grade
      └── 轮次耗尽 → 用最后一轮通过 docs ────┘

    返回 (docs, trace)。trace 含：
      - rounds: int                         实际跑了几轮检索（含首轮）
      - pass_rate: float                    最后一轮 grading 通过率
      - rewrite_history: list[str]          每一轮的 query（index 0 = 原 query）
      - degraded: bool                      是否因异常降级
      - mode: str                           传入的档位（便于日志 / LangSmith 过滤）

    失败降级：任何一步 LLM / retriever 异常 → trace['degraded']=True，返回当前已有 docs 或空 list。
    """
    from app.services.rag_service import _mode_at_least

    trace: dict[str, Any] = {
        "rounds": 0,
        "pass_rate": 0.0,
        "rewrite_history": [query],
        "degraded": False,
        "mode": mode,
    }

    enable_rewrite = _mode_at_least(mode, "grading_rewrite")
    use_multi_query = bool(getattr(rag, "multi_query_enabled", False))
    # Multi-Query 已经覆盖多角度，rewrite 边际收益低，上限降 1
    max_rewrites = 1 if use_multi_query else 2
    if not enable_rewrite:
        max_rewrites = 0

    current_query = query
    passed_docs: list[Document] = []

    try:
        # ──── 首轮 ────
        docs = await _retrieve_once(current_query, rag, use_reranker, use_multi_query)
        trace["rounds"] = 1

        if not docs:
            logger.info("[AgenticRAG] round=1 retrieved=0, no docs to grade")
            return [], trace

        graded = await grade_documents(current_query, docs)
        passed_docs = [d for (d, rel, _r) in graded if rel]
        pass_rate = len(passed_docs) / max(1, len(graded))
        trace["pass_rate"] = round(pass_rate, 3)
        logger.info(
            f"[AgenticRAG] round=1 q={current_query!r} retrieved={len(docs)} "
            f"passed={len(passed_docs)} pass_rate={pass_rate:.2f}"
        )

        # 通过率够高 → 用 passed 直接返回
        if pass_rate >= _GRADING_PASS_THRESHOLD or not enable_rewrite:
            # 如果 passed 为空（全部判不相关）但通过率不到阈值又不能 rewrite，
            # 降级返回原始 docs（fail-soft：宁多勿少）
            return (passed_docs if passed_docs else docs), trace

        # ──── Rewrite 重试循环 ────
        failure_reasons = [r for (_d, rel, r) in graded if not rel][:3]
        retry_docs: list[Document] = []  # 每次重试后的 docs（覆盖上一轮）

        for attempt in range(1, max_rewrites + 1):
            rewritten = await rewrite_query_for_retry(
                original_query=query,      # 始终以原 query 为参考，不是上一轮 query
                failure_reasons=failure_reasons,
                history_messages=history_messages,
            )
            trace["rewrite_history"].append(rewritten)

            # 若 rewriter 返回原 query（表示放弃），结束循环
            if rewritten.strip() == current_query.strip():
                logger.info(
                    f"[AgenticRAG] round={attempt + 1} rewrite unchanged, break loop"
                )
                break

            current_query = rewritten
            # 重试阶段永远单 query（不再叠加 multi-query，避免成本放大）
            retry_docs = await _retrieve_once(
                current_query, rag, use_reranker, use_multi_query=False
            )
            trace["rounds"] = attempt + 1

            if not retry_docs:
                logger.info(f"[AgenticRAG] round={attempt + 1} rewritten retrieved=0")
                continue

            graded = await grade_documents(current_query, retry_docs)
            retry_passed = [d for (d, rel, _r) in graded if rel]
            pass_rate = len(retry_passed) / max(1, len(graded))
            trace["pass_rate"] = round(pass_rate, 3)
            logger.info(
                f"[AgenticRAG] round={attempt + 1} q={current_query!r} "
                f"retrieved={len(retry_docs)} passed={len(retry_passed)} "
                f"pass_rate={pass_rate:.2f}"
            )

            if retry_passed:
                passed_docs = retry_passed

            if pass_rate >= _GRADING_PASS_THRESHOLD:
                return passed_docs, trace

            failure_reasons = [r for (_d, rel, r) in graded if not rel][:3]

        # 循环耗尽：返回累积的 passed（如果有），否则降级到最后一轮原始 docs
        if passed_docs:
            return passed_docs, trace
        if retry_docs:
            return retry_docs, trace
        return docs, trace

    except Exception as e:
        logger.warning(
            f"[AgenticRAG] orchestrator exception, degrading to classical: "
            f"{type(e).__name__}: {e}"
        )
        trace["degraded"] = True
        # 返回已拿到的任意 docs；实在没有就空
        fallback = passed_docs or []
        return fallback, trace
