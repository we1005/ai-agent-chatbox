import json
import logging
import re
from beanie import PydanticObjectId
from app.models.conversation import Conversation, Message, _utcnow
from app.models.event import Event, EventKind
from app.schemas.conversation import ConversationCreate, MessageCreate

logger = logging.getLogger(__name__)


# ── Event stream 镜像（Context Engine v2 P1.1）──────────────────────
# add_message / remove_last_assistant_message 在写 Conversation.messages 之外
# 同步镜像一份到 events 集合，供未来 chat_stream 从服务端重建上下文（P1.2）。
# 当前阶段纯旁路写入，即便 events 写失败也不影响主流程。
# 见 plan-doc-dir/长上下文机制设计v2·集百家之长.md §7 P1.1 / §5.2。


async def _next_turn_id(conversation_id: str) -> int:
    """返回该会话下一轮 turn_id（从 0 起；同一轮 user+assistant+tool_* 共享）。

    策略：一个"user_msg"开一个新轮；其它 event 加入该轮。
    实现：找到 max(turn_id) + (1 if 最后一个 event 是 user_msg else 0)。
    简化规则：只要下一条是 user_msg 就新开一轮；否则复用当前 max。
    """
    last = await (
        Event.find({"conversation_id": conversation_id})
        .sort("-turn_id", "-created_at")
        .limit(1)
        .to_list()
    )
    if not last:
        return 0
    return int(last[0].turn_id)


async def load_events_for_conv(
    conversation_id: str, *, include_summary: bool = True
) -> list[Event]:
    """拉会话全部 events（按 turn_id + created_at 升序），供 condenser 处理（P2.3）。

    - 过滤 metadata.removed=True
    - include_summary=False 时跳过 kind="summary"（某些场景只想看原始对话）
    """
    query = {
        "conversation_id": conversation_id,
    }
    events = await Event.find(query).sort("turn_id", "created_at").to_list()
    return [
        e for e in events
        if not e.metadata.get("removed") and (include_summary or e.kind != "summary")
    ]


async def persist_summary_event(summary_like) -> Event | None:
    """把 Condenser 产出的 summary（SimpleNamespace 替身）落盘为真 Event Document。

    调用前提：Beanie 已初始化。失败 fail-soft 不抛。
    """
    try:
        evt = Event(
            conversation_id=summary_like.conversation_id,
            turn_id=summary_like.turn_id,
            kind="summary",
            role=None,
            content=summary_like.content,
            tokens=getattr(summary_like, "tokens", 0),
            metadata=dict(getattr(summary_like, "metadata", {})),
            created_at=getattr(summary_like, "created_at", _utcnow()),
        )
        await evt.insert()
        return evt
    except Exception as e:
        logger.warning(
            f"[event_stream] persist summary failed (non-fatal) "
            f"conv={getattr(summary_like, 'conversation_id', '?')}: {type(e).__name__}: {e}"
        )
        return None


async def load_history_for_rebuild(conversation_id: str) -> list[dict]:
    """从 events 集合重建聊天历史供 chat_stream 消费（P1.2）。

    约定：
      - 只拉 user_msg / assistant_msg 两类（tool_call 等不是对话历史）
      - 过滤 metadata.removed=True（regenerate 留痕的旧 assistant）
      - 按 (turn_id, created_at) 升序排列
      - **剥掉尾部的 user_msg**——它是当前轮的镜像（chat.py:34-37 在调 chat_stream 前
        已经写入 events），不应出现在历史里；`user_query` 仍由 chat_stream 自己从
        messages[-1] 取，维持现有合同。

    返回格式与 chat_stream 入参一致：[{"role": "user"|"assistant", "content": ...}, ...]
    """
    events = await (
        Event.find({
            "conversation_id": conversation_id,
            "kind": {"$in": ["user_msg", "assistant_msg"]},
        })
        .sort("turn_id", "created_at")
        .to_list()
    )
    history: list[dict] = []
    for ev in events:
        if ev.metadata.get("removed"):
            continue
        role = ev.role or ("user" if ev.kind == "user_msg" else "assistant")
        history.append({"role": role, "content": ev.content})
    # 剥掉尾部 user_msg（当前轮输入；chat_stream 自己处理）
    if history and history[-1]["role"] == "user":
        history.pop()
    return history


async def _append_event(
    conversation_id: str,
    kind: EventKind,
    *,
    role: str | None = None,
    content: str = "",
    tokens: int = 0,
    metadata: dict | None = None,
    turn_id: int | None = None,
) -> Event | None:
    """低层 event 追加。失败只打 warning，不抛异常（P1.1 阶段 fail-soft）。"""
    try:
        if turn_id is None:
            turn_id = await _next_turn_id(conversation_id)
            # user_msg 开新轮
            if kind == "user_msg":
                turn_id += 1
        evt = Event(
            conversation_id=conversation_id,
            turn_id=turn_id,
            kind=kind,
            role=role,
            content=content,
            tokens=tokens,
            metadata=metadata or {},
        )
        await evt.insert()
        return evt
    except Exception as e:
        logger.warning(
            f"[event_stream] mirror failed (non-fatal) "
            f"conv={conversation_id} kind={kind}: {type(e).__name__}: {e}"
        )
        return None


class ConversationService:
    @staticmethod
    async def create_conversation(conversation: ConversationCreate) -> Conversation:
        db_conversation = Conversation(title=conversation.title)
        await db_conversation.insert()
        return db_conversation

    @staticmethod
    async def get_conversations(skip: int = 0, limit: int = 100) -> list[Conversation]:
        return await Conversation.find_all().sort("-updated_at").skip(skip).limit(limit).to_list()

    @staticmethod
    async def get_conversation(conversation_id: str) -> Conversation | None:
        return await Conversation.get(PydanticObjectId(conversation_id))

    @staticmethod
    async def delete_conversation(conversation_id: str):
        conversation = await Conversation.get(PydanticObjectId(conversation_id))
        if conversation:
            await conversation.delete()

    @staticmethod
    async def add_message(conversation_id: str, message: MessageCreate) -> Message | None:
        conversation = await Conversation.get(PydanticObjectId(conversation_id))
        if not conversation:
            return None

        new_message = Message(
            role=message.role,
            content=message.content,
            refs=message.refs,
        )
        conversation.messages.append(new_message)
        conversation.updated_at = _utcnow()
        await conversation.save()

        # 镜像到 event stream（P1.1，fail-soft；P1.2 开始会用它重建历史）
        kind: EventKind = "user_msg" if message.role == "user" else "assistant_msg"
        await _append_event(
            conversation_id,
            kind,
            role=message.role,
            content=message.content,
            metadata={"refs": message.refs} if message.refs else {},
        )
        return new_message

    @staticmethod
    async def remove_last_assistant_message(conversation_id: str):
        conversation = await Conversation.get(PydanticObjectId(conversation_id))
        if conversation and conversation.messages:
            if conversation.messages[-1].role == "assistant":
                conversation.messages.pop()
                conversation.updated_at = _utcnow()
                await conversation.save()
                # 镜像到 event stream：regenerate 场景，标记最后一个 assistant_msg 事件为 removed
                try:
                    last = await (
                        Event.find({
                            "conversation_id": conversation_id,
                            "kind": "assistant_msg",
                        })
                        .sort("-created_at")
                        .limit(1)
                        .to_list()
                    )
                    if last:
                        last[0].metadata["removed"] = True
                        await last[0].save()
                except Exception as e:
                    logger.warning(
                        f"[event_stream] mark-removed failed (non-fatal) "
                        f"conv={conversation_id}: {type(e).__name__}: {e}"
                    )

    @staticmethod
    async def update_title(conversation_id: str, title: str):
        conversation = await Conversation.get(PydanticObjectId(conversation_id))
        if conversation:
            conversation.title = title
            await conversation.save()

    @staticmethod
    async def search_conversations(query: str) -> list[Conversation]:
        pattern = re.compile(re.escape(query), re.IGNORECASE)
        return await Conversation.find(
            {"title": {"$regex": pattern}}
        ).sort("-updated_at").to_list()
