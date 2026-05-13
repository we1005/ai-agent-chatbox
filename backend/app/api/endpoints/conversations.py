from fastapi import APIRouter, HTTPException
from app.services.conversation_service import ConversationService
from app.schemas.conversation import Conversation, ConversationCreate, MessageCreate

router = APIRouter()


@router.get("/conversations", response_model=list[Conversation])
async def get_conversations(skip: int = 0, limit: int = 100):
    return await ConversationService.get_conversations(skip=skip, limit=limit)


@router.get("/conversations/{conversation_id}", response_model=Conversation)
async def get_conversation(conversation_id: str):
    conversation = await ConversationService.get_conversation(conversation_id)
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return conversation


@router.post("/conversations", response_model=Conversation)
async def create_conversation(conversation: ConversationCreate):
    return await ConversationService.create_conversation(conversation)


@router.delete("/conversations/{conversation_id}")
async def delete_conversation(conversation_id: str):
    await ConversationService.delete_conversation(conversation_id)
    return {"ok": True}


@router.post("/conversations/{conversation_id}/messages")
async def add_message_to_conversation(conversation_id: str, message: MessageCreate):
    """直接向会话写入消息（bench session 回放专用，不触发 LLM 生成）。"""
    result = await ConversationService.add_message(conversation_id, message)
    if result is None:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return {"ok": True}
