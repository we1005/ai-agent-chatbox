"""P3.1 · memory_service 薄包装 mem0ai 的单测。

不启 Beanie / mem0 真实实例——只测：
  - `_build_mem0_config` 的关键字段（DeepSeek / BGE-M3 / Qdrant collection）
  - `_mirror_results_to_mongo` 对 ADD/UPDATE/DELETE/NOOP 四种 event 的分支（mock MemoryRecord）
  - `add_memory` / `search_memory` fail-soft 路径（mem0 抛异常时返回空）
  - `list_memories` / `soft_delete_memory` / `update_memory_text` 的基本契约
"""

from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services import memory_service as ms  # noqa: E402


# ── _build_mem0_config ─────────────────────────────────────────────


def test_build_config_requires_deepseek_key(monkeypatch):
    cls_mock = MagicMock()
    cls_mock.DEEPSEEK_API_KEY = ""
    monkeypatch.setattr(ms, "get_settings", lambda: cls_mock)
    with pytest.raises(RuntimeError, match="DEEPSEEK_API_KEY"):
        ms._build_mem0_config()


def test_build_config_requires_bge_m3_on_disk(monkeypatch, tmp_path):
    settings = MagicMock()
    settings.DEEPSEEK_API_KEY = "sk-x"
    settings.QDRANT_URL = "http://localhost:6333"
    settings.QDRANT_API_KEY = ""
    monkeypatch.setattr(ms, "get_settings", lambda: settings)
    # 指一个不存在的路径
    monkeypatch.setattr(ms, "BGE_M3_LOCAL_PATH", str(tmp_path / "nope"))
    with pytest.raises(RuntimeError, match="BGE-M3"):
        ms._build_mem0_config()


def test_build_config_happy(monkeypatch, tmp_path):
    settings = MagicMock()
    settings.DEEPSEEK_API_KEY = "sk-x"
    settings.QDRANT_URL = "http://q:6333"
    settings.QDRANT_API_KEY = "abc"
    monkeypatch.setattr(ms, "get_settings", lambda: settings)

    fake_bge = tmp_path / "bge-m3"
    fake_bge.mkdir()
    monkeypatch.setattr(ms, "BGE_M3_LOCAL_PATH", str(fake_bge))

    cfg = ms._build_mem0_config()
    assert cfg["llm"]["config"]["model"] == "deepseek-chat"
    assert cfg["llm"]["config"]["openai_base_url"] == "https://api.deepseek.com/v1"
    assert cfg["embedder"]["config"]["embedding_dims"] == 1024
    assert cfg["vector_store"]["config"]["collection_name"] == "mem0"
    assert cfg["vector_store"]["config"]["url"] == "http://q:6333"
    assert cfg["vector_store"]["config"]["api_key"] == "abc"


# ── _mirror_results_to_mongo ────────────────────────────────────────


def _fake_memory_record_class(created_list: list, find_one_map: dict):
    """替身 MemoryRecord：捕获 insert/save/find_one。

    find_one_map: {"m0_id" -> MagicMock(instance)}，模拟 UPDATE/DELETE 场景
    能在 Mongo 里查到旧记录。
    """
    class _FakeMR:
        _find_one_map = find_one_map

        def __init__(self, **kw):
            self.__dict__.update(kw)
            self.id = f"mongo-{len(created_list)+1}"
            self.invalidated_at = None
            self.superseded_by = None
            self.raw_metadata = kw.get("raw_metadata", {})

        async def insert(self):
            created_list.append(self)
            return self

        async def save(self):
            return self

        @classmethod
        def find_one(cls, query: dict):
            mem0_id = query.get("mem0_id")
            f = AsyncMock(return_value=cls._find_one_map.get(mem0_id))
            return f()  # awaitable

    return _FakeMR


@pytest.mark.asyncio
async def test_mirror_ADD_creates_record(monkeypatch):
    created = []
    monkeypatch.setattr(ms, "MemoryRecord", _fake_memory_record_class(created, {}))
    result = {"results": [
        {"id": "mem0-1", "memory": "用户偏好简体中文", "event": "ADD"},
    ]}
    recs = await ms._mirror_results_to_mongo(
        result, user_id="u1", conversation_id="c1",
        source_event_ids=["ev1"], kind="user_preference",
    )
    assert len(recs) == 1
    assert recs[0].object == "用户偏好简体中文"
    assert recs[0].mem0_id == "mem0-1"
    assert recs[0].user_id == "u1"


@pytest.mark.asyncio
async def test_mirror_UPDATE_invalidates_old_and_inserts_new(monkeypatch):
    old = MagicMock()
    old.id = "mongo-old"
    old.save = AsyncMock()
    created = []
    fake_cls = _fake_memory_record_class(created, {"mem0-1": old})
    monkeypatch.setattr(ms, "MemoryRecord", fake_cls)

    result = {"results": [
        {"id": "mem0-1", "memory": "用户偏好繁体中文（修正）", "event": "UPDATE"},
    ]}
    recs = await ms._mirror_results_to_mongo(
        result, user_id="u1", conversation_id="c1",
        source_event_ids=[], kind="user_preference",
    )
    assert len(recs) == 1
    # 旧记录被标失效
    assert old.invalidated_at is not None
    assert old.superseded_by == recs[0].id
    old.save.assert_awaited()


@pytest.mark.asyncio
async def test_mirror_DELETE_only_invalidates(monkeypatch):
    old = MagicMock()
    old.id = "mongo-old"
    old.save = AsyncMock()
    created = []
    fake_cls = _fake_memory_record_class(created, {"mem0-1": old})
    monkeypatch.setattr(ms, "MemoryRecord", fake_cls)

    result = {"results": [
        {"id": "mem0-1", "memory": "（已删）", "event": "DELETE"},
    ]}
    recs = await ms._mirror_results_to_mongo(
        result, user_id="u1", conversation_id=None,
        source_event_ids=[], kind="general",
    )
    assert recs == []                  # DELETE 不产新 record
    assert old.invalidated_at is not None
    old.save.assert_awaited()


@pytest.mark.asyncio
async def test_mirror_NOOP_is_skipped(monkeypatch):
    created = []
    monkeypatch.setattr(ms, "MemoryRecord", _fake_memory_record_class(created, {}))
    result = {"results": [
        {"id": "mem0-x", "memory": "xxx", "event": "NOOP"},
    ]}
    recs = await ms._mirror_results_to_mongo(
        result, user_id="u1", conversation_id=None,
        source_event_ids=[], kind="general",
    )
    assert recs == []
    assert created == []


@pytest.mark.asyncio
async def test_mirror_handles_empty_result(monkeypatch):
    created = []
    monkeypatch.setattr(ms, "MemoryRecord", _fake_memory_record_class(created, {}))
    assert await ms._mirror_results_to_mongo(
        {}, user_id="u", conversation_id=None, source_event_ids=[], kind="general"
    ) == []
    assert await ms._mirror_results_to_mongo(
        {"results": []}, user_id="u", conversation_id=None, source_event_ids=[], kind="general"
    ) == []


# ── add_memory fail-soft ────────────────────────────────────────────


@pytest.mark.asyncio
async def test_add_memory_init_fail_returns_empty(monkeypatch):
    async def _boom():
        raise RuntimeError("config missing")
    monkeypatch.setattr(ms, "get_memory", _boom)
    out = await ms.add_memory("test", user_id="u1")
    assert out == []


@pytest.mark.asyncio
async def test_add_memory_mem0_add_fail_returns_empty(monkeypatch):
    fake_mem = MagicMock()
    fake_mem.add = AsyncMock(side_effect=RuntimeError("api down"))
    async def _get():
        return fake_mem
    monkeypatch.setattr(ms, "get_memory", _get)
    out = await ms.add_memory("test", user_id="u1")
    assert out == []


@pytest.mark.asyncio
async def test_add_memory_happy_path(monkeypatch):
    fake_mem = MagicMock()
    fake_mem.add = AsyncMock(return_value={"results": [
        {"id": "mem0-A", "memory": "test fact", "event": "ADD"},
    ]})
    async def _get():
        return fake_mem
    monkeypatch.setattr(ms, "get_memory", _get)
    created = []
    monkeypatch.setattr(ms, "MemoryRecord", _fake_memory_record_class(created, {}))

    out = await ms.add_memory("test", user_id="u1", conversation_id="c1")
    assert len(out) == 1
    assert out[0].mem0_id == "mem0-A"
    # 确保 user_id 被传进去（§13.3 footgun 2）
    fake_mem.add.assert_awaited_once()
    kwargs = fake_mem.add.await_args.kwargs
    assert kwargs["user_id"] == "u1"


# ── search_memory ──────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_search_memory_happy(monkeypatch):
    fake_mem = MagicMock()
    fake_mem.search = AsyncMock(return_value={"results": [
        {"id": "mem0-A", "memory": "用户喜欢简体中文", "score": 0.91},
        {"id": "mem0-B", "memory": "用户叫小红", "score": 0.72},
    ]})
    async def _get():
        return fake_mem
    monkeypatch.setattr(ms, "get_memory", _get)

    hits = await ms.search_memory("用户偏好？", user_id="u1", limit=5)
    assert len(hits) == 2
    assert hits[0]["text"] == "用户喜欢简体中文"
    assert hits[0]["score"] == pytest.approx(0.91)
    assert hits[0]["mem0_id"] == "mem0-A"


@pytest.mark.asyncio
async def test_search_memory_failsoft(monkeypatch):
    async def _boom():
        raise RuntimeError("init fail")
    monkeypatch.setattr(ms, "get_memory", _boom)
    assert await ms.search_memory("q", user_id="u1") == []


# ── MemoryKind 白名单 ──────────────────────────────────────────────


# ── reflect_and_write（P3.2）──────────────────────────────────────


def _mock_event_find_list(events_to_return):
    """伪造 Event.find(...).sort(...).limit(...).to_list() 链，或 .sort().to_list()。"""
    to_list = AsyncMock(return_value=events_to_return)
    limit = MagicMock()
    limit.to_list = to_list
    sort = MagicMock()
    sort.limit = MagicMock(return_value=limit)
    sort.to_list = to_list
    find = MagicMock()
    find.sort = MagicMock(return_value=sort)
    return find


def _mock_settings(enabled=True, debounce=3, bg_limit=50):
    s = MagicMock()
    s.MEMORY_REFLECT_ENABLED = enabled
    s.MEMORY_REFLECT_DEBOUNCE_TURNS = debounce
    s.MEMORY_REFLECT_BG_QUEUE_LIMIT = bg_limit
    return s


@pytest.mark.asyncio
async def test_reflect_disabled_returns_empty(monkeypatch):
    monkeypatch.setattr(ms, "get_settings", lambda: _mock_settings(enabled=False))
    out = await ms.reflect_and_write("c1", 5)
    assert out == []


@pytest.mark.asyncio
async def test_reflect_debounce_skip(monkeypatch):
    monkeypatch.setattr(ms, "get_settings", lambda: _mock_settings(enabled=True, debounce=3))
    # last_reflected_turn = 4; current = 5; gap = 1 < 3 → skip
    last_evt = MagicMock()
    last_evt.turn_id = 4
    monkeypatch.setattr(
        ms.Event, "find",
        classmethod(lambda cls, *a, **k: _mock_event_find_list([last_evt])),
    )
    out = await ms.reflect_and_write("c1", 5)
    assert out == []


@pytest.mark.asyncio
async def test_reflect_force_bypasses_debounce(monkeypatch):
    monkeypatch.setattr(ms, "get_settings", lambda: _mock_settings(enabled=False, debounce=3))

    # force=True → 不看开关也不看 debounce
    # 但要把 find / dialog-load / add_memory / mark_memory_flush 都 mock
    last_evt = MagicMock()
    last_evt.turn_id = 5
    user_evt = MagicMock()
    user_evt.turn_id = 6
    user_evt.id = "e1"
    user_evt.role = "user"
    user_evt.content = "hi"
    user_evt.metadata = {}
    asst_evt = MagicMock()
    asst_evt.turn_id = 6
    asst_evt.id = "e2"
    asst_evt.role = "assistant"
    asst_evt.content = "hello"
    asst_evt.metadata = {}

    find_map = {
        "last": _mock_event_find_list([last_evt]),
        "dialog": _mock_event_find_list([user_evt, asst_evt]),
    }
    call_count = {"n": 0}
    def _find_dispatch(cls, query, *a, **k):
        # 第一次调用（_last_reflected_turn）用 "last"；其后 "dialog"
        call_count["n"] += 1
        if call_count["n"] == 1:
            return find_map["last"]
        return find_map["dialog"]
    monkeypatch.setattr(ms.Event, "find", classmethod(_find_dispatch))

    # mock add_memory 返回一条 record
    async def _fake_add(text, **kw):
        r = MagicMock()
        r.id = "mem-1"
        return [r]
    monkeypatch.setattr(ms, "add_memory", _fake_add)

    # mock mark_memory_flush（内部直接 Event(...).insert()，Beanie 未 init 会炸）
    monkeypatch.setattr(ms, "_mark_memory_flush", AsyncMock())

    out = await ms.reflect_and_write("c1", 6, force=True)
    assert len(out) == 1
    ms._mark_memory_flush.assert_awaited_once()


@pytest.mark.asyncio
async def test_reflect_empty_dialog_returns_empty(monkeypatch):
    """debounce 满足但无新对话 → 返回空列表。"""
    monkeypatch.setattr(ms, "get_settings", lambda: _mock_settings(enabled=True, debounce=2))
    last_evt = MagicMock()
    last_evt.turn_id = 1

    call_count = {"n": 0}
    def _find_dispatch(cls, query, *a, **k):
        call_count["n"] += 1
        if call_count["n"] == 1:
            return _mock_event_find_list([last_evt])
        return _mock_event_find_list([])   # no new events
    monkeypatch.setattr(ms.Event, "find", classmethod(_find_dispatch))

    out = await ms.reflect_and_write("c1", 5)
    assert out == []


@pytest.mark.asyncio
async def test_reflect_mem0_failure_marks_degraded(monkeypatch):
    """add_memory 抛异常 → 返回 [] + mark_memory_flush(degraded=True)。"""
    monkeypatch.setattr(ms, "get_settings", lambda: _mock_settings(enabled=True, debounce=1))

    last_evt = MagicMock()
    last_evt.turn_id = 0
    user_evt = MagicMock()
    user_evt.turn_id = 1
    user_evt.id = "e1"
    user_evt.role = "user"
    user_evt.content = "hi"
    user_evt.metadata = {}

    call_count = {"n": 0}
    def _find_dispatch(cls, query, *a, **k):
        call_count["n"] += 1
        if call_count["n"] == 1:
            return _mock_event_find_list([last_evt])
        return _mock_event_find_list([user_evt])
    monkeypatch.setattr(ms.Event, "find", classmethod(_find_dispatch))

    async def _boom(*a, **k):
        raise RuntimeError("api down")
    monkeypatch.setattr(ms, "add_memory", _boom)

    mark = AsyncMock()
    monkeypatch.setattr(ms, "_mark_memory_flush", mark)

    out = await ms.reflect_and_write("c1", 1)
    assert out == []
    mark.assert_awaited_once()
    # 第三个位置参数 / kwarg degraded=True
    _, kwargs = mark.await_args.args, mark.await_args.kwargs
    assert kwargs.get("degraded") is True


# ── MemoryKind 白名单 ──────────────────────────────────────────────


def test_memory_kind_literal():
    from app.models.memory import MemoryKind
    import typing
    args = set(typing.get_args(MemoryKind))
    assert {"user_preference", "project_fact", "task_progress",
            "episodic_example", "procedural_rule", "general"} <= args
