"""LongMemEval-S Memory Benchmark Runner。

5 配置 × N QA，全程使用 qwen3.5-flash。

用法：
    # smoke：baseline_off 配置，只跑 3 条
    python scripts/run_memory_bench.py --config baseline_off --limit 3

    # 所有配置，oracle 250 条
    python scripts/run_memory_bench.py --config all --limit 250 \\
        --questions tests/eval-data/longmemeval/oracle_questions.jsonl

输出：
    tests/eval-data/results/memory_run_<timestamp>.jsonl
    tests/eval-data/results/memory_latest.jsonl  (symlink)
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import httpx

# ── 路径设置 ─────────────────────────────────────────────────────────────
SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parents[1]
BACKEND_ROOT = SCRIPT_DIR.parent
sys.path.insert(0, str(BACKEND_ROOT))

from scripts.bench_utils import (  # noqa: E402
    BENCH_CONFIGS,
    create_bench_conversation,
    load_bench_questions,
    replay_session,
    set_context_engine_config,
    sse_chat_memory,
    wait_for_reflection,
)

RESULTS_DIR = PROJECT_ROOT / "tests" / "eval-data" / "results"
QUESTIONS_DEFAULT = PROJECT_ROOT / "tests" / "eval-data" / "longmemeval" / "full_questions.jsonl"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-7s %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


def _extract_session_messages(qa: dict) -> list[dict]:
    """从 LongMemEval QA 记录中提取 session history 消息列表。

    支持两种格式：
      真实数据：qa["haystack_sessions"] 是 list[list[dict]]，每个 session 直接是消息列表
      合成数据：qa["haystack_sessions"] 是 list[dict]，每个 session 有 "conversations" key
    """
    messages: list[dict] = []
    sessions = qa.get("haystack_sessions") or qa.get("sessions") or []
    for session in sessions:
        if isinstance(session, list):
            turns = session
        elif isinstance(session, dict):
            turns = session.get("conversations") or session.get("messages") or []
        else:
            continue
        for turn in turns:
            role = turn.get("role", "")
            content = turn.get("content", "")
            if role in ("user", "assistant") and content:
                messages.append({"role": role, "content": content})
    return messages


async def run_config(
    config_name: str,
    config: dict,
    questions: list[dict],
    model: str,
    out_file,
    client: httpx.AsyncClient,
) -> int:
    """跑单个 config 下的所有 QA，写结果到 out_file。返回成功条数。"""
    logger.info(f"\n{'='*60}")
    logger.info(f"Config: {config_name} — {config['label']}")
    logger.info(f"QA 数量: {len(questions)}  模型: {model}")
    logger.info(f"{'='*60}")

    await set_context_engine_config(
        client,
        context_engine=config["context_engine"],
        memory_reflect=config["memory_reflect"],
        memory_retrieval=config["memory_retrieval"],
    )

    success = 0
    for i, qa in enumerate(questions, 1):
        qid = str(qa.get("question_id") or qa.get("session_id") or qa.get("qid") or i)
        question_type = str(qa.get("question_type") or "unknown")
        question = str(qa.get("question") or "")
        gold_answer = str(qa.get("answer") or "")

        if not question:
            logger.warning(f"[{i}/{len(questions)}] qid={qid} question 为空，跳过")
            continue

        logger.info(f"[{i}/{len(questions)}] qid={qid} type={question_type}")
        logger.info(f"  Q: {question[:80]}")

        # 1. 建 bench 会话
        try:
            conv_id = await create_bench_conversation(
                client, title=f"bench_{config_name}_{qid}"
            )
        except Exception as e:
            logger.warning(f"  create_conversation failed: {e}")
            _write_row(out_file, config_name, qid, question_type, question, gold_answer,
                       "", 0, f"create_conv:{e}")
            continue

        # 2. 回放 session history
        session_msgs = _extract_session_messages(qa)
        if session_msgs:
            logger.info(f"  回放 {len(session_msgs)} 条历史消息 ...")
            await replay_session(client, conv_id, session_msgs, delay=0.2)
        else:
            logger.info("  无 session history，直接问答")

        # 3. 等待 memory 反思完成（仅 memory_reflect=True 时有意义）
        if config["memory_reflect"] and session_msgs:
            logger.info("  等待 Mem0 反思完成 ...")
            await wait_for_reflection(client, conv_id, timeout=30.0)

        # 4. 发问
        result = await sse_chat_memory(client, conv_id, question, model=model)
        logger.info(
            f"  A: {result['answer'][:80]!r}  "
            f"latency={result['latency_ms']}ms  "
            f"error={result['error']}"
        )

        _write_row(
            out_file, config_name, qid, question_type, question, gold_answer,
            result["answer"], result["latency_ms"], result["error"],
        )
        if not result["error"]:
            success += 1

        # 礼貌间隔，避免撞 DashScope RPM 限制
        await asyncio.sleep(0.5)

    logger.info(f"Config {config_name} 完成：{success}/{len(questions)} 成功")
    return success


def _write_row(
    f,
    config: str,
    qid: str,
    question_type: str,
    question: str,
    gold_answer: str,
    answer: str,
    latency_ms: int,
    error: str | None,
) -> None:
    row = {
        "config": config,
        "qid": qid,
        "question_type": question_type,
        "question": question,
        "gold_answer": gold_answer,
        "answer": answer,
        "latency_ms": latency_ms,
        "error": error,
    }
    f.write(json.dumps(row, ensure_ascii=False) + "\n")
    f.flush()


async def main() -> None:
    parser = argparse.ArgumentParser(description="LongMemEval-S memory benchmark runner")
    parser.add_argument(
        "--config",
        default="baseline_off",
        help=f"配置名（baseline_off / condenser_only / condenser_reflect / full / all），默认 baseline_off",
    )
    parser.add_argument("--limit", type=int, default=0, help="每 config 最多跑 N 条（0=全量）")
    parser.add_argument(
        "--questions",
        type=str,
        default=str(QUESTIONS_DEFAULT),
        help="问题集 JSONL 路径",
    )
    parser.add_argument("--model", type=str, default="qwen3.5-flash", help="被测模型")
    args = parser.parse_args()

    questions_path = Path(args.questions)
    if not questions_path.exists():
        logger.error(f"问题集不存在：{questions_path}")
        logger.error("请先运行：python scripts/fetch_longmemeval.py --sample 10")
        sys.exit(1)

    questions = load_bench_questions(questions_path, limit=args.limit or None)
    logger.info(f"加载 {len(questions)} 条 QA from {questions_path.name}")

    selected_configs: list[str] = []
    if args.config == "all":
        selected_configs = list(BENCH_CONFIGS.keys())
    elif args.config in BENCH_CONFIGS:
        selected_configs = [args.config]
    else:
        logger.error(f"未知 config: {args.config}，可选：{list(BENCH_CONFIGS.keys())} / all")
        sys.exit(1)

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    out_path = RESULTS_DIR / f"memory_run_{ts}.jsonl"
    latest_link = RESULTS_DIR / "memory_latest.jsonl"

    t_start = time.monotonic()
    logger.info(f"输出：{out_path}")

    async with httpx.AsyncClient(timeout=120.0) as client:
        with open(out_path, "w", encoding="utf-8") as out_file:
            for config_name in selected_configs:
                config = BENCH_CONFIGS[config_name]
                await run_config(config_name, config, questions, args.model, out_file, client)

    # 更新 symlink
    if latest_link.is_symlink() or latest_link.exists():
        latest_link.unlink()
    latest_link.symlink_to(out_path.name)

    elapsed = time.monotonic() - t_start
    logger.info(f"\n完成！耗时 {elapsed:.1f}s，结果 → {out_path}")
    logger.info(f"下一步：python scripts/score_memory_bench.py")


if __name__ == "__main__":
    asyncio.run(main())
