"""Solo 模式的复杂度识别器。

目标：给 planner 前加一个"是否需要深度思考"的轻量分类。
复用 intent_service 的 JSON-mode + AsyncOpenAI + DeepSeek 调用骨架。
异常/超时 → 默认 False（快速路径优先，不为识别失败拖慢主流程）。
"""

from __future__ import annotations

import logging

import json_repair

from app.core.config import get_settings
from app.services._langsmith import get_utility_openai

settings = get_settings()
logger = logging.getLogger(__name__)

_COMPLEXITY_SYSTEM_PROMPT = """\
你是一个问题复杂度分类器，判断用户问题是否需要"深度思考"。

判定为 complex=true（需要深度思考）的典型特征：
- 多步数学 / 逻辑推理（证明、多步解方程、组合概率等）
- 代码 / 系统架构设计（需要权衡多个因素、取舍、方案对比）
- 多跳关系推理（A 的 B 的 C 是什么；需要跨多个实体 / 段落串联）
- 明显需要"先分析再回答"的开放问题（"分析一下……""为什么……的差别在于……"）
- 多实体 / 多方案对比（A 和 B 谁更好，以及哪些场景）

判定为 complex=false（不需要深度思考）的典型特征：
- 单一事实查询（"上海天气"、"今天星期几"）
- 简单计算（"1+1="、"3*7=")
- 闲聊 / 问候 / 指令（"你好"、"帮我总结下上文"）
- 明确指向知识库 / 联网检索的目录型问题（"知识库里有几个文档"、"查 OpenAI 最新消息"）
  —— 这些由工具直接完成，不需要额外推理链

必须以 JSON 输出：
{"complex": true|false, "reason": "不超过 20 字的判定依据"}

示例：
- "1+1=" → {"complex": false, "reason": "单步算术"}
- "证明勾股定理" → {"complex": true, "reason": "多步数学证明"}
- "上海天气" → {"complex": false, "reason": "事实查询走工具"}
- "设计一个高性能限流算法" → {"complex": true, "reason": "系统设计多权衡"}
- "比较 Redis 和 Memcached 在缓存场景下的优劣" → {"complex": true, "reason": "多维对比"}
- "你好" → {"complex": false, "reason": "闲聊"}"""


async def classify_complexity(user_query: str) -> dict:
    """返回 {"complex": bool, "reason": str}。异常/超时 → {"complex": False, "reason": "fallback:..."}。"""
    fallback = {"complex": False, "reason": "fallback_default"}
    result = fallback.copy()

    try:
        client = get_utility_openai(timeout=3.0)
        response = await client.chat.completions.create(
            model=settings.UTILITY_LLM_MODEL,
            messages=[
                {"role": "system", "content": _COMPLEXITY_SYSTEM_PROMPT},
                {"role": "user", "content": user_query},
            ],
            response_format={"type": "json_object"},
            max_tokens=60,
        )
        raw = response.choices[0].message.content or ""
        parsed = json_repair.loads(raw)

        if isinstance(parsed, dict):
            complex_flag = bool(parsed.get("complex", False))
            reason = str(parsed.get("reason") or "")[:60]
            result = {"complex": complex_flag, "reason": reason or "model_json"}
        else:
            result = {"complex": False, "reason": f"invalid_json_type:{type(parsed).__name__}"}
            logger.warning(f"[Complexity] Unexpected json_repair result type={type(parsed)}, fallback simple")

    except Exception as e:
        result = {"complex": False, "reason": f"exception:{type(e).__name__}"}
        logger.warning(f"[Complexity] classify failed, fallback simple: {e}")

    logger.info(
        f"[Complexity] complex={result['complex']} reason={result['reason']!r} "
        f"query={user_query[:60]!r}"
    )
    return result
