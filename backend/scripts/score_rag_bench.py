"""
读 run_rag_bench.py 产出的 JSONL，算 Recall@K + RAGAS（DeepSeek judge）指标。

用法：
  # 默认取 tests/eval-data/results/latest.jsonl
  venv/bin/python scripts/score_rag_bench.py

  # 指定 run 文件 / 跳过 RAGAS（只算 Recall）
  venv/bin/python scripts/score_rag_bench.py --run results/run_20260422_153000.jsonl --skip-ragas

输出：
  tests/eval-data/results/report_<ts>.md   # 汇总表 + 分类下钻

成本防护：
  - RAGAS judge 用 DeepSeek-chat（不是 reasoner）
  - 每次 trial 算 faithfulness + answer_correctness 两个指标
  - 可 --skip-ragas 先看客观指标

详见 plan-doc-dir/RAG评测集落地规划.md。
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from statistics import mean

ROOT = Path(__file__).resolve().parents[2]
RESULTS_DIR = ROOT / "tests" / "eval-data" / "results"


# ── Recall@K ───────────────────────────────────────────────────────


def _normalize_source(s: str) -> str:
    """crud-0001.txt → crud-0001，其它保持不变。"""
    if s.endswith(".txt"):
        return s[:-4]
    return s


def recall_at_k(row: dict) -> float | None:
    gold = set(row.get("gold_doc_ids") or [])
    if not gold:
        return None  # kb_absent：没有 gold，Recall 无意义
    retrieved = {_normalize_source(r.get("source", "")) for r in (row.get("retrieved_refs") or [])}
    # graph_rag 降级时可能没有有效 source；视为 recall=0
    if not retrieved or all(s.startswith("graph_rag:") for s in retrieved):
        # LightRAG 只能解析 source 时才有意义；解析失败标记为 None（排除统计）
        if all(s.startswith("graph_rag:") for s in retrieved):
            return None
        return 0.0
    hit = len(gold & retrieved)
    return hit / len(gold)


# ── RAGAS ──────────────────────────────────────────────────────────


def _build_ragas_llm_and_embeddings():
    """用 DeepSeek-chat 作 judge，BGE-M3 作 embedding。

    RAGAS 0.2+ 接受 LangChain 风格的 BaseChatModel / Embeddings。
    """
    from langchain_openai import ChatOpenAI
    from ragas.llms import LangchainLLMWrapper
    from ragas.embeddings import LangchainEmbeddingsWrapper

    api_key = os.environ.get("DEEPSEEK_API_KEY") or _read_env_key("DEEPSEEK_API_KEY")
    if not api_key:
        raise RuntimeError("DEEPSEEK_API_KEY 未设置（backend/.env 或环境变量）")

    llm = ChatOpenAI(
        model="deepseek-chat",
        openai_api_key=api_key,
        openai_api_base="https://api.deepseek.com/v1",
        temperature=0.0,
        timeout=60,
    )
    ragas_llm = LangchainLLMWrapper(llm)

    # Embedding：复用 BGE-M3（本地已加载）
    from langchain_huggingface import HuggingFaceEmbeddings
    backend_dir = ROOT / "backend"
    local_path = backend_dir / "data" / "models" / "bge-m3"
    if not local_path.exists():
        raise RuntimeError(f"BGE-M3 未下载到 {local_path}；先在 /knowledge 激活模型")
    emb = HuggingFaceEmbeddings(model_name=str(local_path))
    ragas_emb = LangchainEmbeddingsWrapper(emb)
    return ragas_llm, ragas_emb


def _read_env_key(name: str) -> str:
    env_file = ROOT / "backend" / ".env"
    if not env_file.exists():
        return ""
    for line in env_file.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line.startswith(f"{name}="):
            return line.split("=", 1)[1].strip().strip('"').strip("'")
    return ""


def score_ragas(rows: list[dict]) -> list[dict]:
    """在原 rows 上附加 `ragas_faithfulness` / `ragas_answer_correctness` 两字段。
    失败 / 无 refs 的 row 赋 None。"""
    from ragas import evaluate
    from ragas.metrics import faithfulness, answer_correctness
    from datasets import Dataset

    llm, emb = _build_ragas_llm_and_embeddings()

    # 准备数据集：user_input / response / reference / retrieved_contexts
    records: list[dict] = []
    idx_map: list[int] = []  # records[i] 对应 rows[idx_map[i]]
    for i, r in enumerate(rows):
        if r.get("error") or not r.get("answer"):
            continue
        contexts = [ref.get("snippet", "") for ref in (r.get("retrieved_refs") or []) if ref.get("snippet")]
        if not contexts:
            # Graph RAG 降级 / 未取到 refs：给个空占位，RAGAS 会算出低分
            contexts = [""]
        records.append({
            "user_input": r["query"],
            "response": r["answer"],
            "reference": r.get("gold_answer", ""),
            "retrieved_contexts": contexts,
        })
        idx_map.append(i)

    if not records:
        print("[score] no usable rows for RAGAS; skipping")
        return rows

    ds = Dataset.from_list(records)
    print(f"[score] running RAGAS on {len(records)} trials (DeepSeek judge)...")
    result = evaluate(
        ds, metrics=[faithfulness, answer_correctness],
        llm=llm, embeddings=emb, raise_exceptions=False,
    )
    df = result.to_pandas()

    for j, row_i in enumerate(idx_map):
        rows[row_i]["ragas_faithfulness"] = _safe_float(df.iloc[j].get("faithfulness"))
        rows[row_i]["ragas_answer_correctness"] = _safe_float(df.iloc[j].get("answer_correctness"))
    return rows


def _safe_float(v) -> float | None:
    try:
        f = float(v)
        if f != f:  # NaN
            return None
        return f
    except (TypeError, ValueError):
        return None


# ── 汇总表 ─────────────────────────────────────────────────────────


def _avg(vals: list[float | None]) -> float | None:
    clean = [v for v in vals if v is not None]
    return mean(clean) if clean else None


def _fmt(v: float | None, digits: int = 3) -> str:
    return f"{v:.{digits}f}" if v is not None else "—"


def aggregate(rows: list[dict]) -> tuple[list[dict], dict[str, list[dict]]]:
    """返回 (overall_rows, per_category[cat] -> rows)。每行一个 config。"""
    by_cfg: dict[str, list[dict]] = defaultdict(list)
    for r in rows:
        by_cfg[r["config"]].append(r)

    overall = []
    for cfg, rs in by_cfg.items():
        overall.append({
            "config": cfg,
            "n": len(rs),
            "errors": sum(1 for r in rs if r.get("error")),
            "recall_at_k": _avg([recall_at_k(r) for r in rs]),
            "faithfulness": _avg([r.get("ragas_faithfulness") for r in rs]),
            "correctness": _avg([r.get("ragas_answer_correctness") for r in rs]),
            "latency_ms": _avg([r.get("latency_ms") for r in rs]),
        })
    overall.sort(key=lambda x: list(_CFG_ORDER.get(x["config"], (99,)))[0])

    per_cat: dict[str, list[dict]] = {}
    cats = sorted({r["category"] for r in rows})
    for cat in cats:
        cat_rows = [r for r in rows if r["category"] == cat]
        agg_by_cfg: dict[str, list[dict]] = defaultdict(list)
        for r in cat_rows:
            agg_by_cfg[r["config"]].append(r)
        bucket = []
        for cfg, rs in agg_by_cfg.items():
            bucket.append({
                "config": cfg,
                "n": len(rs),
                "recall_at_k": _avg([recall_at_k(r) for r in rs]),
                "faithfulness": _avg([r.get("ragas_faithfulness") for r in rs]),
                "correctness": _avg([r.get("ragas_answer_correctness") for r in rs]),
            })
        bucket.sort(key=lambda x: list(_CFG_ORDER.get(x["config"], (99,)))[0])
        per_cat[cat] = bucket
    return overall, per_cat


_CFG_ORDER = {k: (i,) for i, k in enumerate([
    "off", "multi_query",
    "agentic_grading", "agentic_rewrite", "agentic_full",
    "graph_naive", "graph_local", "graph_global", "graph_hybrid", "graph_mix",
])}


def _render_overall_table(rows: list[dict]) -> str:
    out = ["| 配置 | n | Recall@K | Faithfulness | Correctness | 平均延迟 | 错误 |",
           "|---|---|---|---|---|---|---|"]
    for r in rows:
        out.append(
            f"| `{r['config']}` | {r['n']} | {_fmt(r['recall_at_k'])} | "
            f"{_fmt(r['faithfulness'])} | {_fmt(r['correctness'])} | "
            f"{_fmt((r['latency_ms'] or 0)/1000, 2)}s | {r['errors']} |"
        )
    return "\n".join(out)


def _render_category_table(rows: list[dict]) -> str:
    out = ["| 配置 | n | Recall@K | Faithfulness | Correctness |",
           "|---|---|---|---|---|"]
    for r in rows:
        out.append(
            f"| `{r['config']}` | {r['n']} | {_fmt(r['recall_at_k'])} | "
            f"{_fmt(r['faithfulness'])} | {_fmt(r['correctness'])} |"
        )
    return "\n".join(out)


def render_report(overall, per_cat, run_path: Path) -> str:
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    md = [
        f"# RAG 策略对比报告",
        f"",
        f"- 数据源：`{run_path.name}`",
        f"- 生成时间：{ts}",
        f"- 评测集：CRUD-RAG mini（60 query × {len(overall)} 策略）",
        f"- Judge：DeepSeek-chat（faithfulness / answer_correctness）",
        f"- 注：`Recall@K` 对 `kb_absent` 类别不适用；Graph RAG 的 refs 若未解析到真实 file_path 会被计为 None（从均值中剔除）",
        f"",
        f"## 汇总（全量）",
        f"",
        _render_overall_table(overall),
        f"",
    ]
    for cat, rows in per_cat.items():
        md += [
            f"## 分类下钻 · `{cat}`（n={rows[0]['n'] if rows else 0}）",
            "",
            _render_category_table(rows),
            "",
        ]
    return "\n".join(md)


# ── main ──────────────────────────────────────────────────────────


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", default=None,
                    help="指定 run JSONL；默认用 results/latest.jsonl")
    ap.add_argument("--skip-ragas", action="store_true",
                    help="跳过 RAGAS（只算 Recall@K + latency）")
    args = ap.parse_args()

    run_path = Path(args.run) if args.run else (RESULTS_DIR / "latest.jsonl")
    if not run_path.is_absolute():
        run_path = (RESULTS_DIR / run_path.name).resolve()
    if not run_path.exists():
        print(f"! run file not found: {run_path}")
        return 1

    with open(run_path, encoding="utf-8") as f:
        rows = [json.loads(line) for line in f if line.strip()]
    print(f"[score] loaded {len(rows)} trials from {run_path.name}")

    if not args.skip_ragas:
        rows = score_ragas(rows)

    overall, per_cat = aggregate(rows)

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_path = RESULTS_DIR / f"report_{ts}.md"
    report_path.write_text(render_report(overall, per_cat, run_path), encoding="utf-8")
    print(f"[score] wrote report → {report_path}")

    # 同时把带 ragas 分的明细存回 JSONL（供二次分析）
    scored_path = RESULTS_DIR / f"scored_{ts}.jsonl"
    with open(scored_path, "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(f"[score] wrote scored detail → {scored_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
