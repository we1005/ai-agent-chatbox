"""Context Engine v2 · P4.1 · 上下文装配相关的数据类型。

这些是纯数据结构，没有任何逻辑——把 chat_stream 里散乱的 dict / 布尔参数
收纳进有名字的对象，方便 A/B 调试、trace、单测。

见 plan-doc-dir/长上下文机制设计v2·集百家之长.md §5.5 / §5.6 / §7 P4.1。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

KbStrategy = Literal["classical", "multi_query", "agentic", "graph", "off"]


@dataclass
class InjectionPlan:
    """Router 的决策输出，Assembler 按此装配 View。

    字段按优先级从高到低排（high-priority 先装，低优先级被 budget 先丢）。
    """

    # L1 identity / policy：永远装
    include_system_prompt: bool = True

    # L2 recent buffer：dialog 的最近 N 轮
    include_recent_raw_turns: int = 5

    # L3 rolling summary：由 condenser 生成的历史摘要
    include_rolling_summary: bool = True

    # L4 durable memory：命中规则时注入 top-K memory hits
    include_memory_hits: bool = False
    memory_search_query: str | None = None
    memory_top_k: int = 5

    # L5 retrieval plane：RAG 的 4 路策略（对齐现有 chat_stream 分支）
    include_kb_retrieval: bool = False
    kb_strategy: KbStrategy = "off"   # 由现有 rag.agentic_rag_mode / graph_rag_enabled / multi_query_enabled 决定
    include_web_search: bool = False

    # 任务隔离（P5 预留）
    isolate_to_task: str | None = None

    # 输出协议：保 XML 结构不变即可
    output_contract: str = "xml"      # "xml" | "plain" | "json"


@dataclass
class TokenBudget:
    """装配时的 token 预算。Assembler 按 priority 先满足高优先级 block。

    block_priority 值越小越先保留（system=0 最高，web=10 最低）。
    chat_stream 里 rag_docs/web_results/memory_hits 都走此优先级表。
    """

    total: int = 120_000           # 窗口上限（DeepSeek-chat 128k，留 8k 给输出）
    reserved_for_output: int = 4000

    # priority map（小=优先保留）
    block_priority: dict[str, int] = field(default_factory=lambda: {
        "system_prompt":    0,
        "current_user":     0,
        "recent_raw_tail":  1,     # 最近 2 轮原文
        "rolling_summary":  3,
        "memory_hits":      4,
        "kb_retrieval":     5,
        "recent_raw_middle": 7,    # 超过 tail 的中间轮
        "web_results":     10,     # 最早被丢
    })

    @property
    def input_cap(self) -> int:
        """留给 prompt 输入的上限。"""
        return max(0, self.total - self.reserved_for_output)


@dataclass
class AssembledBlock:
    """一个 context block（装配器的中间态）。"""

    name: str                        # "system_prompt" / "recent_raw_tail" / ...
    role: str                        # "system" / "user" / "assistant"
    content: str
    tokens: int
    priority: int


@dataclass
class AssembledMessages:
    """Assembler 的最终产出——messages 列表 + trace。"""

    messages: list[dict] = field(default_factory=list)   # chat_stream 期望格式 [{role,content}]
    used_tokens: int = 0
    dropped_blocks: list[str] = field(default_factory=list)
    included_blocks: list[str] = field(default_factory=list)
    trace: dict = field(default_factory=dict)


# ── 粗略 token 估算 ─────────────────────────────────────────────


def estimate_tokens(text: str) -> int:
    """中文约 1.8 字符/token，英文约 4 字符/token——取折中 2.5。

    用于 budget 预估；不追求精确（精确值要调 tokenizer，延迟更高）。
    """
    if not text:
        return 0
    return max(1, len(text) // 2 + 1)
