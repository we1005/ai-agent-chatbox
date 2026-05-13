"""Context Engine v2 P1.1 — Event 模型 + dual-write 的最小单测。

本文件不启 FastAPI / Mongo：用 unittest.mock 替掉 Event 类的 insert/find/save，
只验证 `ConversationService.add_message` + `remove_last_assistant_message` 触发
事件写入的契约（kind / role / content / metadata / turn_id 逻辑）。

真实 Mongo 集成测试留给后续 P1.2 的 E2E smoke。

用法：
  cd backend && venv/bin/python -m pytest tests/test_event_stream.py -v --asyncio-mode=auto
"""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.models.event import Event, EventKind  # noqa: E402
from app.services import conversation_service as cs  # noqa: E402


# ── _next_turn_id ───────────────────────────────────────────────────


def _mock_find_chain(return_list):
    """伪造 `Event.find(...).sort(...).limit(...).to_list()` 链。"""
    to_list = AsyncMock(return_value=return_list)
    limit = MagicMock()
    limit.to_list = to_list
    sort = MagicMock()
    sort.limit = MagicMock(return_value=limit)
    find = MagicMock()
    find.sort = MagicMock(return_value=sort)
    return find, to_list


@pytest.mark.asyncio
async def test_next_turn_id_empty_conv(monkeypatch):
    find, _ = _mock_find_chain([])
    monkeypatch.setattr(Event, "find", lambda *a, **k: find)
    assert await cs._next_turn_id("conv-A") == 0


@pytest.mark.asyncio
async def test_next_turn_id_returns_max(monkeypatch):
    latest = MagicMock()
    latest.turn_id = 7
    find, _ = _mock_find_chain([latest])
    monkeypatch.setattr(Event, "find", lambda *a, **k: find)
    assert await cs._next_turn_id("conv-A") == 7


# ── _append_event ───────────────────────────────────────────────────


def _make_fake_event_class(latest_turn_id: int | None, captured: dict, raise_on_insert: bool = False):
    """造一个替身 Event 类：find() 返回 mocked chain，__init__ 捕获字段，insert() 可选抛错。"""
    latest_list = []
    if latest_turn_id is not None:
        m = MagicMock()
        m.turn_id = latest_turn_id
        latest_list = [m]
    find, _ = _mock_find_chain(latest_list)

    class _FakeEvent:
        def __init__(self, **kw):
            captured.update(kw)

        async def insert(self):
            if raise_on_insert:
                raise RuntimeError("mongo down")
            return self

        @classmethod
        def find(cls, *a, **k):
            return find

    return _FakeEvent


@pytest.mark.asyncio
async def test_append_event_bumps_turn_on_user_msg(monkeypatch):
    captured: dict = {}
    fake = _make_fake_event_class(latest_turn_id=3, captured=captured)
    monkeypatch.setattr(cs, "Event", fake)
    evt = await cs._append_event("conv-X", "user_msg", role="user", content="hi")
    assert evt is not None
    # user_msg → 新轮 = 4
    assert captured["turn_id"] == 4
    assert captured["kind"] == "user_msg"
    assert captured["content"] == "hi"


@pytest.mark.asyncio
async def test_append_event_reuses_turn_on_assistant(monkeypatch):
    captured: dict = {}
    fake = _make_fake_event_class(latest_turn_id=3, captured=captured)
    monkeypatch.setattr(cs, "Event", fake)
    await cs._append_event("conv-X", "assistant_msg", role="assistant", content="hello")
    # 非 user_msg 复用当前 max turn_id = 3
    assert captured["turn_id"] == 3


@pytest.mark.asyncio
async def test_append_event_first_user_msg_is_turn_1(monkeypatch):
    """空会话第一条 user_msg → turn_id = 1（0 + 1）。"""
    captured: dict = {}
    fake = _make_fake_event_class(latest_turn_id=None, captured=captured)
    monkeypatch.setattr(cs, "Event", fake)
    await cs._append_event("conv-Y", "user_msg", role="user", content="hi")
    assert captured["turn_id"] == 1


@pytest.mark.asyncio
async def test_append_event_failsoft_on_db_error(monkeypatch):
    """Mongo 异常时只 warn，不 raise——保护主流程。"""
    captured: dict = {}
    fake = _make_fake_event_class(latest_turn_id=None, captured=captured, raise_on_insert=True)
    monkeypatch.setattr(cs, "Event", fake)
    result = await cs._append_event("conv-X", "user_msg", role="user", content="hi")
    assert result is None


# ── EventKind 白名单（防止 add_message 拼错 kind 字符串）───────────


# ── load_history_for_rebuild（P1.2）───────────────────────────────


def _evt(role, content, turn_id=1, removed=False, kind=None):
    m = MagicMock()
    m.role = role
    m.content = content
    m.turn_id = turn_id
    m.kind = kind or (f"{role}_msg")
    m.metadata = {"removed": True} if removed else {}
    return m


def _mock_plain_find(return_list):
    """`Event.find(...).sort(...).to_list()`（没有 limit 的链）。"""
    to_list = AsyncMock(return_value=return_list)
    sort = MagicMock()
    sort.to_list = to_list
    find = MagicMock()
    find.sort = MagicMock(return_value=sort)
    return find


@pytest.mark.asyncio
async def test_rebuild_strips_trailing_user(monkeypatch):
    """完整的一轮对话 + 新 user_msg → 历史应去掉尾部 user。"""
    evts = [
        _evt("user",      "Q1", turn_id=1),
        _evt("assistant", "A1", turn_id=1),
        _evt("user",      "Q2", turn_id=2),  # 当前轮，要剥掉
    ]
    monkeypatch.setattr(Event, "find", classmethod(lambda cls, *a, **k: _mock_plain_find(evts)))
    hist = await cs.load_history_for_rebuild("conv-A")
    assert hist == [
        {"role": "user", "content": "Q1"},
        {"role": "assistant", "content": "A1"},
    ]


@pytest.mark.asyncio
async def test_rebuild_filters_removed(monkeypatch):
    """regenerate 标记 removed=True 的 assistant_msg 不进历史。"""
    evts = [
        _evt("user",      "Q1", turn_id=1),
        _evt("assistant", "A1-old", turn_id=1, removed=True),   # 被 regenerate 踢掉
        _evt("assistant", "A1-new", turn_id=1),
        _evt("user",      "Q2", turn_id=2),                     # 当前轮
    ]
    monkeypatch.setattr(Event, "find", classmethod(lambda cls, *a, **k: _mock_plain_find(evts)))
    hist = await cs.load_history_for_rebuild("conv-A")
    assert hist == [
        {"role": "user", "content": "Q1"},
        {"role": "assistant", "content": "A1-new"},
    ]


@pytest.mark.asyncio
async def test_rebuild_empty_conv(monkeypatch):
    monkeypatch.setattr(Event, "find", classmethod(lambda cls, *a, **k: _mock_plain_find([])))
    assert await cs.load_history_for_rebuild("conv-X") == []


@pytest.mark.asyncio
async def test_rebuild_assistant_at_tail_is_kept(monkeypatch):
    """末尾是 assistant（罕见：无新 user 的中间状态）→ 不剥。"""
    evts = [
        _evt("user",      "Q1", turn_id=1),
        _evt("assistant", "A1", turn_id=1),
    ]
    monkeypatch.setattr(Event, "find", classmethod(lambda cls, *a, **k: _mock_plain_find(evts)))
    hist = await cs.load_history_for_rebuild("conv-A")
    assert hist == [
        {"role": "user", "content": "Q1"},
        {"role": "assistant", "content": "A1"},
    ]


def test_event_kind_is_literal():
    # 确保 Literal 里的关键字没被漏改
    required = {
        "user_msg", "assistant_msg",
        "tool_call", "tool_result",
        "rag_retrieval", "web_search",
        "summary", "memory_flush",
        "intent_routed",
    }
    import typing
    args = set(typing.get_args(EventKind))
    assert required <= args, f"EventKind 缺失：{required - args}"
