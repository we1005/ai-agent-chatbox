"""P4 · Context Types + Router InjectionPlan + Assembler 预算裁剪单测。"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services.context_types import (  # noqa: E402
    AssembledBlock, AssembledMessages, InjectionPlan, TokenBudget, estimate_tokens,
)
from app.services.context_router import route_context  # noqa: E402
from app.services.context_assembler import AssemblyInputs, assemble_messages  # noqa: E402


# ── estimate_tokens ────────────────────────────────────────────


def test_estimate_tokens_empty():
    assert estimate_tokens("") == 0


def test_estimate_tokens_nonzero():
    assert estimate_tokens("你好世界") > 0
    # 大致：len//2 + 1
    assert estimate_tokens("abcdef") == 3 + 1


# ── route_context ─────────────────────────────────────────────


def test_route_context_kb_strategy_priority_graph():
    p = route_context("hi",
                      use_knowledge_base=True,
                      graph_rag_enabled=True,
                      agentic_rag_mode="full",
                      multi_query_enabled=True)
    assert p.kb_strategy == "graph"   # graph 最高


def test_route_context_kb_strategy_agentic_wins_over_multi_query():
    p = route_context("hi",
                      use_knowledge_base=True,
                      graph_rag_enabled=False,
                      agentic_rag_mode="grading_only",
                      multi_query_enabled=True)
    assert p.kb_strategy == "agentic"


def test_route_context_kb_off_when_not_using_kb():
    p = route_context("hi",
                      use_knowledge_base=False,
                      graph_rag_enabled=True)
    assert p.kb_strategy == "off"
    assert p.include_kb_retrieval is False


def test_route_context_memory_triggered_by_reference_word():
    p = route_context("记得我之前说过吗", memory_retrieval_enabled=True)
    assert p.include_memory_hits is True
    assert p.memory_search_query is not None


def test_route_context_memory_disabled_flag():
    p = route_context("记得我之前说过吗", memory_retrieval_enabled=False)
    assert p.include_memory_hits is False


# ── assemble_messages · 预算裁剪 ─────────────────────────────


def test_assemble_basic_under_budget():
    inputs = AssemblyInputs(
        system_prompt="你是一个助手",
        history_messages=[
            {"role": "user", "content": "Q1"},
            {"role": "assistant", "content": "A1"},
            {"role": "user", "content": "Q2"},
            {"role": "assistant", "content": "A2"},
        ],
        current_user_content="当前问题",
        recent_raw_tail_turns=2,
    )
    result = assemble_messages(inputs)
    # system + 4 history + user
    assert len(result.messages) == 6
    assert result.messages[0]["role"] == "system"
    assert result.messages[-1]["content"] == "当前问题"
    assert result.dropped_blocks == []


def test_assemble_memory_hits_prepended_to_system():
    inputs = AssemblyInputs(
        system_prompt="你是助手",
        memory_hits_text="[用户相关的长期记忆]\n- 偏好简体中文",
        current_user_content="Q",
    )
    result = assemble_messages(inputs)
    sys_msg = next(m for m in result.messages if m["role"] == "system")
    assert "你是助手" in sys_msg["content"]
    assert "用户相关的长期记忆" in sys_msg["content"]


def test_assemble_tiny_budget_drops_middle_history():
    """预算只够 system + user + tail 时，middle 被丢。"""
    # 造 10 轮对话，每轮内容约 2000 字，中间轮总 token 会很大
    long_text = "x" * 2000
    history = []
    for i in range(10):
        history.append({"role": "user", "content": f"Q{i} {long_text}"})
        history.append({"role": "assistant", "content": f"A{i} {long_text}"})

    inputs = AssemblyInputs(
        system_prompt="sys",
        history_messages=history,
        current_user_content="current",
        recent_raw_tail_turns=2,
    )
    # 预算：system(2) + tail(4*1000≈4000 tokens) + user(1) 约 4k，middle ~16 轮 × 1000 = 16k
    # 把 cap 设到只容 tail
    b = TokenBudget(total=6000, reserved_for_output=500)
    result = assemble_messages(inputs, b)

    assert "recent_raw_middle" in result.dropped_blocks
    # tail 要保留
    assert "recent_raw_tail" in result.included_blocks
    # tail 轮内容仍在 messages 里
    assert any(m["content"].startswith("A9") for m in result.messages)


def test_assemble_trace_fields():
    inputs = AssemblyInputs(
        system_prompt="sys",
        history_messages=[{"role": "user", "content": "x"}, {"role": "assistant", "content": "y"}],
        current_user_content="q",
        recent_raw_tail_turns=1,
    )
    result = assemble_messages(inputs)
    assert "cap_tokens" in result.trace
    assert "used_tokens" in result.trace
    assert result.trace["history_turns_total"] == 2
    assert result.trace["recent_tail_turns"] == 1


def test_assemble_empty_history():
    inputs = AssemblyInputs(
        system_prompt="sys",
        history_messages=[],
        current_user_content="q",
    )
    result = assemble_messages(inputs)
    assert [m["role"] for m in result.messages] == ["system", "user"]
    assert result.trace["history_turns_total"] == 0


# ── InjectionPlan dataclass ────────────────────────────────


def test_injection_plan_defaults():
    p = InjectionPlan()
    assert p.include_system_prompt is True
    assert p.include_recent_raw_turns == 5
    assert p.kb_strategy == "off"
    assert p.output_contract == "xml"


def test_token_budget_input_cap():
    b = TokenBudget(total=100, reserved_for_output=30)
    assert b.input_cap == 70
