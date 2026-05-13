import asyncio
import json
import logging
import re

from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from app.schemas.chat import ChatRequest
from app.services.chat_service import ChatService
from app.services.conversation_service import ConversationService
from app.schemas.conversation import ConversationCreate, MessageCreate

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/chat/completions")
async def chat_completions(request: ChatRequest):
    chat_service = ChatService(model_name=request.model)

    conversation_id = request.conversation_id
    is_new_conversation = not conversation_id
    first_user_query = ""

    if is_new_conversation:
        first_user_query = request.messages[0].content if request.messages else "New Chat"
        conv = await ConversationService.create_conversation(ConversationCreate(title="New Chat"))
        conversation_id = str(conv.id)
        logger.info(f"Created new conversation: {conversation_id}")

    if request.regenerate and conversation_id:
        await ConversationService.remove_last_assistant_message(conversation_id)

    if not request.regenerate and request.messages:
        last_msg = request.messages[-1]
        if last_msg.role == "user":
            await ConversationService.add_message(conversation_id, MessageCreate(role="user", content=last_msg.content))

    async def event_generator():
        full_response = ""
        yield f"data: {json.dumps({'conversation_id': conversation_id})}\n\n"

        title_task = None
        if is_new_conversation:
            title_task = asyncio.create_task(
                chat_service.generate_title(first_user_query)
            )

        try:
            msg_dicts = [msg.model_dump() for msg in request.messages]

            # ─────────────────────────────────────────────────────────────
            # 前置 intent 检测（修复 #bc65c73 后续 issue）：
            # 早期实现里 enable_thinking 走 chat_stream_with_thinking 这条
            # parallel 分支，**完全绕过** intent 识别 / 天气 MCP 短路 / RAG
            # 注入——开 Deep Think 后问"今天天气" LLM 会胡编。
            # 修复：把 intent 检测提到 chat.py 端点层，weather 意图无视
            # enable_thinking 直接走 _handle_weather_query；general + thinking
            # 才走 chat_stream_with_thinking；general 非 thinking 走 chat_stream
            # 并把 intent_result 传下去免得二次调用 LLM。
            # 见 plan-doc-dir/长上下文机制设计v2·集百家之长.md §3 问题 #4。
            # ─────────────────────────────────────────────────────────────
            last_user_msg = next(
                (m for m in reversed(msg_dicts) if m.get("role") == "user"),
                None,
            )
            intent_result: dict = {"intent": "general"}
            if last_user_msg:
                from app.services.intent_service import detect_intent
                try:
                    intent_result = await detect_intent(last_user_msg["content"])
                except Exception as e:
                    logger.warning(f"[Intent] detect failed (fallback to general): {e}")
                    intent_result = {"intent": "general"}
            intent = intent_result.get("intent", "general")

            if intent == "weather" and last_user_msg:
                # 天气短路：thinking on/off 都走这里；不调 LLM 思考链，直接 MCP
                logger.info(
                    f"[Intent] Weather (pre-routed at endpoint, enable_thinking={request.enable_thinking}), "
                    f"city={intent_result.get('city')!r}"
                )
                async for chunk in chat_service._handle_weather_query(
                    city_keyword=intent_result.get("city") or last_user_msg["content"],
                    original_query=last_user_msg["content"],
                ):
                    full_response += chunk
                    yield f"data: {json.dumps({'content': chunk})}\n\n"
            elif request.enable_thinking and request.model.startswith("deepseek"):
                # 已知遗留：intent=="code" + thinking 时**不切 Doubao**，沉默地保留 DeepSeek
                # thinking 链路。理由：Doubao 代码模型本身不支持 thinking；用户既然主动
                # 开了 thinking，就尊重 thinking 优先（与"沉默地降级 thinking 走 Doubao"
                # 的另一选项相反）。语义决定，不做隐式切换。
                # 仅打日志 + 挂 LangSmith metadata 便于事后追踪：
                if intent == "code":
                    logger.info(
                        f"[Intent] Code + Deep Think → 保 thinking 走 DeepSeek（不切 Doubao 代码模型）"
                    )
                    try:
                        from app.services._langsmith import attach_run_metadata
                        attach_run_metadata(
                            intent="code",
                            doubao_skipped_due_to_thinking=True,
                            enable_thinking=True,
                            model=request.model,
                        )
                    except Exception:
                        pass
                async for item in chat_service.chat_stream_with_thinking(msg_dicts):
                    if item["type"] == "reasoning":
                        yield f"data: {json.dumps({'reasoning': item['text']})}\n\n"
                    elif item["type"] == "content":
                        full_response += item["text"]
                        yield f"data: {json.dumps({'content': item['text']})}\n\n"
            else:
                async for chunk in chat_service.chat_stream(
                    msg_dicts,
                    use_knowledge_base=request.use_knowledge_base,
                    use_reranker=request.use_reranker,
                    use_web_search=request.use_web_search,
                    conversation_id=conversation_id,
                    precomputed_intent=intent_result,
                ):
                    full_response += chunk
                    yield f"data: {json.dumps({'content': chunk})}\n\n"

            # ── 流结束后，解析 XML 并推送结构化数据 ──────────────────
            content_to_save = full_response
            refs_to_save: list = []

            if full_response and not request.enable_thinking:
                try:
                    # 仅当输出看起来是 XML 结构时才解析，避免把 Markdown（尤其代码块）误清洗。
                    looks_like_xml = re.search(r"<\s*(content|recommend|ref)\b", full_response) is not None
                    if looks_like_xml:
                        from app.services.xml_parser import parse_llm_xml
                        parsed = parse_llm_xml(full_response, chat_service._last_rag_docs)
                        if parsed.get("refs") or parsed.get("recommend"):
                            yield f"data: {json.dumps({'parsed': parsed})}\n\n"
                        # 保留 <ref>N</ref> 标签存入 DB，刷新后前端可重新渲染引用角标
                        content_to_save = parsed.get("content") or full_response
                        refs_to_save = parsed.get("refs", [])
                except Exception as e:
                    logger.error(f"XML parsing failed: {e}")

            yield "data: [DONE]\n\n"

            if full_response:
                await ConversationService.add_message(
                    conversation_id,
                    MessageCreate(
                        role="assistant",
                        content=content_to_save,
                        refs=refs_to_save,
                    ),
                )

                # Context Engine v2 · P3.2 · turn 结束后台反思（fire-and-forget）
                # MEMORY_REFLECT_ENABLED=false 时 reflect_and_write 立即 return []，零开销
                # —— 安全前置：Mongo 里 user_msg + assistant_msg 都已入 events
                try:
                    import asyncio as _aio
                    from app.services.conversation_service import _next_turn_id
                    from app.services.memory_service import reflect_and_write
                    _current_turn = await _next_turn_id(conversation_id)
                    _aio.create_task(
                        reflect_and_write(conversation_id, _current_turn)
                    )
                except Exception as _e:
                    logger.warning(
                        f"[memory_reflect] schedule failed (non-fatal): "
                        f"{type(_e).__name__}: {_e}"
                    )

        except Exception as e:
            logger.error(f"Error in chat stream: {e}")
            error_data = json.dumps({"error": str(e)})
            yield f"data: {error_data}\n\n"

        if title_task:
            try:
                title = await title_task
                if title:
                    await ConversationService.update_title(conversation_id, title)
                    yield f"data: {json.dumps({'title_update': title})}\n\n"
            except Exception as e:
                logger.error(f"Failed to generate title: {e}")

    return StreamingResponse(event_generator(), media_type="text/event-stream")
