import logging

from pymongo import AsyncMongoClient
from beanie import init_beanie
from app.core.config import get_settings

settings = get_settings()
logger = logging.getLogger(__name__)


class MongoUnavailableError(RuntimeError):
    """MongoDB 不可用——由 main.lifespan 捕获后优雅退出。"""


async def init_db():
    # beanie 2.x 不再兼容 motor，改用 pymongo 原生 AsyncMongoClient。
    # serverSelectionTimeoutMS 压到 3 秒，避免默认 30s 拖出长 traceback
    client = AsyncMongoClient(
        settings.MONGODB_URL,
        serverSelectionTimeoutMS=3000,
    )
    # 主动 ping 一次，把连接失败前置到这里一个 try/except 里处理，
    # 而不是等后面 init_beanie 读集合元数据时爆长堆栈
    try:
        await client.admin.command("ping")
    except Exception as e:
        raise MongoUnavailableError(
            f"无法连接到 MongoDB（URL={settings.MONGODB_URL}）：{type(e).__name__}: {e}"
        ) from e

    db = client[settings.MONGODB_DB_NAME]

    from app.models.conversation import Conversation
    from app.models.knowledge_document import KnowledgeDocument
    from app.models.event import Event  # Context Engine v2 事件流（见 plan-doc-dir/长上下文机制设计v2·集百家之长.md）
    from app.models.memory import MemoryRecord  # Context Engine v2 P3 durable memory 审计镜像
    from app.models.task import TaskContext  # Context Engine v2 P5 复杂任务隔离
    await init_beanie(database=db, document_models=[Conversation, KnowledgeDocument, Event, MemoryRecord, TaskContext])
    logger.info(f"MongoDB connected: {settings.MONGODB_URL}/{settings.MONGODB_DB_NAME}")
