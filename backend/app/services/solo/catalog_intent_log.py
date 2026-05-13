"""
目录型 query 规则识别的事件日志采集器。

每次 Solo 首轮 Planner 执行（iteration==0 → 递增为 1）时写一条 JSON-L 记录到
`logs/catalog_intent.jsonl`，记录：
  - ts             : ISO-8601 UTC 时间戳
  - query          : 用户原问题（截断到 200 字）
  - is_catalog     : 规则是否命中
  - reason         : 命中/未命中原因（"list_verb=X+doc_ref=Y" / "topic_pattern=X" / ""）
  - planner_tools  : Planner 这一轮实际触发的 tool_calls 名字列表
  - planner_has_content : Planner 是否直接输出了 <content>（跳过工具）
  - model_name     : 本次 Planner 用的模型

用途（事后离线分析，见 backend/scripts/analyze_catalog_intent.py）：
  - 统计触发率 = is_catalog=True 的占比
  - 观察命中场景下 Planner 是否真的优先调 query_knowledge_base_catalog（规则有效性）
  - 观察未命中场景下 Planner 是否仍然调了目录工具（规则漏检）
  - 抽样复查：每个象限采样若干条，人工判定假阳/假阴

写入永不阻断主流程（吞掉所有异常只打 debug 日志）。
"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger(__name__)

# 默认落在项目根 logs/，跟 backend.log 并列。支持环境变量覆盖便于测试。
# 计算路径：当前文件 backend/app/services/solo/catalog_intent_log.py
# → 上 4 级到 <project_root>，再 / logs / catalog_intent.jsonl
_HERE = os.path.dirname(os.path.abspath(__file__))
_DEFAULT_PATH = os.path.abspath(
    os.path.join(_HERE, "..", "..", "..", "..", "logs", "catalog_intent.jsonl")
)
_MAX_QUERY_CHARS = 200


def _log_path() -> str:
    return os.environ.get("CATALOG_INTENT_LOG_PATH") or _DEFAULT_PATH


def log_detection(
    *,
    query: str,
    is_catalog: bool,
    reason: str,
    planner_tools: list[str],
    planner_has_content: bool,
    model_name: str,
) -> None:
    """同步追加一条 JSON-L 记录。失败吞异常。

    小文件追加（~300 字节 / 行），单次 I/O 在 ms 级，放在 Solo 首轮同步执行不敏感。
    如果以后量级起来了（日千条以上）再改用 buffered writer / background queue。
    """
    record: dict[str, Any] = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "query": (query or "")[:_MAX_QUERY_CHARS],
        "is_catalog": bool(is_catalog),
        "reason": reason or "",
        "planner_tools": list(planner_tools or []),
        "planner_has_content": bool(planner_has_content),
        "model_name": model_name or "",
    }
    try:
        path = _log_path()
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
    except Exception as e:
        logger.debug(f"[catalog_intent_log] write failed: {e}")
