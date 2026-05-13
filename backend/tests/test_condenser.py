"""P2.1 · Condenser 骨架 + RecentBufferCondenser 单测。

用 fake Event 对象替身（不需要 Mongo）；所有断言围绕 turn_id 切片逻辑。
"""

from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services.condenser import (  # noqa: E402
    CondenseContext,
    LLMSummarizingCondenser,
    PipelineCondenser,
    RecentBufferCondenser,
    ToolOutputCondenser,
    events_to_messages,
)


# ── 替身 Event ────────────────────────────────────────────────────


def _ev(turn_id: int, kind: str, content: str = "", role: str | None = None, removed: bool = False, idx: int = 0):
    m = MagicMock()
    m.turn_id = turn_id
    m.kind = kind
    m.content = content
    m.role = role if role is not None else (
        "user" if kind == "user_msg"
        else "assistant" if kind == "assistant_msg"
        else None
    )
    # created_at 用 idx 保证稳定排序
    m.created_at = datetime(2026, 4, 22, 0, 0, 0, idx, tzinfo=timezone.utc)
    m.metadata = {"removed": True} if removed else {}
    return m


def _simple_conv(n_turns: int) -> list:
    """造 n_turns 轮 user+assistant 的简单序列。turn_id 从 1 起。"""
    events = []
    for t in range(1, n_turns + 1):
        events.append(_ev(t, "user_msg", f"Q{t}", idx=t * 2))
        events.append(_ev(t, "assistant_msg", f"A{t}", idx=t * 2 + 1))
    return events


# ── RecentBufferCondenser ─────────────────────────────────────────


@pytest.mark.asyncio
async def test_recent_buffer_empty():
    c = RecentBufferCondenser(max_recent_turns=5)
    out = await c.condense([], CondenseContext())
    assert out == []


@pytest.mark.asyncio
async def test_recent_buffer_shorter_than_budget():
    """只有 3 轮，max_recent_turns=5 → 全部保留。"""
    c = RecentBufferCondenser(max_recent_turns=5)
    events = _simple_conv(3)
    ctx = CondenseContext()
    out = await c.condense(events, ctx)
    assert len(out) == 6  # 3 × 2
    assert ctx.trace["recent_buffer"]["dropped_event_count"] == 0


@pytest.mark.asyncio
async def test_recent_buffer_drops_old_turns():
    """10 轮，max=3 → 只保留 turn 8/9/10（6 条 event）。"""
    c = RecentBufferCondenser(max_recent_turns=3)
    events = _simple_conv(10)
    ctx = CondenseContext()
    out = await c.condense(events, ctx)
    assert len(out) == 6
    # 都是 turn_id ≥ 8
    assert all(e.turn_id >= 8 for e in out)
    assert ctx.trace["recent_buffer"]["kept_turns"] == 3
    assert ctx.trace["recent_buffer"]["cutoff_turn_id"] == 8
    assert ctx.trace["recent_buffer"]["dropped_event_count"] == 14  # 7 轮 × 2


@pytest.mark.asyncio
async def test_recent_buffer_preserves_summary():
    """即便 summary 的 turn_id 早于 cutoff，也要保留（摘要代表早期压缩）。"""
    c = RecentBufferCondenser(max_recent_turns=3)
    events = _simple_conv(10)
    summary = _ev(2, "summary", "摘要：前 7 轮讨论过天气", idx=100)
    events_with_summary = events + [summary]
    ctx = CondenseContext()
    out = await c.condense(events_with_summary, ctx)
    # summary 保留 + 最近 3 轮的 6 条 → 7 条
    assert len(out) == 7
    assert any(e.kind == "summary" for e in out)


@pytest.mark.asyncio
async def test_recent_buffer_preserves_memory_flush_and_intent_routed():
    """memory_flush / intent_routed 同样受保护。"""
    c = RecentBufferCondenser(max_recent_turns=2)
    events = _simple_conv(5)
    mem = _ev(1, "memory_flush", '{"action":"ADD"}', idx=200)
    intent = _ev(3, "intent_routed", '{"strategy":"kb"}', idx=201)
    ctx = CondenseContext()
    out = await c.condense(events + [mem, intent], ctx)
    # 最近 2 轮 = 4 条 + 2 条受保护 = 6 条
    assert len(out) == 6
    kinds = {e.kind for e in out}
    assert "memory_flush" in kinds and "intent_routed" in kinds


@pytest.mark.asyncio
async def test_recent_buffer_invalid_max_raises():
    with pytest.raises(ValueError):
        RecentBufferCondenser(max_recent_turns=0)


# ── PipelineCondenser ─────────────────────────────────────────────


class _TagCondenser:
    """测试用：在每个 event content 前加 tag，并记录调用次数到 ctx.trace。"""
    def __init__(self, tag: str):
        self.tag = tag

    async def condense(self, events, ctx):
        for e in events:
            e.content = f"[{self.tag}] {e.content}"
        ctx.trace.setdefault("pipeline_order", []).append(self.tag)
        return events


@pytest.mark.asyncio
async def test_pipeline_runs_steps_in_order():
    p = PipelineCondenser([_TagCondenser("A"), _TagCondenser("B"), _TagCondenser("C")])
    ctx = CondenseContext()
    events = _simple_conv(1)
    out = await p.condense(events, ctx)
    assert ctx.trace["pipeline_order"] == ["A", "B", "C"]
    assert all(e.content.startswith("[C] [B] [A]") for e in out)


@pytest.mark.asyncio
async def test_pipeline_empty_steps_passthrough():
    p = PipelineCondenser([])
    events = _simple_conv(2)
    out = await p.condense(events, CondenseContext())
    assert len(out) == 4


# ── events_to_messages ─────────────────────────────────────────────


def test_events_to_messages_basic():
    events = _simple_conv(2)
    msgs = events_to_messages(events)
    assert msgs == [
        {"role": "user", "content": "Q1"},
        {"role": "assistant", "content": "A1"},
        {"role": "user", "content": "Q2"},
        {"role": "assistant", "content": "A2"},
    ]


def test_events_to_messages_summary_becomes_system():
    events = [
        _ev(1, "summary", "前 20 轮摘要：用户问了 X 和 Y", idx=10),
        _ev(21, "user_msg", "Q21", idx=20),
        _ev(21, "assistant_msg", "A21", idx=21),
    ]
    msgs = events_to_messages(events)
    assert msgs[0] == {"role": "system", "content": "[历史摘要] 前 20 轮摘要：用户问了 X 和 Y"}
    assert msgs[1]["role"] == "user"


def test_events_to_messages_filters_removed():
    events = [
        _ev(1, "user_msg", "Q1", idx=1),
        _ev(1, "assistant_msg", "A1-old", removed=True, idx=2),
        _ev(1, "assistant_msg", "A1-new", idx=3),
    ]
    msgs = events_to_messages(events)
    assert len(msgs) == 2
    assert msgs[1]["content"] == "A1-new"


# ── LLMSummarizingCondenser（P2.2）─────────────────────────────────


def _make_stub_llm(return_text: str = "摘要文本", raise_exc: Exception | None = None):
    calls = []
    async def _fn(prompt: str) -> str:
        calls.append(prompt)
        if raise_exc:
            raise raise_exc
        return return_text
    _fn.calls = calls  # type: ignore[attr-defined]
    return _fn


@pytest.mark.asyncio
async def test_llm_summary_not_fired_below_threshold():
    """body 未满 max_size → 不调 LLM。"""
    stub = _make_stub_llm("不应被调用")
    c = LLMSummarizingCondenser(max_size=10, keep_first=1, llm_summary_fn=stub)
    events = _simple_conv(3)  # 6 个 event < 10
    ctx = CondenseContext()
    out = await c.condense(events, ctx)
    assert len(out) == 6
    assert ctx.trace["llm_summary"]["fired"] is False
    assert len(stub.calls) == 0


@pytest.mark.asyncio
async def test_llm_summary_fires_above_threshold():
    """body 超 max_size → 触发摘要，输出 = head + summary + tail。"""
    stub = _make_stub_llm("简化后的任务脉络摘要")
    c = LLMSummarizingCondenser(max_size=6, keep_first=1, llm_summary_fn=stub)
    events = _simple_conv(10)  # 20 events
    ctx = CondenseContext(conversation_id="conv-test")
    out = await c.condense(events, ctx)

    # head(keep_first=1) + summary(1) + tail(max_size//2=3) = 5
    assert len(out) == 5
    assert out[0].kind == "user_msg"  # head
    assert out[1].kind == "summary"
    assert out[1].content == "简化后的任务脉络摘要"
    assert ctx.trace["llm_summary"]["fired"] is True
    assert ctx.trace["llm_summary"]["kept_head"] == 1
    assert ctx.trace["llm_summary"]["kept_tail"] == 3
    assert ctx.trace["llm_summary"]["forgotten"] == 16
    assert len(stub.calls) == 1


@pytest.mark.asyncio
async def test_llm_summary_uses_previous_summary():
    """存在旧 summary → 生成新 summary 时 prompt 里有 [前一次摘要]。"""
    stub = _make_stub_llm("新摘要")
    c = LLMSummarizingCondenser(max_size=6, keep_first=1, llm_summary_fn=stub)
    events = _simple_conv(10)
    prev = _ev(2, "summary", "前一次的摘要内容", idx=999)
    ctx = CondenseContext(conversation_id="c1")
    out = await c.condense(events + [prev], ctx)

    assert len(stub.calls) == 1
    prompt = stub.calls[0]
    assert "[前一次摘要]" in prompt
    assert "前一次的摘要内容" in prompt
    # 新 summary 的 metadata 指向旧 summary（prev_summary_id）
    new_sum = [e for e in out if e.kind == "summary"][0]
    assert new_sum.content == "新摘要"
    assert "prev_summary_id" in new_sum.metadata


@pytest.mark.asyncio
async def test_llm_summary_failsoft_on_llm_error():
    """LLM 异常 → 不 raise，沿用旧 summary；degraded=True。"""
    stub = _make_stub_llm(raise_exc=TimeoutError("api timeout"))
    c = LLMSummarizingCondenser(max_size=6, keep_first=1, llm_summary_fn=stub)
    events = _simple_conv(10)
    prev = _ev(2, "summary", "旧摘要", idx=999)
    ctx = CondenseContext(conversation_id="c1")
    out = await c.condense(events + [prev], ctx)

    summaries = [e for e in out if e.kind == "summary"]
    assert len(summaries) == 1
    assert summaries[0].content == "旧摘要"  # 保留旧的
    assert ctx.trace["llm_summary"]["degraded"] is True


@pytest.mark.asyncio
async def test_llm_summary_failsoft_no_prev_summary():
    """LLM 异常 + 没有旧 summary → out 里也没 summary event（但 head+tail 仍在）。"""
    stub = _make_stub_llm(raise_exc=RuntimeError("boom"))
    c = LLMSummarizingCondenser(max_size=6, keep_first=1, llm_summary_fn=stub)
    events = _simple_conv(10)
    ctx = CondenseContext()
    out = await c.condense(events, ctx)

    assert not any(e.kind == "summary" for e in out)
    # head(1) + tail(3) = 4
    assert len(out) == 4


@pytest.mark.asyncio
async def test_llm_summary_invalid_max_size():
    with pytest.raises(ValueError):
        LLMSummarizingCondenser(max_size=3)


@pytest.mark.asyncio
async def test_llm_summary_invalid_keep_first():
    with pytest.raises(ValueError):
        LLMSummarizingCondenser(max_size=10, keep_first=5)  # >= max_size/2


@pytest.mark.asyncio
async def test_llm_summary_with_pipeline_then_recent_buffer():
    """端到端：先摘要 → 再 recent buffer → 输出结构应稳定。"""
    summary_stub = _make_stub_llm("中段被压缩成这段摘要")
    pipeline = PipelineCondenser([
        LLMSummarizingCondenser(max_size=6, keep_first=1, llm_summary_fn=summary_stub),
        RecentBufferCondenser(max_recent_turns=2),
    ])
    events = _simple_conv(10)
    ctx = CondenseContext(conversation_id="c1")
    out = await pipeline.condense(events, ctx)

    # 摘要阶段：head(turn=1 user_msg) + summary(覆盖 turn 1-9) + tail(最后 3 event)
    # 10 轮 = [u1,a1,u2,a2,...,u10,a10]，tail=3 取末三条 = [a9, u10, a10]
    # RecentBuffer(max=2)：非 protected turns = [1, 9, 10]，cutoff=9 → 丢 turn=1 的 head
    # 结果应为：summary(protected) + a9 + u10 + a10 = 4 event
    kinds = [e.kind for e in out]
    assert "summary" in kinds
    assert kinds.count("user_msg") == 1       # 只剩 u10
    assert kinds.count("assistant_msg") == 2  # a9 + a10


# ── Summary event 可被后续 condenser 当 prev_summary 读（P2.3 闭环）──


@pytest.mark.asyncio
async def test_summary_feeds_back_into_next_round():
    """SimpleNamespace 替身 summary 被喂回 condenser 时，作为 prev_summary 参与。"""
    # 第一轮：触发摘要
    stub1 = _make_stub_llm("第一轮摘要：讨论了 A 和 B")
    c = LLMSummarizingCondenser(max_size=6, keep_first=1, llm_summary_fn=stub1)
    round1_out = await c.condense(_simple_conv(10), CondenseContext(conversation_id="c1"))
    summary_like = next(e for e in round1_out if e.kind == "summary")
    assert summary_like.content == "第一轮摘要：讨论了 A 和 B"
    # 替身有 id=None（标记"尚未落盘"，由 chat_stream 负责 persist）
    assert summary_like.id is None

    # 第二轮：再塞 10 轮进去 + 上轮 summary → 新摘要应含"前一次摘要"字样
    stub2 = _make_stub_llm("第二轮摘要：继续讨论 C")
    new_events = _simple_conv(10) + [summary_like]
    c2 = LLMSummarizingCondenser(max_size=6, keep_first=1, llm_summary_fn=stub2)
    round2_out = await c2.condense(new_events, CondenseContext(conversation_id="c1"))
    assert len(stub2.calls) == 1
    assert "前一次摘要" in stub2.calls[0]
    assert "第一轮摘要：讨论了 A 和 B" in stub2.calls[0]
    new_sum = next(e for e in round2_out if e.kind == "summary" and e.content == "第二轮摘要：继续讨论 C")
    assert new_sum.metadata["prev_summary_id"] is not None or new_sum.metadata["prev_summary_id"] == ""


# ── events_to_messages 的剩余 case ─────────────────────────────────


def test_events_to_messages_skips_tool_and_internal():
    events = [
        _ev(1, "user_msg", "Q1", idx=1),
        _ev(1, "tool_call", "search(x)", idx=2),
        _ev(1, "tool_result", "{...}", idx=3),
        _ev(1, "memory_flush", '{"action":"ADD"}', idx=4),
        _ev(1, "intent_routed", '{"strategy":"kb"}', idx=5),
        _ev(1, "assistant_msg", "A1", idx=6),
    ]
    msgs = events_to_messages(events)
    assert len(msgs) == 2  # 只有 user_msg + assistant_msg 进 LLM
    assert msgs[0]["role"] == "user"
    assert msgs[1]["role"] == "assistant"


# ── ToolOutputCondenser（P4.4）─────────────────────────────


@pytest.mark.asyncio
async def test_tool_output_condenser_short_passthrough():
    c = ToolOutputCondenser(max_chars_per_tool=500)
    short = _ev(1, "tool_result", "x" * 100, idx=1)
    ctx = CondenseContext()
    out = await c.condense([short], ctx)
    assert out[0] is short
    assert ctx.trace["tool_output"]["pruned_events"] == 0


@pytest.mark.asyncio
async def test_tool_output_condenser_long_truncates():
    c = ToolOutputCondenser(max_chars_per_tool=300, head_chars=50, tail_chars=50)
    long_text = "HEAD" + "x" * 5000 + "TAIL"
    e = _ev(1, "tool_result", long_text, idx=1)
    ctx = CondenseContext()
    out = await c.condense([e], ctx)
    assert out[0].content != long_text
    assert len(out[0].content) < len(long_text) // 2
    assert "HEAD" in out[0].content
    assert "TAIL" in out[0].content
    # 原文保留在 metadata
    assert out[0].metadata["raw_content"] == long_text
    assert out[0].metadata["pruned_by"] == "tool_output_condenser"


@pytest.mark.asyncio
async def test_tool_output_condenser_error_lines_extracted():
    c = ToolOutputCondenser(max_chars_per_tool=200, head_chars=50, tail_chars=50)
    content = (
        "ok line 1\n"
        "ok line 2\n"
        "…" * 500 +
        "\nERROR: connection timeout\n"
        "traceback: something\n"
        "ok again"
    )
    e = _ev(1, "tool_result", content, idx=1)
    ctx = CondenseContext()
    out = await c.condense([e], ctx)
    # 错误行应该被抽取
    assert "ERROR: connection timeout" in out[0].content or "traceback" in out[0].content.lower()


@pytest.mark.asyncio
async def test_tool_output_condenser_skip_non_tool_events():
    c = ToolOutputCondenser(max_chars_per_tool=100)
    long = "x" * 1000
    events = [
        _ev(1, "user_msg", long, idx=1),         # 不动
        _ev(1, "assistant_msg", long, idx=2),    # 不动
        _ev(1, "tool_result", long, idx=3),      # 应被裁
    ]
    ctx = CondenseContext()
    out = await c.condense(events, ctx)
    # user/assistant 保持原内容
    assert out[0].content == long
    assert out[1].content == long
    # tool_result 被裁
    assert out[2].content != long


@pytest.mark.asyncio
async def test_tool_output_condenser_invalid_size():
    with pytest.raises(ValueError):
        ToolOutputCondenser(max_chars_per_tool=50)


@pytest.mark.asyncio
async def test_tool_output_condenser_llm_summary_cache():
    """同 content 第二次不再调 LLM。"""
    call_count = {"n": 0}
    async def _fn(prompt):
        call_count["n"] += 1
        return "结构化摘要文本"
    c = ToolOutputCondenser(
        max_chars_per_tool=100,
        enable_llm_summary=True,
        llm_summary_fn=_fn,
    )
    long = "x" * 5000
    e1 = _ev(1, "tool_result", long, idx=1)
    e2 = _ev(2, "tool_result", long, idx=2)  # 同 content
    await c.condense([e1], CondenseContext())
    await c.condense([e2], CondenseContext())
    assert call_count["n"] == 1   # 第二次命中缓存
