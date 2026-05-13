"""Memory Bench 共享工具函数。

与 run_rag_bench.py 的 sse_chat / load_queries 模式对齐，
新增：create_bench_conversation / replay_session / wait_for_reflection /
      set_context_engine_config / load_bench_questions。
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from pathlib import Path
from typing import Any

import httpx

logger = logging.getLogger(__name__)

BASE_URL = "http://localhost:8000"

BENCH_CONFIGS: dict[str, dict] = {
    "baseline_off": {
        "context_engine": False, "memory_reflect": False, "memory_retrieval": False,
        "label": "Baseline（仅 Event Stream 真相源）",
    },
    "condenser_only": {
        "context_engine": True,  "memory_reflect": False, "memory_retrieval": False,
        "label": "Condenser（Recent Buffer + Rolling Summary）",
    },
    "condenser_reflect": {
        "context_engine": True,  "memory_reflect": True,  "memory_retrieval": False,
        "label": "Condenser + Mem0 反思（写 memories，不检索）",
    },
    "full": {
        "context_engine": True,  "memory_reflect": True,  "memory_retrieval": True,
        "label": "Full（Context Router + Memory 注入）",
    },
}


async def create_bench_conversation(client: httpx.AsyncClient, title: str = "bench") -> str:
    """创建 bench 专用会话，返回 conversation_id。"""
    resp = await client.post(
        f"{BASE_URL}/api/conversations",
        json={"title": title},
        timeout=10.0,
    )
    resp.raise_for_status()
    data = resp.json()
    return str(data.get("_id") or data.get("id") or data["id"])


async def replay_session(
    client: httpx.AsyncClient,
    conv_id: str,
    messages: list[dict],
    delay: float = 0.05,
) -> None:
    """把一段 session history 逐条写入 Mongo（通过 add_message API）。

    messages 格式：[{"role": "user"|"assistant", "content": "..."}, ...]
    """
    for msg in messages:
        role = msg.get("role", "user")
        content = msg.get("content", "")
        if not content:
            continue
        try:
            resp = await client.post(
                f"{BASE_URL}/api/conversations/{conv_id}/messages",
                json={"role": role, "content": content, "refs": []},
                timeout=15.0,
            )
            resp.raise_for_status()
        except Exception as e:
            logger.warning(f"[replay_session] add_message failed: {e}")
        await asyncio.sleep(delay)


async def wait_for_reflection(
    client: httpx.AsyncClient,
    conv_id: str,
    timeout: float = 30.0,
    stable_gap: float = 2.0,
) -> bool:
    """轮询 memory_flush 事件计数，等到稳定（两次 stable_gap 秒间隔 count 不变）。

    返回 True 表示稳定，False 表示超时。
    """
    deadline = time.monotonic() + timeout
    prev_count = -1
    stable_since: float | None = None

    while time.monotonic() < deadline:
        try:
            resp = await client.get(
                f"{BASE_URL}/api/conversations/{conv_id}/events",
                params={"kind": "memory_flush"},
                timeout=5.0,
            )
            count = len(resp.json()) if resp.is_success else 0
        except Exception:
            count = prev_count

        if count == prev_count and count >= 0:
            if stable_since is None:
                stable_since = time.monotonic()
            elif time.monotonic() - stable_since >= stable_gap:
                return True
        else:
            stable_since = None
            prev_count = count

        await asyncio.sleep(1.0)

    return False


async def sse_chat_memory(
    client: httpx.AsyncClient,
    conv_id: str,
    question: str,
    model: str = "qwen3.5-flash",
    use_knowledge_base: bool = False,
) -> dict[str, Any]:
    """向 /api/chat/completions 发 SSE 请求，收集完整回答。

    返回 {"answer": str, "latency_ms": int, "error": str|None}
    """
    payload = {
        "conversation_id": conv_id,
        "messages": [{"role": "user", "content": question}],
        "model": model,
        "stream": True,
        "use_knowledge_base": use_knowledge_base,
        "use_web_search": False,
        "enable_thinking": False,
    }
    answer_parts: list[str] = []
    error: str | None = None
    t0 = time.monotonic()

    try:
        async with client.stream(
            "POST",
            f"{BASE_URL}/api/chat/completions",
            json=payload,
            timeout=httpx.Timeout(180.0, read=120.0),
        ) as resp:
            resp.raise_for_status()
            async for line in resp.aiter_lines():
                if not line.startswith("data: "):
                    continue
                raw = line[6:].strip()
                if raw == "[DONE]":
                    break
                try:
                    ev = json.loads(raw)
                except json.JSONDecodeError:
                    continue
                if "parsed" in ev:
                    answer_parts = [ev["parsed"].get("content", "")]
                    break
                if "content" in ev:
                    answer_parts.append(ev["content"])
    except Exception as e:
        error = f"{type(e).__name__}: {e}"
        logger.warning(f"[sse_chat_memory] error conv={conv_id}: {e}")

    latency_ms = int((time.monotonic() - t0) * 1000)
    answer = "".join(answer_parts).strip()
    # 去掉 XML 结构标签（如果模型输出了 <content>...</content>）
    for tag in ("<content>", "</content>", "<recommend>", "</recommend>"):
        answer = answer.replace(tag, "")
    answer = answer.strip()
    return {"answer": answer, "latency_ms": latency_ms, "error": error}


async def set_context_engine_config(
    client: httpx.AsyncClient,
    context_engine: bool,
    memory_reflect: bool,
    memory_retrieval: bool,
) -> None:
    """通过 admin 端点切换 Context Engine feature flags。"""
    resp = await client.put(
        f"{BASE_URL}/api/admin/context-engine-config",
        json={
            "context_engine": context_engine,
            "memory_reflect": memory_reflect,
            "memory_retrieval": memory_retrieval,
        },
        timeout=10.0,
    )
    resp.raise_for_status()
    data = resp.json()
    logger.info(
        f"[bench] config switched: "
        f"context_engine={data['context_engine']} "
        f"memory_reflect={data['memory_reflect']} "
        f"memory_retrieval={data['memory_retrieval']}"
    )


def load_bench_questions(path: str | Path, limit: int | None = None) -> list[dict]:
    """读取 JSONL 格式的 benchmark 问题集，支持可选数量上限。"""
    records: list[dict] = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    if limit and limit > 0:
        records = records[:limit]
    return records
