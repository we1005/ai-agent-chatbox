"""P5.1 · task_service 最小单测。

用替身 TaskContext 类测 CRUD 契约，不需要真 Beanie。
"""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services import task_service as ts  # noqa: E402


def _fake_task_cls(find_one_map: dict, created: list):
    """替身 TaskContext：find_one(map) + insert + save。"""
    class _FT:
        _map = find_one_map

        def __init__(self, **kw):
            self.__dict__.update(kw)
            self.id = f"task-{len(created)+1}"
            self.status = kw.get("status", "pending")
            self.step_event_ids = kw.get("step_event_ids", [])
            self.task_delta = kw.get("task_delta", {})
            self.task_rolling_summary = kw.get("task_rolling_summary", None)
            self.updated_at = None
            self.finished_at = None

        async def insert(self):
            created.append(self)
            return self

        async def save(self):
            return self

        @classmethod
        def find_one(cls, query):
            key = query.get("task_id")
            f = AsyncMock(return_value=cls._map.get(key))
            return f()

        @classmethod
        def find(cls, query):
            # 简单起见，返回空链
            limit = MagicMock()
            limit.to_list = AsyncMock(return_value=[])
            sort = MagicMock()
            sort.limit = MagicMock(return_value=limit)
            find = MagicMock()
            find.sort = MagicMock(return_value=sort)
            return find

    return _FT


@pytest.mark.asyncio
async def test_ensure_task_creates_new(monkeypatch):
    created = []
    monkeypatch.setattr(ts, "TaskContext", _fake_task_cls({}, created))
    t = await ts.ensure_task("task-1", "conv-1", goal="完成一个复杂任务")
    assert t.task_id == "task-1"
    assert t.conversation_id == "conv-1"
    assert t.goal == "完成一个复杂任务"
    assert t.status == "running"
    assert len(created) == 1


@pytest.mark.asyncio
async def test_ensure_task_idempotent(monkeypatch):
    """已存在的 task 不会被覆盖 goal。"""
    existing = MagicMock()
    existing.goal = "old goal"
    existing.status = "running"
    existing.updated_at = None
    existing.save = AsyncMock()
    created = []
    monkeypatch.setattr(ts, "TaskContext", _fake_task_cls({"task-1": existing}, created))
    t = await ts.ensure_task("task-1", "conv-1", goal="new goal")
    assert t is existing
    assert t.goal == "old goal"           # 没被覆盖
    assert existing.save.awaited
    assert len(created) == 0              # 未插入新记录


@pytest.mark.asyncio
async def test_append_step_event(monkeypatch):
    existing = MagicMock()
    existing.step_event_ids = []
    existing.updated_at = None
    existing.save = AsyncMock()
    monkeypatch.setattr(ts, "TaskContext", _fake_task_cls({"t1": existing}, []))

    assert await ts.append_step_event("t1", "ev-1") is True
    assert existing.step_event_ids == ["ev-1"]

    # 重复 event_id → 幂等
    assert await ts.append_step_event("t1", "ev-1") is True
    assert existing.step_event_ids == ["ev-1"]


@pytest.mark.asyncio
async def test_append_step_event_missing_task(monkeypatch):
    monkeypatch.setattr(ts, "TaskContext", _fake_task_cls({}, []))
    assert await ts.append_step_event("nonexistent", "ev-1") is False


@pytest.mark.asyncio
async def test_finish_task_success(monkeypatch):
    existing = MagicMock()
    existing.status = "running"
    existing.task_delta = {}
    existing.task_rolling_summary = None
    existing.finished_at = None
    existing.updated_at = None
    existing.save = AsyncMock()
    monkeypatch.setattr(ts, "TaskContext", _fake_task_cls({"t1": existing}, []))

    t = await ts.finish_task("t1", status="completed",
                             task_delta={"summary": "ok"},
                             summary="搞定")
    assert t is existing
    assert existing.status == "completed"
    assert existing.task_delta == {"summary": "ok"}
    assert existing.task_rolling_summary == "搞定"
    assert existing.finished_at is not None


@pytest.mark.asyncio
async def test_finish_task_failed_status(monkeypatch):
    existing = MagicMock()
    existing.status = "running"
    existing.task_delta = {}
    existing.task_rolling_summary = None
    existing.finished_at = None
    existing.updated_at = None
    existing.save = AsyncMock()
    monkeypatch.setattr(ts, "TaskContext", _fake_task_cls({"t1": existing}, []))
    t = await ts.finish_task("t1", status="failed")
    assert existing.status == "failed"


@pytest.mark.asyncio
async def test_finish_task_missing(monkeypatch):
    monkeypatch.setattr(ts, "TaskContext", _fake_task_cls({}, []))
    assert await ts.finish_task("nope") is None
