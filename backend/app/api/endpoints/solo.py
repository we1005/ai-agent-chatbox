"""Solo 模式聊天端点。

与 /api/chat/completions 的关系：
- 接口契约（ChatRequest / SSE 事件 content/parsed/conversation_id/[DONE]）保持一致，
  前端只需把 Solo 开关映射到不同的 URL 即可，不改渲染层。
- 新增事件：stage / tool_call，前端 AgentTrace 组件按需消费；老前端忽略也不会报错。
- 不依赖 ChatRequest 里的 use_knowledge_base / use_reranker / use_web_search / enable_thinking —— Solo 模式下 Planner 自主决定。
- 仍使用 request.regenerate 来控制"重新生成"语义（与 classic 一致）。
"""

import json
import logging
import re
from typing import Any, AsyncGenerator

from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from app.schemas.chat import ChatRequest
from app.schemas.conversation import ConversationCreate, MessageCreate
from app.services.chat_service import ChatService
from app.services.conversation_service import ConversationService
from app.services.solo.events import translate
from app.services.solo.graph import SOLO_RECURSION_LIMIT, get_solo_graph

logger = logging.getLogger(__name__)
router = APIRouter()


def _to_langchain_messages(messages: list) -> list:
    """把 ChatRequest.messages 转成 LangChain 消息对象。

    说明：Solo Graph 的 system prompt 由 planner_node 在每轮内部附加，
    所以这里即便传入 role=system 也会被 planner 的 system 覆盖到前面 —— 这没关系，
    因为用户前端理论上不应主动发 system 消息。
    """
    out = []
    for m in messages:
        role = m.role if hasattr(m, "role") else m["role"]
        content = m.content if hasattr(m, "content") else m["content"]
        if role == "user":
            out.append(HumanMessage(content=content))
        elif role == "assistant":
            out.append(AIMessage(content=content))
        elif role == "system":
            out.append(SystemMessage(content=content))
    return out


@router.post("/chat/solo")
async def chat_solo(request: ChatRequest):
    """Solo 模式入口：LangGraph ReAct 流式 SSE。"""

    # ── 会话管理（沿用 classic 的流程，避免数据层出现两套逻辑） ──
    conversation_id = request.conversation_id
    is_new_conversation = not conversation_id
    first_user_query = ""

    if is_new_conversation:
        first_user_query = request.messages[0].content if request.messages else "New Chat"
        conv = await ConversationService.create_conversation(ConversationCreate(title="New Chat"))
        conversation_id = str(conv.id)
        logger.info(f"[solo] Created new conversation: {conversation_id}")

    if request.regenerate and conversation_id:
        await ConversationService.remove_last_assistant_message(conversation_id)

    if not request.regenerate and request.messages:
        last_msg = request.messages[-1]
        if last_msg.role == "user":
            await ConversationService.add_message(
                conversation_id,
                MessageCreate(role="user", content=last_msg.content),
            )

    # 标题生成用的辅助 service（仅复用 generate_title，不走 chat_stream）
    title_service = ChatService(model_name=request.model)

    async def event_generator() -> AsyncGenerator[str, None]:
        import asyncio

        full_content = ""
        yield f"data: {json.dumps({'conversation_id': conversation_id})}\n\n"

        title_task = None
        if is_new_conversation:
            title_task = asyncio.create_task(title_service.generate_title(first_user_query))

        try:
            # P5.1 · TaskContext：Solo 请求进入时幂等创建任务上下文，
            # task_id = conversation_id（一对一，保持 LangGraph thread_id 不分裂）
            try:
                from app.services.task_service import ensure_task, finish_task
                await ensure_task(
                    task_id=conversation_id,
                    conversation_id=conversation_id,
                    goal=first_user_query or "",
                )
            except Exception as _te:
                logger.warning(f"[solo] ensure_task failed (non-fatal): {type(_te).__name__}: {_te}")

            graph = get_solo_graph()
            initial_state: dict[str, Any] = {
                "messages": _to_langchain_messages(request.messages),
                "model_name": request.model,
                "need_thinking": False,
                "iteration": 0,
            }
            # LangSmith 可观测性：metadata/tags/run_name 会自动顺着 StateGraph 传到每个节点；
            # UI 里可按 conversation_id / model / mode 过滤，便于一个会话的完整轨迹聚合查看。
            # 关闭追踪时 LangChain 依旧接受这些字段，只是不上报，零副作用。
            config = {
                "recursion_limit": SOLO_RECURSION_LIMIT,
                "metadata": {
                    "conversation_id": conversation_id,
                    "model": request.model,
                    "mode": "solo",
                },
                "tags": ["solo", f"model:{request.model}"],
                "run_name": f"solo_chat_{conversation_id[:8]}" if conversation_id else "solo_chat",
            }

            raw_events = graph.astream_events(
                initial_state,
                config=config,
                version="v2",
            )

            # 看看最终面向用户的正文里到底有没有人话（<intent>/<plan>/<thinking> 不算）
            content_outside_trace = ""

            async for out_event in translate(raw_events):
                kind = out_event["event"]
                data = out_event["data"]

                if kind == "content":
                    text = data.get("text") or ""
                    if text:
                        full_content += text
                        yield f"data: {json.dumps({'content': text})}\n\n"
                elif kind == "reasoning":
                    # DeepSeek thinking 推理链：和 classic 的 enable_thinking 使用相同 SSE 字段，
                    # 前端 store 已有 `parsed.reasoning` → `msg.reasoning` 累积逻辑，零改动即可渲染
                    text = data.get("text") or ""
                    if text:
                        yield f"data: {json.dumps({'reasoning': text})}\n\n"
                elif kind == "stage":
                    yield f"data: {json.dumps({'stage': data})}\n\n"
                elif kind == "tool_call":
                    yield f"data: {json.dumps({'tool_call': data})}\n\n"

            # ── 空内容兜底 ──────────────────────────────────────
            # 计算"trace 以外"的正文：把 intent/plan/thinking 整块拿掉，看剩下还有没有字。
            # 这样即便图里的 planner 只产出了 <intent>/<plan> 而没给 <content>，也能给用户一条
            # 真实的失败提示（而不是前端看到的空白气泡 + empty-answer 占位）。
            content_outside_trace = re.sub(
                r"<(intent|plan|thinking)>[\s\S]*?</\1>",
                "",
                full_content,
                flags=re.IGNORECASE,
            ).strip()
            if not content_outside_trace:
                logger.warning(
                    "[solo/endpoint] graph produced no user-visible <content>; "
                    "emitting synthesized failure fallback."
                )
                fallback = (
                    "<content>抱歉，本次未能生成有效回答——模型可能没有真正发起所需的工具调用，"
                    "或工具返回了异常。请点击「重新生成」重试，或切换到 DeepSeek 模型后再试。"
                    "</content>"
                )
                full_content += fallback
                yield f"data: {json.dumps({'content': fallback})}\n\n"

            # ── 流结束后，解析 XML 并推送结构化数据 ──
            content_to_save = full_content
            refs_to_save: list = []

            if full_content:
                try:
                    looks_like_xml = re.search(r"<\s*(content|recommend|ref)\b", full_content) is not None
                    if looks_like_xml:
                        from app.services.xml_parser import parse_llm_xml
                        # Solo 模式下没有像 classic 一样预先按文件分组的 rag_docs，
                        # 传空列表即可（refs 仍会从 <ref>N</ref> 中抽编号，仅没有 snippet）。
                        parsed = parse_llm_xml(full_content, [])
                        if parsed.get("refs") or parsed.get("recommend"):
                            yield f"data: {json.dumps({'parsed': parsed})}\n\n"
                        content_to_save = parsed.get("content") or full_content
                        refs_to_save = parsed.get("refs", [])
                except Exception as e:
                    logger.error(f"[solo] XML parsing failed: {e}")

            yield "data: [DONE]\n\n"

            if full_content:
                await ConversationService.add_message(
                    conversation_id,
                    MessageCreate(
                        role="assistant",
                        content=content_to_save,
                        refs=refs_to_save,
                    ),
                )

            # P5.1 · 任务完成：标 status=completed（fail-soft）
            try:
                await finish_task(conversation_id, status="completed")
            except Exception as _te:
                logger.warning(f"[solo] finish_task failed (non-fatal): {type(_te).__name__}: {_te}")

        except Exception as e:
            logger.error(f"[solo] Error in chat stream: {e}", exc_info=True)
            try:
                from app.services.task_service import finish_task as _ft
                await _ft(conversation_id, status="failed")
            except Exception:
                pass
            error_data = json.dumps({"error": str(e)})
            yield f"data: {error_data}\n\n"

        if title_task:
            try:
                title = await title_task
                if title:
                    await ConversationService.update_title(conversation_id, title)
                    yield f"data: {json.dumps({'title_update': title})}\n\n"
            except Exception as e:
                logger.error(f"[solo] Failed to generate title: {e}")

    return StreamingResponse(event_generator(), media_type="text/event-stream")
