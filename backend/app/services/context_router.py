"""Context Engine v2 · P3.3 · 最小规则版 Context Router（memory 检索开关）

职责：在 chat_stream 真正装配 prompt 之前，做一个轻量决策——**这轮 query
是否需要注入 durable memory？**

完整 Router（§5.5）会决定 kb_strategy / memory / pin / task isolation 等多个
维度；P3.3 只做 memory 一个维度，先跑通数据流。P4 会扩成完整版。

策略（规则优先，无 LLM）：
  1. 代词/回指信号：命中"记得/之前/上次/你刚才/我说过..."等词 → 打分 +2
  2. 第二人称询问用户自身信息："我是谁/我叫什么/我偏好..." → +2
  3. 命令式操作不依赖记忆（"翻译这段/解释一下..."）→ 跳过
  4. 得分 ≥ 1 → 触发 memory 检索；把 top-K 结果作为 system message 插入 View
  5. fail-soft：mem0 / Qdrant 出错只 warn，不影响主流程

见 plan-doc-dir/长上下文机制设计v2·集百家之长.md §5.5 / §7 P3.3 / §9 observability。
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field

from app.services.context_types import InjectionPlan, KbStrategy

logger = logging.getLogger(__name__)


# ── 规则关键词（中文为主） ─────────────────────────────────────────


# 回指 / 时间引用：强信号
_REFERENCE_PATTERNS = [
    r"(记得|之前|上次|上回|上一次|刚才|刚刚)",
    r"(我.{0,3}说过|我.{0,3}告诉过|我.{0,3}提到)",
    r"(你.{0,3}说过|你.{0,3}告诉|你.{0,3}提到)",
    r"我.{0,5}(名字|姓名|叫什么|是谁)",
    r"我.{0,5}(喜欢|偏好|习惯|常用)",
    r"(我家|我的宠物|我的朋友|我的孩子|我的公司|我的职业)",
]
_REFERENCE_RE = re.compile("|".join(_REFERENCE_PATTERNS))

# 明显无需记忆的命令式（命中则 -1 抵消弱命中）
_COMMAND_PATTERNS = [
    r"^(翻译|解释|分析|总结|改写|写一段|生成|画一张)",
    r"^(帮我|请帮|麻烦)",   # 兜底：命令式开头
]
_COMMAND_RE = re.compile("|".join(_COMMAND_PATTERNS))


# ── 决策输出 ─────────────────────────────────────────────────────


@dataclass
class MemoryRouteDecision:
    """P3.3 最小输出：是否查 memory，查什么。"""
    should_inject: bool = False
    search_query: str = ""
    rule_score: int = 0
    rule_hits: list[str] = field(default_factory=list)
    fallback_reason: str | None = None   # "disabled" / "router_skip" / None


def decide_memory_injection(
    user_query: str,
    *,
    enabled: bool = True,
) -> MemoryRouteDecision:
    """对一条 user query 打分，决定是否触发 memory 检索。

    纯规则、同步、零 I/O、零 LLM。`enabled=False` 直接返回 disabled。
    """
    if not enabled:
        return MemoryRouteDecision(should_inject=False, fallback_reason="disabled")
    if not user_query or not user_query.strip():
        return MemoryRouteDecision(should_inject=False, fallback_reason="empty_query")

    text = user_query.strip()
    score = 0
    hits: list[str] = []

    # 回指 / 用户自指 / 所有物代词 → +2（每命中一类 +2，最多一次）
    if _REFERENCE_RE.search(text):
        score += 2
        hits.append("reference_word")

    # 命令式开头 → -1（弱抵消；命令式通常不需要记忆）
    if _COMMAND_RE.search(text):
        score -= 1
        hits.append("command_prefix")

    should = score >= 1

    return MemoryRouteDecision(
        should_inject=should,
        search_query=text if should else "",
        rule_score=score,
        rule_hits=hits,
        fallback_reason=None if should else "router_skip",
    )


# ── P4.2 · 完整 InjectionPlan Router（规则快路径）─────────────────


def route_context(
    user_query: str,
    *,
    use_knowledge_base: bool = False,
    use_web_search: bool = False,
    use_reranker: bool = False,
    agentic_rag_mode: str = "off",
    graph_rag_enabled: bool = False,
    multi_query_enabled: bool = False,
    memory_retrieval_enabled: bool = False,
    recent_turns: int = 5,
) -> InjectionPlan:
    """把散在各处的策略开关汇总成一个 InjectionPlan。

    P4.2 阶段是**纯规则**版本：直接映射现有 chat_stream 行为，不引入新的
    决策逻辑——未来 P5 / Deep Research 再加 LLM 慢路径 + task 隔离。
    """
    # kb_strategy：graph > agentic > multi_query > classical > off
    kb_strategy: KbStrategy = "off"
    if use_knowledge_base:
        if graph_rag_enabled:
            kb_strategy = "graph"
        elif agentic_rag_mode != "off":
            kb_strategy = "agentic"
        elif multi_query_enabled:
            kb_strategy = "multi_query"
        else:
            kb_strategy = "classical"

    # memory：直接复用 decide_memory_injection 的规则
    mem_decision = decide_memory_injection(user_query, enabled=memory_retrieval_enabled)

    return InjectionPlan(
        include_system_prompt=True,
        include_recent_raw_turns=recent_turns,
        include_rolling_summary=True,
        include_memory_hits=mem_decision.should_inject,
        memory_search_query=mem_decision.search_query or None,
        include_kb_retrieval=use_knowledge_base,
        kb_strategy=kb_strategy,
        include_web_search=use_web_search,
        isolate_to_task=None,
        output_contract="xml",
    )
