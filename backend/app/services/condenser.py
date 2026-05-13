"""Context Engine v2 · Condenser 框架（P2.1 骨架 + RecentBufferCondenser）

职责：把完整 event 流投影成本轮实际要喂给 LLM 的"View 事件子集"。
不改 event store（只读），不写回——View 是派生物。

设计原则（见 plan-doc-dir/长上下文机制设计v2·集百家之长.md §5.4 / §6.1-6.2）：

1. **Protocol + 组合**：每个 Condenser 只做一件事；PipelineCondenser 把多个
   串起来（先工具输出裁剪，再对话摘要……）。
2. **Recent Buffer 保护**：最近 N 轮原文永远在，不进摘要。保证"刚刚那句话"
   不会被压缩掉。
3. **不碰 event store**：condenser 接收 list[Event]，返回 list[Event]；
   所有写回由调用方（P2.2 的 summary event / P2.3 的 chat_stream）负责。
4. **P2.1 本 commit 只实现 RecentBufferCondenser（纯确定性）**；
   LLMSummarizingCondenser 留 P2.2。

本文件零 LLM 调用、零 Mongo 读写；所有 Condenser 都是 async 但无 I/O（保留
async 签名是为了 P2.2 的 LLM condenser 不改接口）。
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from types import SimpleNamespace


def _naive(dt: datetime | None) -> datetime | None:
    """归一化 datetime 到 tz-naive，避免 Beanie 反序列化的 naive datetime 与
    condenser 新建的 tz-aware datetime 在同一个 sorted() 里比较导致 TypeError。"""
    if dt is None:
        return None
    if dt.tzinfo is not None:
        return dt.replace(tzinfo=None)
    return dt
from typing import Any, Awaitable, Callable, Protocol

from app.models.event import Event

logger = logging.getLogger(__name__)


# Condenser 输出不一定是 Beanie Event Document——LLMSummarizingCondenser 合成的
# summary 在 condenser 阶段只是个 SimpleNamespace 占位对象（duck-typed：kind /
# role / content / turn_id / conversation_id / metadata / tokens / created_at）。
# 真正写回 Mongo 的 Event Document 由调用方（P2.3 chat_stream）在 Beanie 已
# 初始化的上下文里 Event(...) 构造。这样 condenser 纯函数、零 DB 耦合、易测。
EventLike = Event  # 类型别名（运行时等同 Event；静态标注用）


# ── CondenseContext ──────────────────────────────────────────────────


@dataclass
class CondenseContext:
    """Condenser 运行时上下文，由 chat_stream / assembler 填入。

    - `conversation_id`：唯一键，供 LLM condenser 写回 summary event
    - `budget_tokens`：token 预算（P4 Assembler 填入；P2.1 里不强制使用）
    - `now_turn_id`：当前正在处理的 turn_id（recency 判断基准）
    - `trace`：dict 累加每层 condenser 的动作摘要，供 LangSmith metadata
    """
    conversation_id: str | None = None
    budget_tokens: int = 8000
    now_turn_id: int | None = None
    trace: dict = field(default_factory=dict)


# ── Protocol ─────────────────────────────────────────────────────────


class Condenser(Protocol):
    """所有 condenser 实现此接口。

    输入：原始（可能很长的）event 序列 + 运行时 ctx。
    输出：被"投影"过的 event 子集——可能包含新生成的 summary event，
         也可能只是原序列的过滤版。
    """

    async def condense(self, events: list[Event], ctx: CondenseContext) -> list[Event]: ...


# ── PipelineCondenser ────────────────────────────────────────────────


class PipelineCondenser:
    """顺序组合多个 condenser。前一个的输出是后一个的输入。

    典型装配：[ToolOutputCondenser, LLMSummarizingCondenser, RecentBufferCondenser]
    —— 先裁剪长工具输出，再对中段做摘要，最后保护 recency 尾部。
    """

    def __init__(self, steps: list[Condenser]):
        self.steps = steps

    async def condense(self, events: list[Event], ctx: CondenseContext) -> list[Event]:
        for step in self.steps:
            events = await step.condense(events, ctx)
        return events


# ── RecentBufferCondenser ────────────────────────────────────────────


class RecentBufferCondenser:
    """保留最近 N 个 user turn 原文，丢弃更早的 event（non-summary）。

    **核心语义**：
      - turn_id 按 `_next_turn_id` 约定：user_msg 开新轮，共享轮内其它 event
      - 本 condenser 只按 turn_id 切片，不看 kind / content
      - 已存在的 `summary` event（P2.2 产物）**始终保留**——它代表更早历史的压缩
        表达，不能跟着老 user/assistant 一起被丢

    **约定**：
      - `max_recent_turns=5` 意味着保留最近 5 个 user turn 的全部 events
      - 早于 cutoff 的 user_msg/assistant_msg/tool_* 统一丢（由后续 LLM
        summarizer 决定是否摘要保留）
      - summary 事件单独一类，不受 cutoff 影响
    """

    def __init__(self, max_recent_turns: int = 5, max_single_turn_chars: int = 2000):
        if max_recent_turns < 1:
            raise ValueError("max_recent_turns 必须 ≥ 1")
        self.max_recent_turns = max_recent_turns
        self.max_single_turn_chars = max_single_turn_chars

    async def condense(
        self, events: list[Event], ctx: CondenseContext
    ) -> list[Event]:
        if not events:
            return events

        # 按 (turn_id, created_at) 升序规整（调用方通常已排好，但兜底一下）
        events_sorted = sorted(events, key=lambda e: (e.turn_id, _naive(e.created_at)))

        # 不参与裁剪的 kind：summary（P2.2）、memory_flush（P3）、intent_routed（P4）
        protected_kinds = {"summary", "memory_flush", "intent_routed"}

        # 所有非受保护 event 中出现过的 turn_id 集合
        turn_ids = sorted({
            e.turn_id for e in events_sorted if e.kind not in protected_kinds
        })
        if not turn_ids:
            # 全是受保护 event，不裁
            ctx.trace.setdefault("recent_buffer", {})["kept_turns"] = 0
            return events_sorted

        # 保留最近 N 个 turn
        cutoff_turn = turn_ids[-self.max_recent_turns] if len(turn_ids) >= self.max_recent_turns else turn_ids[0]

        kept: list[Event] = []
        dropped_turns: list[int] = []
        for e in events_sorted:
            if e.kind in protected_kinds:
                kept.append(e)
                continue
            if e.turn_id >= cutoff_turn:
                kept.append(e)
            else:
                dropped_turns.append(e.turn_id)

        ctx.trace.setdefault("recent_buffer", {}).update({
            "kept_turns": len(turn_ids[-self.max_recent_turns:]),
            "dropped_event_count": len(dropped_turns),
            "cutoff_turn_id": cutoff_turn,
        })
        return kept


# ── LLMSummarizingCondenser（P2.2，OpenHands 算法移植）────────────────


# 默认 DeepSeek client 工厂；测试里 monkey-patch 这一层即可跳 LLM
_LLMSummaryFn = Callable[[str], Awaitable[str]]


def _default_llm_summary_fn() -> _LLMSummaryFn:
    """返回一个用 DeepSeek-chat 跑 summary 的 async 函数。

    延迟构造（import 时不建 client）。失败由调用方兜底。
    """
    async def _call(prompt: str) -> str:
        from app.core.config import get_settings
        from app.services._langsmith import get_utility_openai
        settings = get_settings()
        client = get_utility_openai()
        resp = await client.chat.completions.create(
            model=settings.UTILITY_LLM_MODEL,
            messages=[
                {"role": "system", "content": (
                    "你是一个对话历史压缩器。把给定的聊天片段压成不超过 400 字的结构化摘要，"
                    "保留：当前任务/目标、关键事实（人名/地名/数字/时间）、已做出的决策/回答、"
                    "未解决的问题或悬挂线索。忽略寒暄、客套。用简体中文输出，不要 markdown 格式。"
                )},
                {"role": "user", "content": prompt},
            ],
            temperature=0.0,
            timeout=45.0,
        )
        return (resp.choices[0].message.content or "").strip()

    return _call


class LLMSummarizingCondenser:
    """递归 rolling global summary（OpenHands `LLMSummarizingCondenser` 移植）。

    核心算法（对齐 OpenHands 源码）：
        view = [head(keep_first)] + [prev_summary?] + [tail(max_size//2)]
    当 event 数量超过 `max_size` 时：
        1. 拎出 head (keep_first 条) 和 tail (max_size // 2 条)
        2. 把中间段（forgotten）+ 上一次的 summary 一起喂 LLM，生成新 summary
        3. 新 summary 作为 kind="summary" event 写回（metadata 含前摘要溯源）
        4. 输出 head + [new_summary_event] + tail

    与 OpenHands 差异：
      - 这里 **不持久化 summary event 到 Mongo**；由调用方（P2.3 的 chat_stream
        / P4 的 assembler）决定是否写回 event store。原因：condenser 应是纯函数，
        便于 mock 和 benchmark。
      - `keep_first` 默认 1（保第一条 user_msg 锚定任务意图）
      - 我们对"event 数"的定义：排除受保护 kind（summary/memory_flush/intent_routed），
        那些不参与摘要循环

    与 RecentBufferCondenser 的配合：
        PipelineCondenser([
            LLMSummarizingCondenser(max_size=20, keep_first=1),   # 先摘要压缩中段
            RecentBufferCondenser(max_recent_turns=5),            # 再保护 recency
        ])
    """

    def __init__(
        self,
        max_size: int = 20,
        keep_first: int = 1,
        *,
        llm_summary_fn: _LLMSummaryFn | None = None,
        max_forgotten_chars: int = 12000,
    ):
        if max_size < 4:
            raise ValueError("max_size 必须 ≥ 4")
        if keep_first < 0 or keep_first >= max_size // 2:
            raise ValueError("keep_first 必须在 [0, max_size/2) 范围内")
        self.max_size = max_size
        self.keep_first = keep_first
        self.max_forgotten_chars = max_forgotten_chars
        self._llm_summary_fn = llm_summary_fn  # 允许测试注入；None 时延迟构造

    async def condense(
        self, events: list[Event], ctx: CondenseContext
    ) -> list[Event]:
        # 受保护 event（上一次 summary / memory_flush / intent_routed）不参与摘要循环
        protected_kinds = {"memory_flush", "intent_routed"}
        # summary 特殊：只保留最后一条作为 prev_summary 输入
        summaries = [e for e in events if e.kind == "summary"]
        prev_summary = summaries[-1] if summaries else None
        body = [
            e for e in events
            if e.kind not in protected_kinds and e.kind != "summary"
        ]
        others = [e for e in events if e.kind in protected_kinds]

        body_sorted = sorted(body, key=lambda e: (e.turn_id, _naive(e.created_at)))

        if len(body_sorted) <= self.max_size:
            # 未到阈值：原样透传（加上 prev_summary 和 others）
            ctx.trace.setdefault("llm_summary", {}).update({
                "fired": False,
                "body_size": len(body_sorted),
                "threshold": self.max_size,
            })
            out: list[Event] = []
            if prev_summary is not None:
                out.append(prev_summary)
            out.extend(others)
            out.extend(body_sorted)
            return out

        head = body_sorted[: self.keep_first]
        tail_size = max(1, self.max_size // 2)
        tail = body_sorted[-tail_size:]
        forgotten = body_sorted[self.keep_first : -tail_size]

        new_summary_event = await self._build_summary_event(
            forgotten=forgotten,
            prev_summary=prev_summary,
            ctx=ctx,
        )

        ctx.trace.setdefault("llm_summary", {}).update({
            "fired": True,
            "body_size": len(body_sorted),
            "threshold": self.max_size,
            "kept_head": len(head),
            "kept_tail": len(tail),
            "forgotten": len(forgotten),
            "degraded": new_summary_event is None,
        })

        out: list[Event] = []
        out.extend(others)           # memory_flush / intent_routed 原位
        out.extend(head)
        if new_summary_event is not None:
            out.append(new_summary_event)
        elif prev_summary is not None:
            # 新 summary 生成失败 → 沿用旧 summary（fail-soft）
            out.append(prev_summary)
        out.extend(tail)
        return out

    # ── 内部辅助 ──────────────────────────────────────────────

    async def _build_summary_event(
        self,
        *,
        forgotten: list[Event],
        prev_summary: Event | None,
        ctx: CondenseContext,
    ) -> Event | None:
        """调 LLM 生成新 summary；失败返回 None。"""
        prompt = self._render_prompt(forgotten, prev_summary)

        fn = self._llm_summary_fn or _default_llm_summary_fn()
        try:
            summary_text = await fn(prompt)
        except Exception as e:
            logger.warning(
                f"[LLMSummaryCondenser] LLM call failed (fail-soft): "
                f"{type(e).__name__}: {e}"
            )
            return None

        if not summary_text:
            logger.warning("[LLMSummaryCondenser] empty summary text returned")
            return None

        # 新 summary 的 turn_id 取被摘要段的最大 turn_id（覆盖到这里）
        covered_max_turn = max((e.turn_id for e in forgotten), default=0)
        prev_id = None
        if prev_summary is not None:
            # 支持真 Event（Beanie）或 SimpleNamespace 替身
            prev_id = str(getattr(prev_summary, "id", None) or prev_summary.metadata.get("_prev_summary_id") or "")

        # 用 SimpleNamespace 合成 duck-typed event；真正持久化到 Mongo 的 Event
        # Document 由 P2.3 的 chat_stream 在 Beanie 已初始化上下文里构造
        evt = SimpleNamespace(
            conversation_id=ctx.conversation_id or (
                forgotten[0].conversation_id if forgotten else "unknown"
            ),
            turn_id=covered_max_turn,
            kind="summary",
            role=None,
            content=summary_text,
            tokens=len(summary_text) // 2,   # 粗估：中文约 2 字符/token
            metadata={
                "covered_turn_min": min((e.turn_id for e in forgotten), default=0),
                "covered_turn_max": covered_max_turn,
                "covered_event_count": len(forgotten),
                "superseded_by": None,
                "prev_summary_id": prev_id,
            },
            created_at=datetime.now(timezone.utc),
            id=None,
        )
        return evt

    def _render_prompt(
        self, forgotten: list[Event], prev_summary: Event | None
    ) -> str:
        """构造 LLM 输入：prev_summary（若有）+ 被遗忘段的 role+content 串联。

        对 forgotten 做 `max_forgotten_chars` 截断保护，避免单次 prompt 过长。
        """
        parts: list[str] = []
        if prev_summary is not None:
            parts.append(f"[前一次摘要]\n{prev_summary.content}\n")

        parts.append("[待摘要的对话片段]")
        running = 0
        for e in forgotten:
            role = e.role or e.kind
            line = f"{role}: {e.content}"
            if running + len(line) > self.max_forgotten_chars:
                parts.append(f"…（省略 {len(forgotten) - forgotten.index(e)} 条过长片段）")
                break
            parts.append(line)
            running += len(line)

        parts.append("\n请输出新的结构化摘要：")
        return "\n".join(parts)


# ── ToolOutputCondenser（P4.4）────────────────────────────────────


_TOOL_ERROR_RE = __import__("re").compile(
    r"(?im)(error|exception|traceback|failed|timeout|denied|unauthorized|invalid|✗|❌)"
)


class ToolOutputCondenser:
    """裁剪长工具输出（> max_chars_per_tool）。

    策略（见 v2 §6.4）：
      - head (head_chars) + tail (tail_chars)
      - 额外抽取含错误关键词的行（regex 匹配）
      - 可选 LLM 生成 200 字结构化摘要（summary_hash 缓存同输入不重算）
      - 原文**保留在 event.metadata.raw_content**——condenser 只改 content 字段

    作用域：只处理 kind in {"tool_result", "web_search"} 的 event，其它不动。
    """

    def __init__(
        self,
        max_chars_per_tool: int = 2000,
        head_chars: int = 500,
        tail_chars: int = 500,
        enable_llm_summary: bool = False,     # 默认 off（省成本）；开启后 LLM 200 字摘要
        llm_summary_fn: _LLMSummaryFn | None = None,
    ):
        if max_chars_per_tool < 100:
            raise ValueError("max_chars_per_tool 必须 ≥ 100")
        self.max_chars_per_tool = max_chars_per_tool
        self.head_chars = head_chars
        self.tail_chars = tail_chars
        self.enable_llm_summary = enable_llm_summary
        self._llm_summary_fn = llm_summary_fn
        self._summary_cache: dict[str, str] = {}   # summary_hash -> cached summary

    async def condense(self, events: list[Event], ctx: CondenseContext) -> list[Event]:
        target_kinds = {"tool_result", "web_search"}
        out: list[Event] = []
        pruned = 0
        total_chars_saved = 0

        for e in events:
            if e.kind not in target_kinds:
                out.append(e)
                continue

            content = e.content or ""
            if len(content) <= self.max_chars_per_tool:
                out.append(e)
                continue

            # 超长：裁剪
            head = content[: self.head_chars]
            tail = content[-self.tail_chars:] if self.tail_chars > 0 else ""
            error_lines = self._extract_error_lines(content)

            summary_text = ""
            if self.enable_llm_summary:
                summary_text = await self._maybe_summarize(content)

            # 拼装新 content
            parts = [head]
            if error_lines:
                parts.append("\n…（错误相关片段）\n" + "\n".join(error_lines[:5]))
            if tail:
                parts.append(f"\n…（尾部 {len(tail)} 字符）\n{tail}")
            if summary_text:
                parts.append(f"\n…（LLM 结构化摘要）\n{summary_text}")
            new_content = "\n".join(parts)

            # 原文存进 metadata.raw_content（debug / 审计）
            new_meta = dict(e.metadata)
            new_meta.setdefault("raw_content", content)
            new_meta["pruned_by"] = "tool_output_condenser"
            new_meta["pruned_from_chars"] = len(content)
            new_meta["pruned_to_chars"] = len(new_content)

            pruned_event = SimpleNamespace(
                conversation_id=e.conversation_id,
                turn_id=e.turn_id,
                kind=e.kind,
                role=e.role,
                content=new_content,
                tokens=len(new_content) // 2,
                metadata=new_meta,
                created_at=e.created_at,
                id=getattr(e, "id", None),
            )
            out.append(pruned_event)
            pruned += 1
            total_chars_saved += len(content) - len(new_content)

        ctx.trace.setdefault("tool_output", {}).update({
            "pruned_events": pruned,
            "chars_saved": total_chars_saved,
            "llm_summary_enabled": self.enable_llm_summary,
        })
        return out

    def _extract_error_lines(self, text: str) -> list[str]:
        """按行找含错误关键词的，返回命中行（去重，保序）。"""
        seen: set[str] = set()
        lines: list[str] = []
        for ln in text.splitlines():
            ln_s = ln.strip()
            if not ln_s or ln_s in seen:
                continue
            if _TOOL_ERROR_RE.search(ln_s):
                seen.add(ln_s)
                lines.append(ln_s)
        return lines

    async def _maybe_summarize(self, content: str) -> str:
        """可选 LLM 摘要 + 同输入缓存。"""
        import hashlib
        h = hashlib.sha1(content.encode("utf-8")).hexdigest()[:16]
        if h in self._summary_cache:
            return self._summary_cache[h]

        fn = self._llm_summary_fn or _default_llm_summary_fn()
        try:
            prompt = (
                "请把下面这段工具输出压缩成不超过 200 字的结构化摘要，"
                "保留数据中的关键数字 / 错误 / 决策线索。\n\n"
                f"{content[:8000]}"
            )
            summary = await fn(prompt)
            summary = (summary or "").strip()
            self._summary_cache[h] = summary
            return summary
        except Exception as e:
            logger.warning(f"[ToolOutputCondenser] summary failed (non-fatal): {type(e).__name__}: {e}")
            return ""


# ── Event → dict messages 适配器 ─────────────────────────────────────


def events_to_messages(events: list[Event]) -> list[dict]:
    """把 condenser 产出的 View events 转换成 chat_stream 期望的
    `list[{"role": ..., "content": ...}]` 格式。

    策略：
      - user_msg / assistant_msg → 原样 {role, content}
      - summary                  → {role: "system", content: "[历史摘要] ..."}（P2.2 产物）
      - tool_call / tool_result  → P4 才决定是否暴露给 LLM；P2 阶段跳过
      - memory_flush / intent_routed → 永远不给 LLM 看
      - metadata.removed=True    → 过滤掉（regenerate 留痕）
    """
    out: list[dict] = []
    for e in events:
        if e.metadata.get("removed"):
            continue
        if e.kind == "user_msg":
            out.append({"role": "user", "content": e.content})
        elif e.kind == "assistant_msg":
            out.append({"role": "assistant", "content": e.content})
        elif e.kind == "summary":
            out.append({"role": "system", "content": f"[历史摘要] {e.content}"})
        # tool_* / memory_flush / intent_routed → skip（P2 不暴露）
    return out
