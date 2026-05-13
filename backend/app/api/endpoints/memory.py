"""P3.4 · /api/memory 审计 API

给前端 `/settings/memory` 页读 / 编辑 / 软删 durable memory。

- GET  /api/memory                列出（可 include_invalidated）
- PUT  /api/memory/{id}           手工编辑 object 文本（Mongo 侧直改，mem0 侧未同步）
- DELETE /api/memory/{id}         软删（打 invalidated_at，不动 mem0 侧）
- POST /api/memory/reflect        手工触发一次反思（force=True，越过 debounce）

见 plan-doc-dir/长上下文机制设计v2·集百家之长.md §7 P3.4。
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.services import memory_service as ms

router = APIRouter()


class MemoryUpdate(BaseModel):
    object: str


class ReflectTrigger(BaseModel):
    conversation_id: str
    current_turn_id: int | None = None
    user_id: str | None = None


def _serialize(rec) -> dict:
    return {
        "id": str(rec.id),
        "conversation_id": rec.conversation_id,
        "user_id": rec.user_id,
        "kind": rec.kind,
        "subject": rec.subject,
        "predicate": rec.predicate,
        "object": rec.object,
        "valid_at": rec.valid_at.isoformat() if rec.valid_at else None,
        "invalidated_at": rec.invalidated_at.isoformat() if rec.invalidated_at else None,
        "superseded_by": rec.superseded_by,
        "source_event_ids": rec.source_event_ids,
        "confidence": rec.confidence,
        "mem0_id": rec.mem0_id,
        "created_at": rec.created_at.isoformat() if rec.created_at else None,
        "updated_at": rec.updated_at.isoformat() if rec.updated_at else None,
        "raw_metadata": rec.raw_metadata,
    }


@router.get("/memory")
async def list_memories(
    user_id: str | None = None,
    include_invalidated: bool = False,
    limit: int = 100,
):
    """列出 durable memory。默认不含 invalidated_at 已置位的条目。"""
    recs = await ms.list_memories(
        user_id=user_id,
        include_invalidated=include_invalidated,
        limit=limit,
    )
    return {"count": len(recs), "memories": [_serialize(r) for r in recs]}


@router.put("/memory/{memory_id}")
async def update_memory(memory_id: str, body: MemoryUpdate):
    """手工编辑 memory.object 文本。Mongo 直改，raw_metadata.manually_edited=True。
    mem0 侧（Qdrant）暂不同步（首版简化，P5 再补）。"""
    rec = await ms.update_memory_text(memory_id, body.object)
    if rec is None:
        raise HTTPException(status_code=404, detail="memory not found")
    return {"ok": True, "memory": _serialize(rec)}


@router.delete("/memory/{memory_id}")
async def delete_memory(memory_id: str):
    """软删：打 invalidated_at。不从 mem0 Qdrant 真删（保留溯源）。"""
    ok = await ms.soft_delete_memory(memory_id)
    if not ok:
        raise HTTPException(status_code=404, detail="memory not found")
    return {"ok": True, "soft_deleted": True}


@router.get("/conversations/{conversation_id}/context-view")
async def get_context_view(conversation_id: str):
    """P5.2 · 返回本会话当前的"上下文视图"快照，供前端 Context Viewer 面板显示。

    内容：recent events 原文 / 最新 rolling summary / 相关 memory hits /
    最近一次 intent_routed 的 InjectionPlan 决策（如有）。

    这是**只读**端点：不改 event store，不触发新 LLM 调用。
    """
    from app.models.event import Event
    from app.services.memory_service import list_memories

    events = await (
        Event.find({"conversation_id": conversation_id})
        .sort("-created_at")
        .limit(20)
        .to_list()
    )
    # 最新 summary
    summary_evt = None
    for e in events:
        if e.kind == "summary":
            summary_evt = e
            break
    # 本会话相关的 memory（未失效）
    memories = await list_memories(include_invalidated=False, limit=20)
    conv_memories = [m for m in memories if m.conversation_id == conversation_id or m.conversation_id is None]

    def _serialize_event(e):
        return {
            "id": str(e.id),
            "turn_id": e.turn_id,
            "kind": e.kind,
            "role": e.role,
            "content_preview": (e.content or "")[:200],
            "content_length": len(e.content or ""),
            "created_at": e.created_at.isoformat() if e.created_at else None,
            "metadata_keys": list((e.metadata or {}).keys()),
        }

    return {
        "conversation_id": conversation_id,
        "events_recent": [_serialize_event(e) for e in events[:15]],
        "events_total": len(events),
        "rolling_summary": {
            "content": summary_evt.content if summary_evt else None,
            "turn_id": summary_evt.turn_id if summary_evt else None,
            "covered_event_count": (summary_evt.metadata or {}).get("covered_event_count") if summary_evt else None,
        } if summary_evt else None,
        "memory_hits": [
            {
                "id": str(m.id),
                "kind": m.kind,
                "object": m.object,
                "valid_at": m.valid_at.isoformat() if m.valid_at else None,
            }
            for m in conv_memories[:10]
        ],
    }


@router.post("/memory/reflect")
async def reflect_now(body: ReflectTrigger):
    """手工触发一次反思（force=True），绕过 debounce 与开关限制。

    调用场景：前端"立即反思"按钮 / 调试。生产后台反思走 chat.py 里的
    asyncio.create_task 自动调。
    """
    from app.services.conversation_service import _next_turn_id
    turn_id = body.current_turn_id
    if turn_id is None:
        turn_id = await _next_turn_id(body.conversation_id)
    records = await ms.reflect_and_write(
        body.conversation_id,
        turn_id,
        user_id=body.user_id,
        force=True,
    )
    return {
        "ok": True,
        "conversation_id": body.conversation_id,
        "records_created": len(records),
        "memories": [_serialize(r) for r in records],
    }
