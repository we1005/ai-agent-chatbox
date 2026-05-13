"""LangSmith 集成入口（fail-soft，默认零开销）。

统一所有 AsyncOpenAI 创建和 @traceable 引入的入口。
当 LANGSMITH_TRACING 不为 true 时：
  - get_openai(**kw) 直接返回原始 AsyncOpenAI，不包任何东西
  - traceable 降级为 no-op 装饰器
  - 不 import langsmith（懒加载），避免冷启动引入额外依赖

设计背景见 plan-doc-dir/集成LangSmith可观测性.md。
"""

from __future__ import annotations

import logging
import os
from typing import Any, Callable, TypeVar

logger = logging.getLogger(__name__)

F = TypeVar("F", bound=Callable[..., Any])


def _tracing_enabled() -> bool:
    return os.environ.get("LANGSMITH_TRACING", "").lower() in ("true", "1", "yes")


def get_utility_openai(**kwargs):
    """工具链 LLM 客户端（意图/改写/Condenser/AgenticRAG/MultiQuery/Solo 复杂度）。

    读取 UTILITY_LLM_* 配置；UTILITY_LLM_API_KEY 为空时 fallback 到 DEEPSEEK_API_KEY。
    LangSmith 追踪行为与 get_openai() 完全一致。
    """
    from app.core.config import get_settings  # 延迟 import，运行时读最新 settings
    s = get_settings()
    api_key = s.UTILITY_LLM_API_KEY or s.DEEPSEEK_API_KEY
    base_url = s.UTILITY_LLM_BASE_URL
    return get_openai(api_key=api_key, base_url=base_url, **kwargs)


def get_openai(**kwargs):
    """替代 AsyncOpenAI(...) 的统一构造入口。

    关闭追踪时：返回原始 AsyncOpenAI 客户端，零开销。
    开启追踪时：用 langsmith.wrappers.wrap_openai 包装，捕获每一次 chat.completions.create。
    包装失败（如 langsmith 版本不匹配）吞异常降级为原客户端，永不阻断主流程。
    """
    from openai import AsyncOpenAI  # 延迟 import 避免循环
    client = AsyncOpenAI(**kwargs)
    if not _tracing_enabled():
        return client
    try:
        from langsmith.wrappers import wrap_openai
        return wrap_openai(client)
    except Exception as e:
        logger.warning(f"[langsmith] wrap_openai failed, fallback to plain client: {e}")
        return client


def traceable(*dargs, **dkwargs):
    """@traceable 装饰器的透明代理。

    关闭追踪时：返回 no-op 装饰器，保留原函数签名和类型。
    开启追踪时：转发到 langsmith.traceable，参数原样传递（name / run_type / metadata / tags）。

    用法：
        @traceable(name="classic_chat_stream", run_type="chain")
        async def chat_stream(...): ...
    """
    if not _tracing_enabled():
        # no-op：支持 @traceable 和 @traceable(name=...) 两种调用形式
        if dargs and callable(dargs[0]) and not dkwargs:
            return dargs[0]

        def _noop(fn: F) -> F:
            return fn

        return _noop

    try:
        from langsmith import traceable as _real_traceable
        return _real_traceable(*dargs, **dkwargs)
    except Exception as e:
        logger.warning(f"[langsmith] traceable import failed, fallback to no-op: {e}")
        if dargs and callable(dargs[0]) and not dkwargs:
            return dargs[0]

        def _noop(fn: F) -> F:
            return fn

        return _noop


def attach_run_metadata(**metadata) -> None:
    """把 metadata 挂到当前 run tree 上（用于后续按 conversation_id / model 过滤）。

    只在追踪开启且当前处于 run 上下文时生效；其余情况静默。
    """
    if not _tracing_enabled() or not metadata:
        return
    try:
        from langsmith.run_helpers import get_current_run_tree
        rt = get_current_run_tree()
        if rt is None:
            return
        # RunTree 在 langsmith 0.3+ 支持直接 .metadata dict；老版本用 .extra.setdefault
        existing = getattr(rt, "metadata", None)
        if existing is None:
            extra = getattr(rt, "extra", None)
            if extra is None:
                return
            existing = extra.setdefault("metadata", {})
        existing.update(metadata)
    except Exception as e:
        logger.debug(f"[langsmith] attach_run_metadata failed (non-fatal): {e}")
