import logging
import json_repair
from app.core.config import get_settings
from app.services._langsmith import get_utility_openai

settings = get_settings()
logger = logging.getLogger(__name__)

_INTENT_SYSTEM_PROMPT = """\
你是一个意图分类器，判断用户问题的类型，同时提取关键实体。

分类规则：
- code：与编程/代码/算法/技术架构相关（包括编程语言语法、算法实现、代码调试、代码审查、框架/库使用等）
- weather：询问某地的天气、气温、气候、降雨、风力等气象状况
- general：其他所有问题

必须以 JSON 格式输出：
{"intent": "code"|"weather"|"general", "city": "城市或区县名（仅 intent 为 weather 时填写，其余填 null）"}

示例：
- "帮我写个快排" → {"intent": "code", "city": null}
- "朝阳区今天天气怎么样" → {"intent": "weather", "city": "朝阳区"}
- "帝都明天会下雨吗" → {"intent": "weather", "city": "北京"}
- "上海今天热不热" → {"intent": "weather", "city": "上海"}
- "什么是量子计算" → {"intent": "general", "city": null}"""


async def detect_intent(user_query: str) -> dict:
    """
    调用 DeepSeek JSON 模式对用户问题进行三分类，同时提取天气查询中的城市名。

    返回格式：{"intent": "code"|"weather"|"general", "city": str|None}
    任何异常均降级返回 {"intent": "general", "city": None}，不中断主流程。
    """
    fallback = {"intent": "general", "city": None}
    reason = "fallback_default"
    result = fallback.copy()

    try:
        client = get_utility_openai(timeout=3.0)
        response = await client.chat.completions.create(
            model=settings.UTILITY_LLM_MODEL,
            messages=[
                {"role": "system", "content": _INTENT_SYSTEM_PROMPT},
                {"role": "user", "content": user_query},
            ],
            response_format={"type": "json_object"},
            max_tokens=40,
        )
        raw = response.choices[0].message.content or ""
        parsed = json_repair.loads(raw)

        if not isinstance(parsed, dict):
            reason = f"invalid_json_type:{type(parsed).__name__}"
            logger.warning(f"[Intent] Unexpected json_repair result type={type(parsed)}, fallback general")
        else:
            intent = parsed.get("intent", "general")
            if intent not in ("code", "weather", "general"):
                intent = "general"
            city = parsed.get("city") or None
            result = {"intent": intent, "city": city}
            reason = "model_json"

    except Exception as e:
        reason = f"exception:{type(e).__name__}"
        logger.warning(f"[Intent] Detection failed, fallback to general: {e}")

    logger.info(
        f"[Intent] intent={result['intent']} city={result['city']!r} "
        f"reason={reason} query={user_query[:50]!r}"
    )
    return result
