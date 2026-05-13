"""LangGraph 原生事件 → 前端 SSE 协议事件 的翻译层。

核心策略：
- 消费 compiled_graph.astream_events(version="v2") 的事件流。
- 为每种前端 UI 关心的状态产出独立事件：
    stage      节点级生命周期（planner / tools 开始/结束）
    tool_call  单次工具调用生命周期（含 args 和 result 预览）
    content    planner 流式 token（会包含 <intent>/<plan>/<content>/<recommend> 等 XML 标签，由前端在需要时抽取）
- 只处理必要事件类型，其它事件静默忽略，避免把所有 LangGraph 细节泄漏到前端。

事件 schema（按前端契约）：
  {"event": "stage",     "data": {"id": str, "title": str, "status": "running"|"done"}}
  {"event": "tool_call", "data": {"id": str, "name": str, "args": dict,  "status": "running"}}
  {"event": "tool_call", "data": {"id": str, "name": str, "result_preview": str, "status": "done"}}
  {"event": "content",   "data": {"text": str}}
  {"event": "reasoning", "data": {"text": str}}      # DeepSeek 原生思考模式的推理链
"""

from __future__ import annotations

import logging
from typing import Any, AsyncGenerator

from app.services.solo.tools import SOLO_TOOLS_BY_NAME

logger = logging.getLogger(__name__)

_TOOL_RESULT_PREVIEW_CHARS = 400
_STAGE_TITLES = {
    "planner": "规划与回答",
    "tools": "调用工具",
}

# 只把这些"顶层"工具的调用事件吐给前端；嵌套在内的 MCP adapter runnables
# （例如 get_weather 内部再调 getWeatherInfo）不显示，避免同一次调用被拆成两条 trace。
_VISIBLE_TOOL_NAMES = set(SOLO_TOOLS_BY_NAME.keys())


def _short(text: str, limit: int = _TOOL_RESULT_PREVIEW_CHARS) -> str:
    if text is None:
        return ""
    text = str(text)
    return text if len(text) <= limit else text[:limit] + f"...[truncated, total {len(text)} chars]"


def _extract_reasoning(chunk: Any) -> str:
    """从 LLM 流式 chunk 中抽取 DeepSeek 思考模式的 reasoning_content。

    LangChain ChatOpenAI 面对 DeepSeek 返回的 reasoning_content 时，
    会把它放到 AIMessageChunk.additional_kwargs["reasoning_content"]（大多数版本）
    或直接作为顶级字段透传。这里两种都兜底一下，哪个有就取哪个。
    """
    if chunk is None:
        return ""
    try:
        # 路径 1：additional_kwargs
        ak = getattr(chunk, "additional_kwargs", None) or {}
        r = ak.get("reasoning_content") or ak.get("reasoning")
        if r:
            return str(r)
        # 路径 2：有些 LangChain 版本直接把它作为 attribute
        r = getattr(chunk, "reasoning_content", None) or getattr(chunk, "reasoning", None)
        if r:
            return str(r)
    except Exception:
        pass
    return ""


async def translate(raw_events: AsyncGenerator[dict[str, Any], None]) -> AsyncGenerator[dict[str, Any], None]:
    """消费 LangGraph `astream_events(v2)` 的事件流，产出前端协议事件。"""

    async for event in raw_events:
        kind = event.get("event")
        name = event.get("name")
        data = event.get("data") or {}

        try:
            # --- 节点级生命周期 ---
            if kind == "on_chain_start" and name in ("planner", "tools"):
                yield {
                    "event": "stage",
                    "data": {
                        "id": name,
                        "title": _STAGE_TITLES.get(name, name),
                        "status": "running",
                    },
                }
                continue

            if kind == "on_chain_end" and name in ("planner", "tools"):
                yield {
                    "event": "stage",
                    "data": {
                        "id": name,
                        "title": _STAGE_TITLES.get(name, name),
                        "status": "done",
                    },
                }
                continue

            # --- 工具单次调用（只显示顶层 SOLO_TOOLS；嵌套的 MCP adapter runnables 过滤掉）---
            if kind == "on_tool_start":
                if name not in _VISIBLE_TOOL_NAMES:
                    continue
                yield {
                    "event": "tool_call",
                    "data": {
                        "id": event.get("run_id") or "",
                        "name": name or "",
                        "args": data.get("input") or {},
                        "status": "running",
                    },
                }
                continue

            if kind == "on_tool_end":
                if name not in _VISIBLE_TOOL_NAMES:
                    continue
                output = data.get("output")
                if output is None:
                    result_preview = ""
                else:
                    # ToolNode 返回的 output 通常是 ToolMessage，取其 content
                    content = getattr(output, "content", None)
                    result_preview = _short(content if content is not None else output)
                yield {
                    "event": "tool_call",
                    "data": {
                        "id": event.get("run_id") or "",
                        "name": name or "",
                        "result_preview": result_preview,
                        "status": "done",
                    },
                }
                continue

            # --- LLM 流式 token ---
            if kind == "on_chat_model_stream":
                chunk = data.get("chunk")
                # DeepSeek thinking：reasoning_content 先于/并行于 content 到达，
                # 单独产出 reasoning 事件，前端走 thinking-block UI
                reasoning = _extract_reasoning(chunk)
                if reasoning:
                    yield {"event": "reasoning", "data": {"text": reasoning}}
                text = getattr(chunk, "content", None) if chunk is not None else None
                if text:
                    yield {"event": "content", "data": {"text": text}}
                continue

        except Exception as e:
            # 事件翻译本身不应打断主流程
            logger.debug(f"[solo/events] translate skipped event {kind}/{name}: {e}")
            continue
