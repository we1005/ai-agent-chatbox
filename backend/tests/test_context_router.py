"""P3.3 · context_router 规则层单测。

纯同步、零 I/O——只测规则打分。
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services.context_router import decide_memory_injection  # noqa: E402


# ── 正例：该触发 memory 检索 ─────────────────────────────────


@pytest.mark.parametrize("query,expected_hits", [
    ("记得我之前说过我叫什么吗？", ["reference_word"]),
    ("上次我提到的那本书是？", ["reference_word"]),
    ("我刚才问的是 Python 问题", ["reference_word"]),
    ("我叫什么名字？", ["reference_word"]),
    ("我喜欢什么风格的回答？", ["reference_word"]),
    ("我的宠物叫什么？", ["reference_word"]),
])
def test_positive_triggers(query, expected_hits):
    d = decide_memory_injection(query)
    assert d.should_inject is True
    for h in expected_hits:
        assert h in d.rule_hits
    assert d.search_query == query.strip()
    assert d.rule_score >= 1


# ── 反例：命令式不该触发 ──────────────────────────────────


@pytest.mark.parametrize("query", [
    "翻译以下这段英文：Hello world",
    "解释一下量子纠缠是什么",
    "请帮我写一段 Python 代码排序列表",
    "总结这篇文章的核心观点",
])
def test_command_prefix_not_trigger(query):
    d = decide_memory_injection(query)
    assert d.should_inject is False
    assert d.fallback_reason == "router_skip"


# ── 混合信号：命令式 + 回指词（得分相加）─────────────────


def test_command_plus_reference_still_fires():
    """'请帮我回忆一下我之前说过的偏好' → command(-1) + reference(+2) = 1 → 触发"""
    d = decide_memory_injection("请帮我回忆一下我之前说过的偏好")
    assert d.should_inject is True
    assert d.rule_score == 1
    assert set(d.rule_hits) == {"command_prefix", "reference_word"}


# ── 边界 ─────────────────────────────────────────────────


def test_empty_query():
    assert decide_memory_injection("").should_inject is False
    assert decide_memory_injection("   ").should_inject is False
    assert decide_memory_injection("").fallback_reason == "empty_query"


def test_disabled_flag():
    d = decide_memory_injection("记得我之前说过吗", enabled=False)
    assert d.should_inject is False
    assert d.fallback_reason == "disabled"


def test_neutral_query_no_trigger():
    """普通问题，无记忆线索 → 不触发。"""
    d = decide_memory_injection("2026 年世界杯在哪个国家举办？")
    assert d.should_inject is False
    assert d.rule_score == 0
    assert d.fallback_reason == "router_skip"
