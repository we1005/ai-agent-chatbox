"""Event stream 模型（Context Engine v2 的真相源）。

OpenHands 风格：所有对话发生的事（user msg / assistant msg / tool call /
tool result / summary / memory flush / intent routing 决策 ...）都是 typed
Event，统一进 Mongo `events` collection。

上下文 View（传给 LLM 的 langchain messages）、rolling summary、durable memory
都是这张表的派生物——原始 event 永不改写，永不物理删。

见 plan-doc-dir/长上下文机制设计v2·集百家之长.md §5.2。
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal

from beanie import Document
from pydantic import Field
from pymongo import ASCENDING


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


# 允许的 event kind（v2 §5.2 定义）。后续新增类型只在这里登记即可。
EventKind = Literal[
    "user_msg",        # 用户消息
    "assistant_msg",   # 助手消息
    "tool_call",       # 工具调用（planner → tool）
    "tool_result",     # 工具返回（tool → planner）
    "rag_retrieval",   # RAG 检索发生（记录策略 / docs 数 / degraded 等）
    "web_search",      # 联网检索发生
    "summary",         # 由 Condenser 生成的 rolling summary
    "memory_flush",    # 后台反思产出的 memory write 事件
    "intent_routed",   # Context Router 的决策（kb_strategy / memory / pin 等）
]


class Event(Document):
    """单条 event。

    - `conversation_id`：string，不用 ObjectId 反序列化，配 Conversation 主键
    - `turn_id`：同一轮（user + assistant + tool_*）共享整数编号，从 0 起
    - `kind`：见 EventKind
    - `role`：user / assistant / tool / None（summary/memory_flush 等无 role）
    - `content`：text 或 json 字符串（tool_call/tool_result 建议 json dumps）
    - `tokens`：估算 token 数（用于 budget 裁剪；未知时填 0）
    - `metadata`：自由 dict——refs / intent / tool_name / rag_strategy / ...

    collection 名 `events`，以 `(conversation_id, turn_id)` 复合索引提速 view 重建。
    """

    conversation_id: str
    turn_id: int = 0
    kind: EventKind
    role: str | None = None
    content: str = ""
    tokens: int = 0
    metadata: dict = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=_utcnow)

    class Settings:
        name = "events"
        indexes = [
            # 按 conv_id + turn_id 查（重建 view 时的主访问路径）
            [("conversation_id", ASCENDING), ("turn_id", ASCENDING), ("created_at", ASCENDING)],
            # 按 kind 过滤（例如只拉 summary）
            [("conversation_id", ASCENDING), ("kind", ASCENDING), ("created_at", ASCENDING)],
        ]
