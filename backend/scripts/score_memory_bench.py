"""LongMemEval-S Memory Benchmark Scorer。

读取 run_memory_bench.py 产生的 JSONL，用 qwen3.5-flash 做二元对错 judge，
按 5 项记忆能力分类输出 markdown 报告。

用法：
    python scripts/score_memory_bench.py                   # 用 memory_latest.jsonl
    python scripts/score_memory_bench.py --run <path>      # 指定文件
    python scripts/score_memory_bench.py --skip-judge      # 只汇总，不调 LLM

输出：
    RAG评测/memory-报告/smoke-YYYY-MM-DD.md  或  oracle-YYYY-MM-DD.md
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import httpx

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parents[1]
BACKEND_ROOT = SCRIPT_DIR.parent
sys.path.insert(0, str(BACKEND_ROOT))

RESULTS_DIR = PROJECT_ROOT / "tests" / "eval-data" / "results"
REPORT_DIR = PROJECT_ROOT / "RAG评测" / "memory-报告"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-7s %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

# ── 能力分类映射 ──────────────────────────────────────────────────────────
CATEGORY_MAP: dict[str, str] = {
    # 真实数据集用连字符
    "single-session-user": "信息抽取（单 session）",
    "single-session-assistant": "信息抽取（单 session）",
    "single-session-preference": "信息抽取（单 session）",
    "multi-session": "跨 session 推理",
    "temporal-reasoning": "时间推理",
    "knowledge-update": "知识更新",
    "open-domain-ab": "弃权 / 偏好",
    # 合成 smoke 数据用下划线（兼容）
    "single_session_user": "信息抽取（单 session）",
    "single_session_assistant": "信息抽取（单 session）",
    "single_session_preference": "信息抽取（单 session）",
    "multi_session": "跨 session 推理",
    "temporal_reasoning": "时间推理",
    "knowledge_update": "知识更新",
    "open_domain_ab": "弃权 / 偏好",
}

# ── Judge prompt（参考 LongMemEval 官方 auto_eval.py）─────────────────────
_JUDGE_SYSTEM = (
    "You are a strict but fair evaluator. Given a question, a gold answer, and "
    "a system response, determine if the system response correctly answers the question. "
    "Answer ONLY 'yes' or 'no'."
)

_JUDGE_USER_TMPL = """\
Question: {question}
Gold Answer: {gold_answer}
System Response: {response}
Is the system response correct? Answer 'yes' or 'no'."""


def _read_env_key(name: str) -> str:
    """从进程环境或 .env 文件读 API key。"""
    val = os.environ.get(name, "")
    if val:
        return val
    env_path = BACKEND_ROOT / ".env"
    if env_path.exists():
        for line in env_path.read_text().splitlines():
            line = line.strip()
            if line.startswith(f"{name}="):
                return line.split("=", 1)[1].strip()
    return ""


def _get_judge_client() -> httpx.AsyncClient:
    return httpx.AsyncClient(timeout=30.0)


async def judge_one(
    client: httpx.AsyncClient,
    question: str,
    gold_answer: str,
    response: str,
    model: str,
    api_key: str,
    base_url: str,
    sem: asyncio.Semaphore,
) -> bool | None:
    """调用 LLM judge，返回 True=正确 / False=错误 / None=调用失败。"""
    prompt = _JUDGE_USER_TMPL.format(
        question=question, gold_answer=gold_answer, response=response
    )
    async with sem:
        try:
            resp = await client.post(
                f"{base_url}/chat/completions",
                headers={"Authorization": f"Bearer {api_key}"},
                json={
                    "model": model,
                    "messages": [
                        {"role": "system", "content": _JUDGE_SYSTEM},
                        {"role": "user", "content": prompt},
                    ],
                    "temperature": 0.0,
                    "max_tokens": 5,
                },
                timeout=30.0,
            )
            resp.raise_for_status()
            text = resp.json()["choices"][0]["message"]["content"].strip().lower()
            return text.startswith("yes")
        except Exception as e:
            logger.warning(f"[judge] error: {e}")
            return None


async def score_rows(rows: list[dict], skip_judge: bool) -> list[dict]:
    """为所有 rows 添加 correct 字段。"""
    if skip_judge:
        for r in rows:
            r["correct"] = None
        return rows

    # 读 utility LLM 配置（默认用 Qwen，与 bench runner 一致）
    utility_key = _read_env_key("UTILITY_LLM_API_KEY") or _read_env_key("DASHSCOPE_API_KEY")
    utility_base = _read_env_key("UTILITY_LLM_BASE_URL") or "https://dashscope.aliyuncs.com/compatible-mode/v1"
    utility_model = _read_env_key("UTILITY_LLM_MODEL") or "qwen3.5-flash"

    if not utility_key:
        logger.error("未找到 UTILITY_LLM_API_KEY 或 DASHSCOPE_API_KEY，无法调 judge")
        for r in rows:
            r["correct"] = None
        return rows

    logger.info(f"[judge] 模型: {utility_model}  base_url: {utility_base}")
    sem = asyncio.Semaphore(3)  # 并发限制，避免撞 RPM

    async with _get_judge_client() as client:
        tasks = [
            judge_one(
                client,
                r["question"], r["gold_answer"], r.get("answer", ""),
                model=utility_model,
                api_key=utility_key,
                base_url=utility_base.rstrip("/"),
                sem=sem,
            )
            for r in rows
        ]
        results = await asyncio.gather(*tasks)

    for r, correct in zip(rows, results):
        r["correct"] = correct

    judged = sum(1 for r in rows if r["correct"] is not None)
    yes = sum(1 for r in rows if r["correct"] is True)
    logger.info(f"[judge] 完成 {judged}/{len(rows)}，正确 {yes}")
    return rows


def aggregate(rows: list[dict]) -> dict:
    """按 config × question_type 统计 accuracy。"""
    from collections import defaultdict

    stats: dict = defaultdict(lambda: {"n": 0, "correct": 0, "latency_sum": 0, "errors": 0})

    for r in rows:
        cfg = r["config"]
        qt = r["question_type"]
        key_total = (cfg, "__total__")
        key_cat = (cfg, qt)

        for k in (key_total, key_cat):
            stats[k]["n"] += 1
            if r.get("error"):
                stats[k]["errors"] += 1
            if r.get("correct") is True:
                stats[k]["correct"] += 1
            stats[k]["latency_sum"] += r.get("latency_ms", 0)

    return dict(stats)


def _acc(s: dict) -> str:
    if s["n"] == 0:
        return "—"
    pct = s["correct"] / s["n"] * 100
    return f"{pct:.1f}%  ({s['correct']}/{s['n']})"


def render_report(rows: list[dict], stats: dict, run_path: Path) -> str:
    from collections import defaultdict

    configs = list(dict.fromkeys(r["config"] for r in rows))
    all_types = list(dict.fromkeys(r["question_type"] for r in rows))
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    n_total = len(rows)
    n_judged = sum(1 for r in rows if r.get("correct") is not None)
    judge_model = _read_env_key("UTILITY_LLM_MODEL") or "qwen3.5-flash"

    lines: list[str] = [
        "# Memory Benchmark · LongMemEval-S 评测报告",
        "",
        f"- **日期**：{ts}",
        f"- **数据源**：`{run_path.name}`",
        f"- **总样本**：{n_total} 条  Judge：{n_judged} 条",
        f"- **被测模型**：qwen3.5-flash  **Judge 模型**：{judge_model}",
        f"- **行业参考**：Mem0 官方 LongMemEval = 93.4",
        "",
        "---",
        "",
        "## 汇总（总分）",
        "",
        "| 配置 | n | 准确率 | 平均延迟 | 错误 |",
        "|---|---|---|---|---|",
    ]
    for cfg in configs:
        s = stats.get((cfg, "__total__"), {"n": 0, "correct": 0, "latency_sum": 0, "errors": 0})
        avg_lat = f"{s['latency_sum'] // max(s['n'], 1)}ms"
        lines.append(f"| `{cfg}` | {s['n']} | {_acc(s)} | {avg_lat} | {s['errors']} |")

    lines += [
        "",
        "---",
        "",
        "## 按记忆能力分类",
        "",
    ]

    category_groups: dict = defaultdict(list)
    for qt in all_types:
        cat_label = CATEGORY_MAP.get(qt, qt)
        category_groups[cat_label].append(qt)

    for cat_label, qts in category_groups.items():
        lines += [f"### {cat_label}", "", "| 配置 | n | 准确率 |", "|---|---|---|"]
        for cfg in configs:
            n_cat = sum(stats.get((cfg, qt), {}).get("n", 0) for qt in qts)
            n_correct = sum(stats.get((cfg, qt), {}).get("correct", 0) for qt in qts)
            if n_cat == 0:
                lines.append(f"| `{cfg}` | 0 | — |")
            else:
                pct = n_correct / n_cat * 100
                lines.append(f"| `{cfg}` | {n_cat} | {pct:.1f}%  ({n_correct}/{n_cat}) |")
        lines.append("")

    lines += [
        "---",
        "",
        "> 生成工具：`scripts/score_memory_bench.py`",
        "> 数据集：[LongMemEval · xiaowu0162/longmemeval-cleaned](https://huggingface.co/datasets/xiaowu0162/longmemeval-cleaned)",
    ]
    return "\n".join(lines)


def _report_filename(rows: list[dict]) -> str:
    n = len(rows)
    date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    if n <= 20:
        prefix = "smoke"
    elif n <= 300:
        prefix = "oracle"
    else:
        prefix = "full"
    return f"{prefix}-{date_str}.md"


async def main() -> None:
    parser = argparse.ArgumentParser(description="LongMemEval memory bench scorer")
    parser.add_argument("--run", type=str, default=None, help="指定 JSONL run 文件路径")
    parser.add_argument("--skip-judge", action="store_true", help="跳过 LLM judge，只汇总")
    args = parser.parse_args()

    if args.run:
        run_path = Path(args.run)
    else:
        run_path = RESULTS_DIR / "memory_latest.jsonl"

    if not run_path.exists():
        logger.error(f"找不到 run 文件：{run_path}")
        logger.error("请先运行：python scripts/run_memory_bench.py --config baseline_off --limit 3")
        sys.exit(1)

    rows: list[dict] = []
    with open(run_path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    rows.append(json.loads(line))
                except json.JSONDecodeError:
                    pass

    logger.info(f"加载 {len(rows)} 条 from {run_path.name}")

    rows = await score_rows(rows, skip_judge=args.skip_judge)
    stats = aggregate(rows)

    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    report_name = _report_filename(rows)
    report_path = REPORT_DIR / report_name
    report_text = render_report(rows, stats, run_path)

    with open(report_path, "w", encoding="utf-8") as f:
        f.write(report_text)

    logger.info(f"\n报告 → {report_path}")
    print(f"\n{'='*60}")
    print(report_text[:800])
    if len(report_text) > 800:
        print("... (截断，完整内容见报告文件)")
    print(f"{'='*60}")


if __name__ == "__main__":
    asyncio.run(main())
