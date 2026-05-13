"""
Query Rewriting（狭义改写）——classic 路径专用。

仅在 classic 路径 (POST /api/chat/completions) 的 RAG 检索**入口前**调用：
  - 把用户的代词 / 省略 / 过短 / 口语 query 改写成更适合向量检索的表达
  - **只影响送到 retriever 的 query**，不改写用户看到的原问题

Solo 路径不走这个模块——Planner 自己在 system prompt 的约束下完成改写
（见 solo/nodes.py 的 _SYSTEM_PROMPT_TAIL 里"查询改写"一节），避免双层 Agent。

设计要点（见 plan-doc-dir/query改写方案汇总.md）：
  - **启发式门控**：无上下文、query 已经足够清晰时**不调 LLM**，省成本和延迟
  - 触发时用 DeepSeek-chat + JSON mode 做轻量改写（非 deepseek-reasoner）
  - 失败软着陆：LLM 异常 / 解析失败 → 返回原 query，永不中断主流程
"""

from __future__ import annotations

import logging
import re

import json_repair

from app.core.config import get_settings
from app.services._langsmith import get_utility_openai

logger = logging.getLogger(__name__)
settings = get_settings()


# 触发改写的代词 / 指代 / 连接词。命中任一即启用改写。
_REFERENCE_TOKENS = (
    "它", "他", "她", "它们", "他们", "她们",
    "这个", "那个", "这些", "那些",
    "这里", "那里",
    "刚才", "上面", "前面", "上次", "上条",
    "继续", "再说说", "还有", "另外", "接着",
)

_SYSTEM_PROMPT = """\
你是查询改写助手。根据多轮对话上下文，把用户最新的一句话改写成**独立、完整、便于向量检索**的查询表达。

规则：
1. 解引用：用历史里具体的名词替换 query 中的代词 / 省略。
2. 补全：把口语化 / 过短的 query 补成完整的、可被单独检索的句子。
3. 保意图：**不要猜测用户意图、不要添加新问题、不要改变提问的主题**。
4. 如果原 query 已经独立清晰，无需改写 —— 照抄原样输出。
5. 输出长度控制在 50 字以内。

输出格式必须是 JSON：{"rewritten": "改写后的 query"}

示例：
上下文：用户上一轮问"LangGraph 是什么？" 助手已回答。
本轮 query："它怎么装？"
输出：{"rewritten": "LangGraph 怎么安装"}

上下文：无
本轮 query："帮我查下天气"
输出：{"rewritten": "帮我查下天气"}   （已足够清晰，不改）
"""


def _needs_rewrite(query: str, history_messages: list[dict]) -> tuple[bool, str]:
    """启发式判断：当前 query 是否值得花一次 LLM 改写。

    返回 (should_rewrite, reason)。
    触发条件（满足任一）：
      - 对话历史里至少有一轮 user+assistant，且 query 含代词/指代词
      - 对话历史里至少有一轮 user+assistant，且 query 长度很短（<= 10 中文字符）

    不触发时跳过 LLM 调用，直接返回原 query。
    """
    if not query or not query.strip():
        return False, "empty_query"

    # 有没有历史 assistant 回答（没有就没什么可指代的）
    has_history = any(m.get("role") == "assistant" for m in history_messages)
    if not has_history:
        return False, "no_history"

    q_stripped = query.strip()

    # 触发 1：含代词/指代连接词
    for token in _REFERENCE_TOKENS:
        if token in q_stripped:
            return True, f"reference_token:{token}"

    # 触发 2：长度过短（中文字符 ≤ 10 或整串 ≤ 15 字符）
    chinese_chars = sum(1 for c in q_stripped if "一" <= c <= "鿿")
    if chinese_chars <= 10 and len(q_stripped) <= 15:
        return True, f"short_query(zh={chinese_chars},len={len(q_stripped)})"

    return False, "looks_standalone"


def _format_history(history_messages: list[dict], max_turns: int = 2) -> str:
    """取最近 max_turns 轮 user+assistant 对话，拼成供 LLM 读的上下文块。"""
    if not history_messages:
        return "（无历史对话）"

    # 从后往前取，过滤掉 system，保留 user/assistant 成对
    pairs: list[tuple[str, str]] = []
    last_user: str | None = None
    for m in reversed(history_messages):
        role = m.get("role")
        content = (m.get("content") or "").strip()
        if not content:
            continue
        if role == "assistant" and last_user is None:
            last_user = content  # 占位
        elif role == "user" and last_user is not None:
            pairs.append((content, last_user))
            last_user = None
            if len(pairs) >= max_turns:
                break

    if not pairs:
        return "（无历史对话）"

    lines = []
    for user_msg, asst_msg in reversed(pairs):
        lines.append(f"用户: {user_msg[:200]}")
        # 助手回答可能很长，截到 300 字节省 token
        lines.append(f"助手: {asst_msg[:300]}")
    return "\n".join(lines)


async def rewrite_query_if_needed(
    user_query: str,
    history_messages: list[dict],
) -> tuple[str, str]:
    """若启发式触发则调用 LLM 改写 query，否则直接返回原样。

    返回 (final_query, reason)。final_query 要喂给 retriever；reason 用来记日志。
    永不抛异常 —— 任何异常降级为返回原 query。
    """
    should, gate_reason = _needs_rewrite(user_query, history_messages)
    if not should:
        return user_query, f"skip:{gate_reason}"

    history_text = _format_history(history_messages, max_turns=2)
    user_content = f"历史对话：\n{history_text}\n\n本轮 query: {user_query}"

    try:
        client = get_utility_openai(timeout=5.0)
        resp = await client.chat.completions.create(
            model=settings.UTILITY_LLM_MODEL,
            messages=[
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": user_content},
            ],
            response_format={"type": "json_object"},
            max_tokens=120,
            temperature=0.0,
        )
        raw = resp.choices[0].message.content or ""
        parsed = json_repair.loads(raw)
        if not isinstance(parsed, dict):
            return user_query, f"fallback:invalid_json_type:{type(parsed).__name__}"

        rewritten = str(parsed.get("rewritten") or "").strip()
        if not rewritten:
            return user_query, "fallback:empty_rewrite"

        # 安全兜底：改写后长度不应暴涨（>3 倍）或直接变空
        if len(rewritten) > max(80, len(user_query) * 3):
            return user_query, f"fallback:rewrite_too_long(len={len(rewritten)})"

        # 如果 LLM 原样返回，按"不需要改写"对待
        if rewritten == user_query.strip():
            return user_query, f"noop:{gate_reason}"

        return rewritten, f"rewrite:{gate_reason}"

    except Exception as e:
        return user_query, f"fallback:{type(e).__name__}:{e}"
