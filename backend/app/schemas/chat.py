from pydantic import BaseModel


class ChatMessage(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    messages: list[ChatMessage]
    model: str = "kimi-k2-0905-preview"
    conversation_id: str | None = None
    stream: bool = True
    use_knowledge_base: bool = False
    use_reranker: bool = False
    use_web_search: bool = False
    enable_thinking: bool = False
    regenerate: bool = False
