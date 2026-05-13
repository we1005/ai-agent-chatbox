"""把 Conversation.messages[] 的历史消息镜像到 events 集合（幂等）。

Context Engine v2 P1.3：P1.1 加了 Event 模型，但它只对**新写入**的消息生效；
存量会话里已经存在的 messages 还没进 events 集合。这个脚本一次性补齐。

设计要点：
  - **幂等**：跑多次不重复写入。去重键 = (conversation_id, turn_id, role, content[:50])
  - **只 backfill，不改 conversations 集合**——原 embedded messages 原样保留
  - **turn_id 按顺序分配**：每两条 user/assistant 视作一轮（遇到 user 就 +1）
  - **失败不抛**：单个 conversation 写失败只 warning，继续下一个
  - **--dry-run** 预览将写入的事件数，不落库

用法：
  cd backend && venv/bin/python scripts/backfill_events_from_messages.py [--dry-run] [--conv <id>]

见 plan-doc-dir/长上下文机制设计v2·集百家之长.md §7 P1.3。
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from pathlib import Path

# 让脚本能 import backend/app/*
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")
logger = logging.getLogger("backfill_events")


async def _main_async(args) -> int:
    # 惰性 import：init_db 内部才连 Mongo
    from app.db.database import init_db
    from app.models.conversation import Conversation
    from app.models.event import Event

    await init_db()

    query = {}
    if args.conv:
        from beanie import PydanticObjectId
        query = {"_id": PydanticObjectId(args.conv)}

    convs = await Conversation.find(query).to_list()
    logger.info(f"scanning {len(convs)} conversation(s)")

    total_scanned = 0
    total_skipped = 0
    total_written = 0
    total_errors = 0

    for conv in convs:
        conv_id = str(conv.id)
        try:
            # 已有 events 的 (content_prefix, role) 集合——去重键
            existing = await Event.find({
                "conversation_id": conv_id,
                "kind": {"$in": ["user_msg", "assistant_msg"]},
            }).to_list()
            existing_keys = {
                (ev.role, ev.content[:50]) for ev in existing
            }

            turn_id = 0
            written_this_conv = 0
            skipped_this_conv = 0
            for msg in conv.messages:
                total_scanned += 1
                role = msg.role
                content = msg.content
                # 每遇到一个 user 开新轮
                if role == "user":
                    turn_id += 1

                key = (role, content[:50])
                if key in existing_keys:
                    total_skipped += 1
                    skipped_this_conv += 1
                    continue

                kind = "user_msg" if role == "user" else "assistant_msg"
                if args.dry_run:
                    written_this_conv += 1
                    total_written += 1
                    continue

                try:
                    evt = Event(
                        conversation_id=conv_id,
                        turn_id=turn_id,
                        kind=kind,
                        role=role,
                        content=content,
                        metadata={"refs": msg.refs, "_backfilled": True} if msg.refs else {"_backfilled": True},
                        created_at=msg.created_at,
                    )
                    await evt.insert()
                    existing_keys.add(key)
                    written_this_conv += 1
                    total_written += 1
                except Exception as e:
                    total_errors += 1
                    logger.warning(f"  ! failed write conv={conv_id} turn={turn_id}: {type(e).__name__}: {e}")

            if written_this_conv or skipped_this_conv:
                logger.info(
                    f"  conv={conv_id[:8]}… title={(conv.title or '')[:20]!r} "
                    f"total={len(conv.messages)} written={written_this_conv} skipped={skipped_this_conv}"
                )

        except Exception as e:
            total_errors += 1
            logger.warning(f"! conv={conv_id} scan failed: {type(e).__name__}: {e}")

    logger.info("-" * 60)
    mode = "[DRY-RUN] " if args.dry_run else ""
    logger.info(
        f"{mode}scanned={total_scanned}  written={total_written}  "
        f"skipped={total_skipped}  errors={total_errors}"
    )
    return 0 if total_errors == 0 else 1


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true", help="只统计，不写入")
    ap.add_argument("--conv", help="只处理单个会话 ID（调试用）")
    args = ap.parse_args()
    return asyncio.run(_main_async(args))


if __name__ == "__main__":
    sys.exit(main())
