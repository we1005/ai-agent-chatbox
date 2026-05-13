from beanie import Document
from pydantic import BaseModel, Field
from datetime import datetime, timezone


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Message(BaseModel):
    role: str
    content: str
    created_at: datetime = Field(default_factory=_utcnow)
    refs: list[dict] = Field(default_factory=list)


class Conversation(Document):
    title: str | None = "New Chat"
    messages: list[Message] = []
    created_at: datetime = Field(default_factory=_utcnow)
    updated_at: datetime = Field(default_factory=_utcnow)

    class Settings:
        name = "conversations"
        indexes = ["title"]
