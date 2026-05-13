"""Context Engine v2 · P3 · Durable Memory 服务

薄包装 `mem0.AsyncMemory`：
  - LLM judge（ADD/UPDATE/DELETE/NOOP）由 mem0 内部跑（DeepSeek-chat）
  - 向量存本项目 Qdrant 的**独立 collection**（`mem0`，默认 dense-only，
    不复用 kb_main 的 BGE-M3 hybrid——见 §13.3 footgun 1）
  - 每次 mem0.add 返回的事实同步镜像到 Mongo `memories` 集合（MemoryRecord），
    挂上双时间 schema（valid_at / invalidated_at / superseded_by），
    便于前端审计 + 回溯

**单例**：进程内 AsyncMemory 懒加载一次；DEEPSEEK_API_KEY / BGE-M3 路径从
settings 读。

**Fail-soft**：所有方法在 mem0 异常时只 warn 不抛，上游调用方不需要包 try。

见 plan-doc-dir/长上下文机制设计v2·集百家之长.md §13.3 / §7 P3.1。
"""

from __future__ import annotations

import asyncio
import logging
import os
from typing import Any

from app.core.config import get_settings
from app.models.event import Event
from app.models.memory import MemoryKind, MemoryRecord

logger = logging.getLogger(__name__)

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
BGE_M3_LOCAL_PATH = os.path.join(BACKEND_DIR, "data", "models", "bge-m3")

# 本项目 Qdrant 里 mem0 用的 collection 命名（与 kb_main 区分开）
_MEM0_COLLECTION_NAME = "mem0"

# 进程内单例
_instance_lock = asyncio.Lock()
_instance: Any = None  # mem0.AsyncMemory | None


# ── mem0 实例化 ─────────────────────────────────────────────────────


def _build_mem0_config() -> dict:
    """构造 mem0 配置 dict：DeepSeek + 本地 BGE-M3 + 项目 Qdrant（独立 collection）。"""
    settings = get_settings()
    if not settings.DEEPSEEK_API_KEY:
        raise RuntimeError("DEEPSEEK_API_KEY 未配置，无法构建 memory_service")
    if not os.path.isdir(BGE_M3_LOCAL_PATH):
        raise RuntimeError(f"BGE-M3 未下载到 {BGE_M3_LOCAL_PATH}；/knowledge 页激活后重试")

    # mem0 接受 OpenAI-compatible custom base_url（见 §13.3 Rank 1 代码样板）
    return {
        "llm": {
            "provider": "openai",
            "config": {
                "model": "deepseek-chat",
                "api_key": settings.DEEPSEEK_API_KEY,
                "openai_base_url": "https://api.deepseek.com/v1",
                "temperature": 0.0,
            },
        },
        "embedder": {
            "provider": "huggingface",
            "config": {
                "model": BGE_M3_LOCAL_PATH,
                "embedding_dims": 1024,    # BGE-M3 维度；与 graph_rag 硬约束对齐
            },
        },
        "vector_store": {
            "provider": "qdrant",
            "config": {
                "url": settings.QDRANT_URL,
                "api_key": settings.QDRANT_API_KEY or None,
                "collection_name": _MEM0_COLLECTION_NAME,
                "embedding_model_dims": 1024,
            },
        },
    }


async def get_memory() -> Any:
    """返回单例 AsyncMemory。延迟构造；失败不 cache（下次再试）。"""
    global _instance
    if _instance is not None:
        return _instance
    async with _instance_lock:
        if _instance is not None:
            return _instance
        from mem0 import AsyncMemory
        cfg = _build_mem0_config()
        inst = await AsyncMemory.from_config(cfg)
        _instance = inst
        logger.info("[memory_service] AsyncMemory initialized (DeepSeek + BGE-M3 + Qdrant/mem0)")
        return _instance


async def _reset_instance_for_tests() -> None:
    global _instance
    async with _instance_lock:
        _instance = None


# ── add / search / mirror ────────────────────────────────────────────


async def add_memory(
    text: str,
    *,
    user_id: str | None = None,
    conversation_id: str | None = None,
    source_event_ids: list[str] | None = None,
    metadata: dict | None = None,
    kind: MemoryKind = "general",
) -> list[MemoryRecord]:
    """把一段文本（通常是一轮对话的摘要）交给 mem0 处理，返回落到 Mongo 的
    MemoryRecord 列表（mem0 一次 add 可能产出多条事实）。

    Fail-soft：mem0 / Mongo 任何一步失败都只 warn 不抛，返回空列表。
    """
    try:
        mem = await get_memory()
    except Exception as e:
        logger.warning(f"[memory_service] init failed (non-fatal): {type(e).__name__}: {e}")
        return []

    # mem0.add 约定：`messages` 可为 str 或 list[{role,content}]
    try:
        # 注意：传 user_id 至关重要——§13.3 footgun 2：不传会跨用户去重
        result = await mem.add(
            messages=text,
            user_id=user_id or "default",
            metadata=metadata or {},
        )
    except Exception as e:
        logger.warning(f"[memory_service] mem0.add failed (non-fatal): {type(e).__name__}: {e}")
        return []

    return await _mirror_results_to_mongo(
        result,
        user_id=user_id,
        conversation_id=conversation_id,
        source_event_ids=source_event_ids or [],
        kind=kind,
    )


async def _mirror_results_to_mongo(
    result: Any,
    *,
    user_id: str | None,
    conversation_id: str | None,
    source_event_ids: list[str],
    kind: MemoryKind,
) -> list[MemoryRecord]:
    """把 mem0 返回的 event 列表镜像为 MemoryRecord。

    mem0 2.0 的 `AsyncMemory.add` 返回形如：
        {"results": [{"id": "...", "memory": "...", "event": "ADD"|"UPDATE"|"DELETE"|"NOOP"}, ...]}
    - ADD → 插一条新 MemoryRecord
    - UPDATE → 找到旧 mem0_id，mark invalidated_at + superseded_by，插新
    - DELETE → 找到旧 mem0_id，mark invalidated_at
    - NOOP → 跳过
    """
    records_created: list[MemoryRecord] = []
    if not isinstance(result, dict) or "results" not in result:
        return records_created

    for item in result.get("results", []):
        try:
            mem0_id = item.get("id")
            memory_text = item.get("memory") or ""
            event = (item.get("event") or "").upper()

            if event == "ADD":
                rec = MemoryRecord(
                    conversation_id=conversation_id,
                    user_id=user_id,
                    kind=kind,
                    subject=user_id or "user",
                    predicate="remembered",
                    object=memory_text,
                    source_event_ids=source_event_ids,
                    mem0_id=mem0_id,
                    raw_metadata={"mem0_event": event},
                )
                await rec.insert()
                records_created.append(rec)

            elif event == "UPDATE":
                old = await MemoryRecord.find_one({"mem0_id": mem0_id, "invalidated_at": None})
                new_rec = MemoryRecord(
                    conversation_id=conversation_id,
                    user_id=user_id,
                    kind=kind,
                    subject=user_id or "user",
                    predicate="remembered",
                    object=memory_text,
                    source_event_ids=source_event_ids,
                    mem0_id=mem0_id,
                    raw_metadata={"mem0_event": event,
                                  "updated_from": str(old.id) if old else None},
                )
                await new_rec.insert()
                if old:
                    from datetime import datetime, timezone
                    old.invalidated_at = datetime.now(timezone.utc)
                    old.superseded_by = str(new_rec.id)
                    await old.save()
                records_created.append(new_rec)

            elif event == "DELETE":
                old = await MemoryRecord.find_one({"mem0_id": mem0_id, "invalidated_at": None})
                if old:
                    from datetime import datetime, timezone
                    old.invalidated_at = datetime.now(timezone.utc)
                    await old.save()
                # DELETE 不产新 record

            # NOOP：跳过

        except Exception as e:
            logger.warning(
                f"[memory_service] mirror {item.get('event')} failed (non-fatal): "
                f"{type(e).__name__}: {e}"
            )
            continue

    return records_created


async def search_memory(
    query: str,
    *,
    user_id: str | None = None,
    limit: int = 5,
) -> list[dict]:
    """hybrid search 项目 Qdrant（mem0 collection）。

    返回 [{"text", "score", "mem0_id"}]。失败 fail-soft 返回空列表。
    """
    try:
        mem = await get_memory()
    except Exception as e:
        logger.warning(f"[memory_service] init failed (non-fatal): {type(e).__name__}: {e}")
        return []

    try:
        result = await mem.search(
            query=query,
            user_id=user_id or "default",
            limit=limit,
        )
    except Exception as e:
        logger.warning(f"[memory_service] mem0.search failed (non-fatal): {type(e).__name__}: {e}")
        return []

    hits: list[dict] = []
    if isinstance(result, dict) and "results" in result:
        for item in result["results"]:
            hits.append({
                "text": item.get("memory") or "",
                "score": float(item.get("score") or 0.0),
                "mem0_id": item.get("id"),
            })
    return hits


# ── 前端审计层需要的只读查询 ────────────────────────────────────────


async def list_memories(
    *,
    user_id: str | None = None,
    include_invalidated: bool = False,
    limit: int = 100,
) -> list[MemoryRecord]:
    """给 /api/memory 审计页用：列出当前有效（或含已失效）的 memory。"""
    query: dict = {}
    if user_id:
        query["user_id"] = user_id
    if not include_invalidated:
        query["invalidated_at"] = None
    return await (
        MemoryRecord.find(query)
        .sort("-updated_at")
        .limit(limit)
        .to_list()
    )


async def soft_delete_memory(record_id: str) -> bool:
    """前端"删除"按钮实际是**软删**：打 invalidated_at。不动 mem0 Qdrant 侧
    （为保持溯源能力；P5 可加异步真删选项）。"""
    from beanie import PydanticObjectId
    from datetime import datetime, timezone
    rec = await MemoryRecord.get(PydanticObjectId(record_id))
    if rec is None:
        return False
    rec.invalidated_at = datetime.now(timezone.utc)
    await rec.save()
    return True


# ── Turn-end reflection hook（P3.2，3 轮 debounce）──────────────────


# 进程级并发限制：同时最多 N 个反思任务在后台跑，防止 DB/LLM 过载
_bg_semaphore: asyncio.Semaphore | None = None


def _get_bg_semaphore() -> asyncio.Semaphore:
    global _bg_semaphore
    if _bg_semaphore is None:
        settings = get_settings()
        _bg_semaphore = asyncio.Semaphore(settings.MEMORY_REFLECT_BG_QUEUE_LIMIT)
    return _bg_semaphore


async def _last_reflected_turn(conversation_id: str) -> int:
    """查最近一次反思覆盖到的 turn_id（读 memory_flush event）。无则返回 0。"""
    events = await (
        Event.find({
            "conversation_id": conversation_id,
            "kind": "memory_flush",
        })
        .sort("-turn_id", "-created_at")
        .limit(1)
        .to_list()
    )
    if not events:
        return 0
    return int(events[0].turn_id)


async def _load_turn_dialog(conversation_id: str, since_turn_id: int) -> tuple[str, list[str], int]:
    """拉 since_turn_id+1..latest 的 user/assistant events，拼成一段文本。

    返回：(joined_text, source_event_ids, latest_turn_id)
    """
    events = await (
        Event.find({
            "conversation_id": conversation_id,
            "kind": {"$in": ["user_msg", "assistant_msg"]},
            "turn_id": {"$gt": since_turn_id},
        })
        .sort("turn_id", "created_at")
        .to_list()
    )
    if not events:
        return "", [], since_turn_id

    lines: list[str] = []
    ids: list[str] = []
    latest = since_turn_id
    for e in events:
        if e.metadata.get("removed"):
            continue
        prefix = "User" if e.role == "user" else "Assistant"
        lines.append(f"{prefix}: {e.content}")
        ids.append(str(e.id))
        latest = max(latest, int(e.turn_id))
    return "\n\n".join(lines), ids, latest


async def _mark_memory_flush(
    conversation_id: str, turn_id: int, record_ids: list[str], degraded: bool = False
) -> None:
    """写一条 memory_flush event 记下反思时间点——下次 _last_reflected_turn 读它。"""
    try:
        await Event(
            conversation_id=conversation_id,
            turn_id=turn_id,
            kind="memory_flush",
            role=None,
            content=f"memories_created={len(record_ids)}",
            metadata={
                "memory_record_ids": record_ids,
                "degraded": degraded,
            },
        ).insert()
    except Exception as e:
        logger.warning(
            f"[memory_service] mark_memory_flush failed (non-fatal): "
            f"{type(e).__name__}: {e}"
        )


async def reflect_and_write(
    conversation_id: str,
    current_turn_id: int,
    *,
    user_id: str | None = None,
    force: bool = False,
) -> list[MemoryRecord]:
    """turn 结束 hook：debounced 地把最近对话段交给 mem0 做 extract+judge+persist。

    触发条件（全部满足才干活）：
      - MEMORY_REFLECT_ENABLED=true
      - force=True OR current_turn_id - last_reflected_turn >= debounce
      - 拉到的对话段非空

    任意步骤异常 fail-soft 返回空列表，不抛。

    见 §6.3 + §7 P3.2。
    """
    settings = get_settings()
    if not settings.MEMORY_REFLECT_ENABLED and not force:
        return []

    try:
        last = await _last_reflected_turn(conversation_id)
    except Exception as e:
        logger.warning(f"[memory_service] read last_reflected failed: {type(e).__name__}: {e}")
        return []

    gap = current_turn_id - last
    if not force and gap < settings.MEMORY_REFLECT_DEBOUNCE_TURNS:
        logger.debug(
            f"[memory_service] reflect skipped (debounce): conv={conversation_id} "
            f"current_turn={current_turn_id} last={last} gap={gap} < {settings.MEMORY_REFLECT_DEBOUNCE_TURNS}"
        )
        return []

    text, source_ids, latest_turn = await _load_turn_dialog(conversation_id, last)
    if not text.strip():
        return []

    sem = _get_bg_semaphore()
    async with sem:
        try:
            records = await add_memory(
                text,
                user_id=user_id,
                conversation_id=conversation_id,
                source_event_ids=source_ids,
                kind="general",
            )
        except Exception as e:
            logger.warning(f"[memory_service] reflect_and_write failed (non-fatal): {type(e).__name__}: {e}")
            records = []

    await _mark_memory_flush(
        conversation_id,
        latest_turn,
        record_ids=[str(r.id) for r in records],
        degraded=(len(records) == 0 and bool(text.strip())),
    )
    logger.info(
        f"[memory_service] reflect_and_write: conv={conversation_id} "
        f"turn_range=({last},{latest_turn}] records={len(records)}"
    )
    return records


async def update_memory_text(record_id: str, new_text: str) -> MemoryRecord | None:
    """手工编辑 memory object 文本。Mongo 侧直改；mem0 Qdrant 侧**不同步**
    （首版简化；P5 可以加 mem0.update 调用把向量也改了）。"""
    from beanie import PydanticObjectId
    from datetime import datetime, timezone
    rec = await MemoryRecord.get(PydanticObjectId(record_id))
    if rec is None:
        return None
    rec.object = new_text
    rec.updated_at = datetime.now(timezone.utc)
    rec.raw_metadata = {**rec.raw_metadata, "manually_edited": True}
    await rec.save()
    return rec
