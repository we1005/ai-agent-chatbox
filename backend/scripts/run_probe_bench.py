"""Probe-based Context Engine 评测 Runner（方案 A）。

读取 probe_scenarios.py 的对话脚本，对每个 config × scenario 跑：
  1. 创建空会话
  2. 回放 22-27 turn 历史消息
  3. 发送 probe 问题，记录回答 + latency + 上下文规模
  4. 写 JSONL

用法：
  # smoke：baseline_off 跑 1 个场景
  python scripts/run_probe_bench.py --config baseline_off --scenarios trip_pivot

  # 全部 4 配置 × 6 场景
  python scripts/run_probe_bench.py --config all

输出：
  tests/eval-data/results/probe_run_<timestamp>.jsonl
  tests/eval-data/results/probe_latest.jsonl  (symlink)
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

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parents[1]
BACKEND_ROOT = SCRIPT_DIR.parent
sys.path.insert(0, str(BACKEND_ROOT))

from scripts.bench_utils import (  # noqa: E402
    BASE_URL,
    BENCH_CONFIGS,
    create_bench_conversation,
    replay_session,
    set_context_engine_config,
    sse_chat_memory,
    wait_for_reflection,
)
from scripts.probe_scenarios import SCENARIOS  # noqa: E402

RESULTS_DIR = PROJECT_ROOT / "tests" / "eval-data" / "results"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-7s %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


async def fetch_context_stats(client: httpx.AsyncClient, conv_id: str) -> dict:
    """读取 context-view 用作上下文规模代理。

    Returns:
      {
        "events_total": 全部事件数（含 summary）,
        "summary_present": condenser 是否产出了 rolling_summary,
        "summary_chars": summary 内容长度（0 表示无）,
        "summary_covered": summary 覆盖了多少 events（None 若无）,
        "memory_hits": Mem0 检索命中数,
      }
    """
    try:
        resp = await client.get(
            f"{BASE_URL}/api/conversations/{conv_id}/context-view", timeout=10.0,
        )
        if not resp.is_success:
            return {"error": f"HTTP {resp.status_code}"}
        data = resp.json()
        rs = data.get("rolling_summary") or {}
        return {
            "events_total": data.get("events_total", 0),
            "summary_present": rs is not None and rs.get("content") is not None,
            "summary_chars": len(rs.get("content") or "") if rs else 0,
            "summary_covered": rs.get("covered_event_count") if rs else None,
            "memory_hits": len(data.get("memory_hits") or []),
        }
    except Exception as e:
        return {"error": str(e)}


async def fetch_conversation_chars(client: httpx.AsyncClient, conv_id: str) -> int:
    """统计会话所有 message 的内容字符总数（baseline_off 的 prompt 大小代理）。"""
    try:
        resp = await client.get(f"{BASE_URL}/api/conversations/{conv_id}", timeout=15.0)
        if not resp.is_success:
            return -1
        data = resp.json()
        msgs = data.get("messages") or []
        return sum(len(m.get("content") or "") for m in msgs)
    except Exception:
        return -1


async def run_scenario(
    client: httpx.AsyncClient,
    config_name: str,
    config: dict,
    scenario: dict,
    model: str,
    out_file,
    index: int,
    total: int,
) -> bool:
    """跑单个 scenario，写一行 JSONL。返回是否成功（无 fatal 错误）。"""
    sid = scenario["id"]
    probe_type = scenario["probe_type"]
    turns = scenario["turns"]
    probe_q = scenario["probe_question"]

    logger.info(f"[{index}/{total}] config={config_name} scenario={sid} type={probe_type}")
    logger.info(f"  Probe: {probe_q[:80]}")

    # 1. 建会话
    try:
        conv_id = await create_bench_conversation(
            client, title=f"probe_{config_name}_{sid}"
        )
    except Exception as e:
        logger.error(f"  create_conversation failed: {e}")
        _write_row(out_file, config_name, sid, probe_type, scenario, "", 0, str(e), {})
        return False

    # 2. 回放 history
    logger.info(f"  Replay {len(turns)} turns ...")
    await replay_session(client, conv_id, turns, delay=0.05)

    # 3. （可选）等待 Mem0 反思
    if config["memory_reflect"]:
        ok = await wait_for_reflection(client, conv_id, timeout=20.0)
        logger.info(f"  reflection stable: {ok}")

    # 4. probe 前的上下文统计（写入 events 总数，summary 是否已存在）
    pre_stats = await fetch_context_stats(client, conv_id)
    pre_chars = await fetch_conversation_chars(client, conv_id)

    # 5. 发 probe，收答案
    result = await sse_chat_memory(client, conv_id, probe_q, model=model)
    answer = result["answer"]
    latency_ms = result["latency_ms"]
    error = result["error"]

    # 6. probe 之后 fetch 一次 stats（condenser 跑完后 summary event 应已写回 Mongo）
    post_stats = await fetch_context_stats(client, conv_id)
    post_chars = await fetch_conversation_chars(client, conv_id)

    logger.info(f"  A: {answer[:100]!r}  latency={latency_ms}ms  error={error}")
    logger.info(
        f"  events: pre={pre_stats.get('events_total')} → post={post_stats.get('events_total')}, "
        f"summary={post_stats.get('summary_present')} (covers={post_stats.get('summary_covered')}, "
        f"{post_stats.get('summary_chars')}c), msg_chars={post_chars}"
    )

    _write_row(
        out_file, config_name, sid, probe_type, scenario, answer, latency_ms, error,
        {"pre": pre_stats, "post": post_stats, "pre_chars": pre_chars, "post_chars": post_chars},
    )
    return error is None


def _write_row(
    out_file,
    config: str,
    scenario_id: str,
    probe_type: str,
    scenario: dict,
    answer: str,
    latency_ms: int,
    error: str | None,
    stats: dict,
) -> None:
    row = {
        "config": config,
        "scenario_id": scenario_id,
        "probe_type": probe_type,
        "topic": scenario.get("topic", ""),
        "probe_question": scenario["probe_question"],
        "rubric_desc": scenario.get("rubric_desc", ""),
        "must_mention": scenario.get("must_mention", []) or scenario.get("must_mention_one_of", []),
        "must_not_mention": (
            scenario.get("must_not_mention_as_choice", [])
            or scenario.get("must_not_mention_as_recommendation", [])
            or scenario.get("must_not_mention_as_endorsement", [])
            or scenario.get("must_not_mention_as_ingredient", [])
            or scenario.get("must_not_mention_as_total", [])
        ),
        "answer": answer,
        "latency_ms": latency_ms,
        "error": str(error) if error else None,
        "stats": stats,
        "ts": datetime.now(timezone.utc).isoformat(),
    }
    out_file.write(json.dumps(row, ensure_ascii=False) + "\n")
    out_file.flush()


async def run_config(
    client: httpx.AsyncClient,
    config_name: str,
    config: dict,
    scenarios: list[dict],
    model: str,
    out_file,
) -> int:
    logger.info(f"\n{'='*60}")
    logger.info(f"Config: {config_name} — {config['label']}")
    logger.info(f"Scenarios: {len(scenarios)}  Model: {model}")
    logger.info(f"{'='*60}")

    await set_context_engine_config(
        client,
        context_engine=config["context_engine"],
        memory_reflect=config["memory_reflect"],
        memory_retrieval=config["memory_retrieval"],
    )

    success = 0
    for i, sc in enumerate(scenarios, 1):
        ok = await run_scenario(client, config_name, config, sc, model, out_file, i, len(scenarios))
        if ok:
            success += 1
    logger.info(f"Config {config_name} done: {success}/{len(scenarios)}")
    return success


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--config", type=str, default="all",
        help=f"配置名或 'all'。可选: {','.join(BENCH_CONFIGS.keys())}",
    )
    parser.add_argument(
        "--scenarios", type=str, default="all",
        help="逗号分隔的 scenario id 或 'all'",
    )
    parser.add_argument("--model", type=str, default="qwen3.5-flash", help="被测模型")
    args = parser.parse_args()

    # 选 config
    if args.config == "all":
        configs = list(BENCH_CONFIGS.keys())
    elif args.config in BENCH_CONFIGS:
        configs = [args.config]
    else:
        logger.error(f"未知 config: {args.config}（可选 {list(BENCH_CONFIGS.keys())}）")
        sys.exit(1)

    # 选 scenarios
    if args.scenarios == "all":
        scenarios = SCENARIOS
    else:
        wanted = {s.strip() for s in args.scenarios.split(",")}
        scenarios = [s for s in SCENARIOS if s["id"] in wanted]
        if not scenarios:
            logger.error(f"未匹配到 scenario: {args.scenarios}")
            sys.exit(1)

    logger.info(f"加载 {len(scenarios)} 个 scenarios")
    for s in scenarios:
        logger.info(f"  {s['id']}: {s['probe_type']} ({len(s['turns'])} turns)")

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    out_path = RESULTS_DIR / f"probe_run_{ts}.jsonl"

    t0 = time.monotonic()
    async with httpx.AsyncClient(timeout=120.0) as client:
        with open(out_path, "w", encoding="utf-8") as out_file:
            for cfg_name in configs:
                await run_config(
                    client, cfg_name, BENCH_CONFIGS[cfg_name],
                    scenarios, args.model, out_file,
                )

    elapsed = time.monotonic() - t0

    # symlink: probe_latest.jsonl
    latest_link = RESULTS_DIR / "probe_latest.jsonl"
    if latest_link.exists() or latest_link.is_symlink():
        latest_link.unlink()
    latest_link.symlink_to(out_path.name)

    logger.info(f"\n完成！耗时 {elapsed:.1f}s，结果 → {out_path}")
    logger.info("下一步：python scripts/score_probe_bench.py")


if __name__ == "__main__":
    asyncio.run(main())
