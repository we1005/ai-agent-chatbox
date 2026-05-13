"""Context Engine v2 · P4.3 · Assembler（按 TokenBudget 的优先级裁剪）

当前 chat_stream 里上下文装配已经分散在多处：
  - condenser.events_to_messages → history
  - P3.3 memory hits 注入为 system message
  - Jinja render 拼 system + user + RAG refs
  - rag_docs 通过 Jinja `<document>` 块拼进 user message

完全统一到 Assembler 是 big-bang 重构，P4.3 采取**中间路线**：
  - 保留 chat_stream 现有的"按 kb_strategy 分 4 路召回"的流水线
  - 在最后喂 LLM 前，Assembler 作为一个后置函数拿到所有已准备好的 block
    （system_prompt / history / user / memory_hits / kb_retrieval / web_results）
    → 按 TokenBudget 的 block_priority 从高到低累加，超预算先丢低优先级
  - 产出 AssembledMessages 带 dropped/included trace，便于 LangSmith debug

这样的好处：
  1. 不破坏现有的 4 路分支 + XML 合同
  2. 立即拿到 token 预算保护（长对话不会再因为 recent 保护 + 大 KB 而爆）
  3. 可观测 dropped 列表 → 后续调 priority 更稳

见 plan-doc-dir/长上下文机制设计v2·集百家之长.md §5.6 / §7 P4.3。
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

from app.services.context_types import (
    AssembledBlock, AssembledMessages, TokenBudget, estimate_tokens,
)

logger = logging.getLogger(__name__)


# ── 装配输入 ─────────────────────────────────────────────────────


@dataclass
class AssemblyInputs:
    """Assembler 的输入。chat_stream 把分散来源填进来。"""

    system_prompt: str = ""
    history_messages: list[dict] = field(default_factory=list)   # [{role, content}]
    current_user_content: str = ""

    memory_hits_text: str = ""          # 已拼好的"[用户相关的长期记忆] ..." 文本
    kb_retrieval_text: str = ""         # 已拼好的 <document>...</document> Jinja 块
    web_results_text: str = ""          # 已拼好的 <web_search_results>... 块

    recent_raw_tail_turns: int = 2      # tail 保护：永远装入的最近 N 轮


def assemble_messages(
    inputs: AssemblyInputs,
    budget: TokenBudget | None = None,
) -> AssembledMessages:
    """把所有 block 按 priority 装成最终 messages 列表，超预算裁掉低优先级。

    装配顺序（最终 messages 数组的位置）：
        [system_prompt(+memory_hits)]
        [history[0:-tail]]  ← middle 可丢
        [history[-tail:]]
        [current_user(+kb_retrieval+web_results)]

    裁剪时从 `recent_raw_middle` / `web_results` 开始丢，保底不动
    `system_prompt` / `current_user` / `recent_raw_tail`。
    """
    budget = budget or TokenBudget()
    cap = budget.input_cap

    # 1. 把各 block 算出来并预估 token
    tail_n = inputs.recent_raw_tail_turns * 2  # user + assistant pair
    history = inputs.history_messages
    recent_tail = history[-tail_n:] if tail_n else []
    recent_middle = history[: len(history) - len(recent_tail)]

    # system_prompt 合并 memory_hits（保顺序：memory 在 system 下方）
    system_content = inputs.system_prompt
    if inputs.memory_hits_text:
        # 在 system prompt 后追加 memory 段，保持 LLM 一眼能看到"我们知道的事"
        system_content = (
            f"{inputs.system_prompt}\n\n{inputs.memory_hits_text}"
            if inputs.system_prompt else inputs.memory_hits_text
        )

    # 最终 user message 合并 kb_retrieval + web_results（这两块通过 Jinja 已经
    # 拼进了 current_user_content；Assembler 这里把它们视作 current_user 的
    # 一部分来计量 token）
    user_content = inputs.current_user_content

    blocks: list[AssembledBlock] = []
    blocks.append(AssembledBlock(
        name="system_prompt", role="system",
        content=system_content,
        tokens=estimate_tokens(system_content),
        priority=budget.block_priority.get("system_prompt", 0),
    ))
    # Recent tail 作为一个 block（多轮消息，tokens 累加）
    tail_tokens = sum(estimate_tokens(m.get("content", "")) for m in recent_tail)
    if recent_tail:
        blocks.append(AssembledBlock(
            name="recent_raw_tail", role="_multi",
            content="",  # 占位，实际 messages 从 inputs.history_messages 还原
            tokens=tail_tokens,
            priority=budget.block_priority.get("recent_raw_tail", 1),
        ))
    middle_tokens = sum(estimate_tokens(m.get("content", "")) for m in recent_middle)
    if recent_middle:
        blocks.append(AssembledBlock(
            name="recent_raw_middle", role="_multi",
            content="",
            tokens=middle_tokens,
            priority=budget.block_priority.get("recent_raw_middle", 7),
        ))
    blocks.append(AssembledBlock(
        name="current_user", role="user",
        content=user_content,
        tokens=estimate_tokens(user_content),
        priority=budget.block_priority.get("current_user", 0),
    ))

    # 2. 按 priority 升序累加 token；超 cap 的 block 从结果里丢
    blocks_sorted = sorted(blocks, key=lambda b: b.priority)
    running = 0
    kept_names: set[str] = set()
    dropped_names: list[str] = []
    for b in blocks_sorted:
        if running + b.tokens <= cap:
            running += b.tokens
            kept_names.add(b.name)
        else:
            dropped_names.append(b.name)

    # 3. 按最终 messages 数组位置重组
    messages: list[dict] = []
    if "system_prompt" in kept_names:
        messages.append({"role": "system", "content": system_content})

    if "recent_raw_middle" in kept_names:
        messages.extend(recent_middle)

    if "recent_raw_tail" in kept_names:
        messages.extend(recent_tail)
    elif recent_middle and "recent_raw_middle" in kept_names and recent_tail:
        # tail 被丢（极端情况，理应不应该——tail 优先级 1 比 middle 7 高）
        # 防御性：仍加 tail，保证语义连贯
        messages.extend(recent_tail)
        kept_names.add("recent_raw_tail")
        dropped_names = [n for n in dropped_names if n != "recent_raw_tail"]

    messages.append({"role": "user", "content": user_content})

    trace = {
        "cap_tokens": cap,
        "used_tokens": running,
        "cap_utilization": round(running / cap, 3) if cap else 0,
        "history_turns_total": len(history),
        "recent_tail_turns": len(recent_tail) // 2,
    }

    return AssembledMessages(
        messages=messages,
        used_tokens=running,
        dropped_blocks=dropped_names,
        included_blocks=sorted(kept_names),
        trace=trace,
    )
