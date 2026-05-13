"""Probe Benchmark Scorer。

读 run_probe_bench.py 的 JSONL，用 qwen3.5-flash 做 rubric judge，
生成 markdown 报告。

用法：
    python scripts/score_probe_bench.py                    # 用 probe_latest.jsonl
    python scripts/score_probe_bench.py --run <path>       # 指定文件

输出：
    RAG评测/memory-报告/probe-YYYY-MM-DD.md
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

import httpx

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parents[1]
BACKEND_ROOT = SCRIPT_DIR.parent

RESULTS_DIR = PROJECT_ROOT / "tests" / "eval-data" / "results"
REPORT_DIR = PROJECT_ROOT / "RAG评测" / "memory-报告"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-7s %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


_JUDGE_SYSTEM = (
    "You are a rigorous evaluator. Given a probe question, a rubric describing "
    "the expected behavior, and an assistant response, decide if the response "
    "correctly satisfies the rubric. Output exactly two lines:\n"
    "SCORE: 1  (correct)\n"
    "SCORE: 0  (incorrect)\n"
    "REASON: <one sentence>"
)


_JUDGE_USER_TMPL = """\
Probe question: {question}

Rubric (the criterion for correct behavior):
{rubric_desc}

Expected to mention (the response should reference at least one of these as the recommendation):
{must_mention}

The response should NOT recommend or endorse these (these were ruled out earlier in the conversation):
{must_not_mention}

Assistant response:
\"\"\"
{response}
\"\"\"

Did the response correctly satisfy the rubric? Output SCORE and REASON."""


def _read_env_key(name: str) -> str:
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


async def judge_one(
    client: httpx.AsyncClient,
    row: dict,
    *,
    model: str,
    api_key: str,
    base_url: str,
    sem: asyncio.Semaphore,
) -> tuple[int | None, str]:
    """返回 (score, reason)。score in {0, 1, None=失败}。"""
    if row.get("error"):
        return (0, f"bench error: {row['error']}")

    prompt = _JUDGE_USER_TMPL.format(
        question=row["probe_question"],
        rubric_desc=row.get("rubric_desc", "-"),
        must_mention=", ".join(row.get("must_mention") or []) or "(any)",
        must_not_mention=", ".join(row.get("must_not_mention") or []) or "(none)",
        response=row.get("answer", "") or "(empty)",
    )
    async with sem:
        text = None
        last_err: Exception | None = None
        # 重试 3 次（Qwen flash judge 偶尔 ReadTimeout）
        for attempt in range(3):
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
                        "max_tokens": 80,
                    },
                    timeout=60.0,
                )
                resp.raise_for_status()
                text = resp.json()["choices"][0]["message"]["content"].strip()
                break
            except Exception as e:
                last_err = e
                logger.warning(f"[judge] attempt {attempt+1}/3 {type(e).__name__}: {e}")
                if attempt < 2:
                    await asyncio.sleep(2.0)
        if text is None:
            return (None, f"judge call failed after 3 retries: {type(last_err).__name__}: {last_err}")

    # 解析
    score = None
    reason = ""
    for line in text.splitlines():
        line = line.strip()
        if line.upper().startswith("SCORE:"):
            v = line.split(":", 1)[1].strip()
            if v.startswith("1"):
                score = 1
            elif v.startswith("0"):
                score = 0
        elif line.upper().startswith("REASON:"):
            reason = line.split(":", 1)[1].strip()
    if not reason:
        reason = text.replace("\n", " ")[:120]
    return (score, reason)


async def score_rows(rows: list[dict]) -> list[dict]:
    api_key = _read_env_key("UTILITY_LLM_API_KEY") or _read_env_key("DASHSCOPE_API_KEY")
    base_url = (
        _read_env_key("UTILITY_LLM_BASE_URL")
        or "https://dashscope.aliyuncs.com/compatible-mode/v1"
    ).rstrip("/")
    model = _read_env_key("UTILITY_LLM_MODEL") or "qwen3.5-flash"

    if not api_key:
        logger.error("缺少 UTILITY_LLM_API_KEY / DASHSCOPE_API_KEY")
        for r in rows:
            r["judged"] = None
            r["reason"] = "no api key"
        return rows

    logger.info(f"[judge] {model} @ {base_url}, {len(rows)} rows")
    sem = asyncio.Semaphore(3)
    async with httpx.AsyncClient(timeout=30.0) as client:
        results = await asyncio.gather(*[
            judge_one(client, r, model=model, api_key=api_key, base_url=base_url, sem=sem)
            for r in rows
        ])
    for r, (score, reason) in zip(rows, results):
        r["judged"] = score
        r["reason"] = reason
    judged = sum(1 for r in rows if r["judged"] is not None)
    correct = sum(1 for r in rows if r["judged"] == 1)
    logger.info(f"[judge] done {judged}/{len(rows)}, correct={correct}")
    return rows


def aggregate(rows: list[dict]) -> dict:
    """按 config 维度统计。"""
    stats: dict = defaultdict(lambda: {
        "n": 0, "correct": 0, "errors": 0, "judge_failed": 0,
        "lat_sum": 0, "msg_chars_sum": 0, "summary_fired": 0, "summary_covered_sum": 0,
    })
    by_probe: dict = defaultdict(lambda: defaultdict(lambda: {"n": 0, "correct": 0}))

    for r in rows:
        cfg = r["config"]
        s = stats[cfg]
        s["n"] += 1
        if r.get("error"):
            s["errors"] += 1
        if r.get("judged") is None:
            s["judge_failed"] += 1
        elif r.get("judged") == 1:
            s["correct"] += 1
        s["lat_sum"] += r.get("latency_ms", 0)
        post = (r.get("stats") or {}).get("post") or {}
        s["msg_chars_sum"] += r.get("stats", {}).get("post_chars", 0) or 0
        if post.get("summary_present"):
            s["summary_fired"] += 1
            s["summary_covered_sum"] += post.get("summary_covered") or 0

        # 按 probe_type
        bp = by_probe[r["probe_type"]][cfg]
        bp["n"] += 1
        if r.get("judged") == 1:
            bp["correct"] += 1
    return {"by_config": dict(stats), "by_probe": {k: dict(v) for k, v in by_probe.items()}}


def render_report(rows: list[dict], agg: dict, run_path: Path) -> str:
    by_cfg = agg["by_config"]
    by_probe = agg["by_probe"]
    configs = list(by_cfg.keys())
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    lines: list[str] = [
        "# Probe Benchmark · Context Engine 评测报告（方案 A）",
        "",
        f"- **日期**：{ts}",
        f"- **数据源**：`{run_path.name}`",
        f"- **总样本**：{len(rows)} 条",
        f"- **被测模型**：qwen3.5-flash  **Judge 模型**：qwen3.5-flash",
        f"- **方案**：自建 6 场景 × {len(configs)} 配置（plan-doc-dir/Context-Engine评测方法论.md §三方案A）",
        "",
        "---",
        "",
        "## 汇总（按配置）",
        "",
        "| 配置 | n | 准确率 | 平均延迟 | 历史字符 | Condenser 触发率 | 摘要平均覆盖 |",
        "|---|---|---|---|---|---|---|",
    ]
    for cfg in configs:
        s = by_cfg[cfg]
        n = s["n"]
        acc = f"{s['correct'] / n * 100:.1f}% ({s['correct']}/{n})" if n else "—"
        avg_lat = f"{s['lat_sum'] // max(n, 1)}ms"
        avg_chars = f"{s['msg_chars_sum'] // max(n, 1)}c"
        fired_rate = f"{s['summary_fired']}/{n}"
        avg_covered = (
            f"{s['summary_covered_sum'] / max(s['summary_fired'], 1):.1f} events"
            if s["summary_fired"] else "—"
        )
        lines.append(f"| `{cfg}` | {n} | {acc} | {avg_lat} | {avg_chars} | {fired_rate} | {avg_covered} |")

    lines += ["", "---", "", "## 按 probe 类型", "", "| Probe 类型 | " + " | ".join(f"`{c}`" for c in configs) + " |"]
    lines.append("|---|" + "|".join(["---"] * len(configs)) + "|")
    for probe, ent in by_probe.items():
        cells = []
        for cfg in configs:
            sub = ent.get(cfg, {"n": 0, "correct": 0})
            if sub["n"] == 0:
                cells.append("—")
            else:
                cells.append(f"{sub['correct']}/{sub['n']}")
        lines.append(f"| {probe} | " + " | ".join(cells) + " |")

    lines += [
        "",
        "---",
        "",
        "## 每条结果",
        "",
        "| Scenario | Probe | " + " | ".join(f"`{c}`" for c in configs) + " |",
        "|---|---|" + "|".join(["---"] * len(configs)) + "|",
    ]
    # 按 scenario_id × config 网格
    by_scn: dict = defaultdict(dict)
    for r in rows:
        by_scn[r["scenario_id"]][r["config"]] = r
    scenarios_sorted = sorted(by_scn.keys())
    for sid in scenarios_sorted:
        first_r = next(iter(by_scn[sid].values()))
        probe = first_r["probe_type"]
        cells = []
        for cfg in configs:
            r = by_scn[sid].get(cfg)
            if r is None:
                cells.append("—")
            elif r.get("judged") == 1:
                cells.append("✅")
            elif r.get("judged") == 0:
                cells.append("❌")
            else:
                cells.append("⚠️")
        lines.append(f"| `{sid}` | {probe} | " + " | ".join(cells) + " |")

    lines += [
        "",
        "---",
        "",
        "## 抽样 judge 理由（baseline_off vs full 失败 / 不一致项）",
        "",
    ]
    interesting = [r for r in rows if r.get("judged") == 0][:8]
    for r in interesting:
        lines += [
            f"### `{r['config']}` × `{r['scenario_id']}` ({r['probe_type']})",
            f"- **Probe**: {r['probe_question']}",
            f"- **Answer**: {(r.get('answer') or '')[:200]!r}",
            f"- **Reason**: {r.get('reason', '-')}",
            "",
        ]

    lines += [
        "---",
        "",
        "> 生成工具：`scripts/score_probe_bench.py`",
        "> 评测方法论：`plan-doc-dir/Context-Engine评测方法论.md`",
    ]
    return "\n".join(lines)


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run", type=str, default=None)
    args = parser.parse_args()

    run_path = Path(args.run) if args.run else (RESULTS_DIR / "probe_latest.jsonl")
    if not run_path.exists():
        logger.error(f"找不到 run 文件：{run_path}")
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

    rows = await score_rows(rows)
    agg = aggregate(rows)

    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    report_path = REPORT_DIR / f"probe-{date_str}.md"
    report_text = render_report(rows, agg, run_path)
    report_path.write_text(report_text, encoding="utf-8")

    logger.info(f"报告 → {report_path}")
    print(f"\n{'='*60}")
    print(report_text[:1200])
    if len(report_text) > 1200:
        print("... (截断)")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
