"""TaskContext 的 CRUD helper（P5.1）。

上层使用：
  - Solo 端点进入时 `ensure_task(task_id, conversation_id, goal)` 幂等创建
  - Solo 子图每跑完一个 step 可以 `append_step_event(task_id, event_id)`
  - 任务结束 `finish_task(task_id, delta)` 写 delta + 合流到 durable memory

见 plan-doc-dir/长上下文机制设计v2·集百家之长.md §6.5 / §7 P5.1。
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from app.models.task import TaskContext, TaskStatus

logger = logging.getLogger(__name__)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


async def ensure_task(
    task_id: str,
    conversation_id: str,
    *,
    goal: str = "",
    user_id: str | None = None,
) -> TaskContext:
    """幂等 upsert：存在则不覆盖 goal，只更新 updated_at。"""
    existing = await TaskContext.find_one({"task_id": task_id})
    if existing:
        existing.updated_at = _utcnow()
        await existing.save()
        return existing
    t = TaskContext(
        task_id=task_id,
        conversation_id=conversation_id,
        goal=goal,
        user_id=user_id,
        status="running",
    )
    await t.insert()
    return t


async def append_step_event(task_id: str, event_id: str) -> bool:
    """把一个 event id 加到 step_event_ids 列表。Fail-soft。"""
    t = await TaskContext.find_one({"task_id": task_id})
    if not t:
        return False
    if event_id in t.step_event_ids:
        return True
    t.step_event_ids.append(event_id)
    t.updated_at = _utcnow()
    await t.save()
    return True


async def finish_task(
    task_id: str,
    *,
    status: TaskStatus = "completed",
    task_delta: dict | None = None,
    summary: str | None = None,
) -> TaskContext | None:
    t = await TaskContext.find_one({"task_id": task_id})
    if not t:
        return None
    t.status = status
    if task_delta is not None:
        t.task_delta = task_delta
    if summary is not None:
        t.task_rolling_summary = summary
    t.finished_at = _utcnow()
    t.updated_at = t.finished_at
    await t.save()
    return t


async def get_task(task_id: str) -> TaskContext | None:
    return await TaskContext.find_one({"task_id": task_id})


async def list_tasks(
    *,
    conversation_id: str | None = None,
    status: TaskStatus | None = None,
    limit: int = 50,
) -> list[TaskContext]:
    query: dict = {}
    if conversation_id:
        query["conversation_id"] = conversation_id
    if status:
        query["status"] = status
    return await (
        TaskContext.find(query)
        .sort("-updated_at")
        .limit(limit)
        .to_list()
    )
