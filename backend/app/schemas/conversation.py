from pydantic import BaseModel, ConfigDict, field_validator
from datetime import datetime


class MessageBase(BaseModel):
    role: str
    content: str


class MessageCreate(MessageBase):
    refs: list[dict] = []


class MessageResponse(MessageBase):
    model_config = ConfigDict(from_attributes=True)

    created_at: datetime
    refs: list[dict] = []


class ConversationBase(BaseModel):
    title: str | None = "New Chat"


class ConversationCreate(ConversationBase):
    pass


class Conversation(ConversationBase):
    model_config = ConfigDict(from_attributes=True)

    id: str
    created_at: datetime
    updated_at: datetime
    messages: list[MessageResponse] = []

    @field_validator('id', mode='before')
    @classmethod
    def convert_objectid_to_str(cls, v):
        return str(v)
