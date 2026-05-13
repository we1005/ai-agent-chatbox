"""TaskContext · Context Engine v2 P5 · 复杂任务的独立上下文 envelope

为了避免"一次复杂 Solo 任务的链式思考污染普通对话记忆"，引入 TaskContext：
  - 一个 task 绑定一个 conversation，但有自己的 goal / step_log / task_summary
  - Solo 子图（LangGraph）未来从 TaskContext 读状态，而不是对话全历史
  - 任务结束后 task_delta 会合流到 durable memory（P3 memory_service）

首版定位：**scaffolding**——model 落库、基本 CRUD helper。
完整把 Solo 子图切到 TaskContext 读路径留给后续 refactor（Solo 现在还能用
原 thread_id，不破坏现有 /api/chat/solo）。

见 plan-doc-dir/长上下文机制设计v2·集百家之长.md §6.5 / §7 P5.1。
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal

from beanie import Document
from pydantic import Field
from pymongo import ASCENDING


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


TaskStatus = Literal["pending", "running", "completed", "failed", "cancelled"]


class TaskContext(Document):
    """一次复杂任务的上下文 envelope。

    `task_id` 也是 LangGraph Solo 子图的 thread_id（保持一一对应，两套 ID 不分裂）。
    """

    task_id: str                     # 唯一键；等同 Solo LangGraph thread_id
    conversation_id: str             # 归属会话
    user_id: str | None = None

    goal: str = ""                   # 用户给的任务目标（通常首条 user 消息）
    status: TaskStatus = "pending"

    # Solo 子图执行轨迹：每条 step 对应一个 event 的 _id（P1 event stream）
    step_event_ids: list[str] = Field(default_factory=list)

    # 任务级 rolling summary（跨很多步骤后压缩）
    task_rolling_summary: str | None = None

    # 是否需要对话上下文作为锚点（默认 True——少量锚点消息；False = 完全隔离）
    depends_on_conversation: bool = True

    # 任务结束时产出的增量更新（合流到 durable memory）
    task_delta: dict = Field(default_factory=dict)

    created_at: datetime = Field(default_factory=_utcnow)
    updated_at: datetime = Field(default_factory=_utcnow)
    finished_at: datetime | None = None

    class Settings:
        name = "tasks"
        indexes = [
            [("task_id", ASCENDING)],
            [("conversation_id", ASCENDING), ("status", ASCENDING)],
            [("status", ASCENDING), ("updated_at", ASCENDING)],
        ]
