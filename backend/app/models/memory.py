"""MemoryRecord · Context Engine v2 P3 · durable 跨会话记忆

这张表是 mem0 写入的**审计镜像**——mem0 自己把事实向量存在 Qdrant 的独立
collection（`mem0`），我们在 Mongo 里再存一份结构化副本，目的：

  1. **可审计**：前端 /settings/memory 列表页直接读这表，用户可编辑/软删
  2. **双时间语义（Zep/Graphiti 风格）**：`valid_at` 事实生效时间 /
     `invalidated_at` 被更新事件覆盖的时间 / `superseded_by` 指向新记录
     —— 永不物理删，永远能回溯"当时模型认为事实是什么"
  3. **溯源**：`source_event_ids` 指向这条记忆来自哪些 events（P1 event stream）
  4. **不暴露 mem0 内部 ID 给前端**——保持实现解耦

见 plan-doc-dir/长上下文机制设计v2·集百家之长.md §5.3 / §13.4。
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal

from beanie import Document
from pydantic import Field
from pymongo import ASCENDING


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


MemoryKind = Literal[
    "user_preference",   # 用户偏好（语言、风格、常用模型）
    "project_fact",      # 项目事实（决策、约定、常量）
    "task_progress",     # 进行中任务状态
    "episodic_example",  # 值得 few-shot 的历史对答
    "procedural_rule",   # 后期沉淀出的规则（可合并到 rule pack）
    "general",           # 兜底：mem0 extract 未分类时使用
]


class MemoryRecord(Document):
    """一条 durable memory。同一事实被更新时：
    - 旧记录：`invalidated_at` 置当前时间，`superseded_by` 指向新 id
    - 新记录：不改老记录主键，形成链式溯源

    `mem0_id` 是 mem0 内部 UUID；本地 primary key 仍用 MongoDB ObjectId。
    """

    # 所属会话（跨会话记忆可留空）
    conversation_id: str | None = None
    user_id: str | None = None

    # 分类 + 事实文本（subject/predicate/object 三元组简化版）
    kind: MemoryKind = "general"
    subject: str = ""         # "user" / "project:chatbox" / 实体名
    predicate: str = ""       # "prefers" / "uses" / "decided"
    object: str = ""          # 自由文本，embedding 对象

    # 双时间（Zep）
    valid_at: datetime = Field(default_factory=_utcnow)
    invalidated_at: datetime | None = None
    superseded_by: str | None = None  # 另一条 MemoryRecord 的 str(id)

    # 溯源 & 元数据
    source_event_ids: list[str] = Field(default_factory=list)
    confidence: float = 1.0
    mem0_id: str | None = None      # mem0 返回的事实 ID（供 update/delete 用）
    raw_metadata: dict = Field(default_factory=dict)

    created_at: datetime = Field(default_factory=_utcnow)
    updated_at: datetime = Field(default_factory=_utcnow)

    class Settings:
        name = "memories"
        indexes = [
            [("user_id", ASCENDING), ("invalidated_at", ASCENDING)],
            [("conversation_id", ASCENDING), ("invalidated_at", ASCENDING)],
            [("mem0_id", ASCENDING)],
            [("kind", ASCENDING)],
        ]
