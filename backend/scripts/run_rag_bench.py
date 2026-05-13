"""
RAG 策略对比评测 runner。

10 个配置 × 60 条 query → 一条一条打 /api/chat/completions，解析 SSE，
记录 answer / refs / latency 到 JSONL。

成本硬约束：每次请求都显式 `use_web_search=false`，禁止 SerpAPI。
用法：
  # smoke：先跑 5 条 × 2 配置
  venv/bin/python scripts/run_rag_bench.py --max-queries 5 --configs off graph_hybrid

  # 全量（10 配置 × 60）
  venv/bin/python scripts/run_rag_bench.py

输出：
  tests/eval-data/results/run_<YYYYMMDD_HHMMSS>.jsonl
  tests/eval-data/results/latest.jsonl → 软链
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any

import httpx

ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT / "tests" / "eval-data" / "crud-mini"
RESULTS_DIR = ROOT / "tests" / "eval-data" / "results"
API = "http://localhost:8000/api"


# ── 10 个策略配置 ─────────────────────────────────────────────────


CONFIGS: dict[str, dict] = {
    "off":                {"graph_rag": False, "agentic": "off",             "multi_query": False},
    "multi_query":        {"graph_rag": False, "agentic": "off",             "multi_query": True},
    "agentic_grading":    {"graph_rag": False, "agentic": "grading_only",    "multi_query": False},
    "agentic_rewrite":    {"graph_rag": False, "agentic": "grading_rewrite", "multi_query": False},
    "agentic_full":       {"graph_rag": False, "agentic": "full",            "multi_query": False},
    "graph_naive":        {"graph_rag": True,  "agentic": "off",             "multi_query": False, "graph_mode": "naive"},
    "graph_local":        {"graph_rag": True,  "agentic": "off",             "multi_query": False, "graph_mode": "local"},
    "graph_global":       {"graph_rag": True,  "agentic": "off",             "multi_query": False, "graph_mode": "global"},
    "graph_hybrid":       {"graph_rag": True,  "agentic": "off",             "multi_query": False, "graph_mode": "hybrid"},
    "graph_mix":          {"graph_rag": True,  "agentic": "off",             "multi_query": False, "graph_mode": "mix"},
}


async def apply_config(client: httpx.AsyncClient, name: str) -> None:
    cfg = CONFIGS[name]
    # 先关 Graph RAG（若之前开着），避免切其它档时被覆盖
    await client.put(f"{API}/embedding/graph-rag", json={"enabled": False})
    # 切 Agentic + Multi-Query
    await client.put(f"{API}/embedding/agentic-rag", json={"mode": cfg["agentic"]})
    await client.put(f"{API}/embedding/multi-query", json={"enabled": cfg["multi_query"]})
    # 最后切 Graph RAG（启用时覆盖前两者，所以要最后设）
    if cfg["graph_rag"]:
        await client.put(
            f"{API}/embedding/graph-rag",
            json={"enabled": True, "query_mode": cfg["graph_mode"]},
        )


# ── SSE chat ─────────────────────────────────────────────────────


async def sse_chat(
    client: httpx.AsyncClient, query: str, *, use_reranker: bool = True
) -> dict[str, Any]:
    """发起一次 chat completions，返回 {answer, refs, latency_ms, error}。"""
    body = {
        "messages": [{"role": "user", "content": query}],
        "model": "deepseek-chat",
        "stream": True,
        "use_knowledge_base": True,
        "use_reranker": use_reranker,
        "use_web_search": False,        # 硬约束：评测期禁用 web
        "enable_thinking": False,
    }

    answer_parts: list[str] = []
    refs: list[dict] = []
    error: str | None = None
    t0 = time.time()

    try:
        async with client.stream(
            "POST", f"{API}/chat/completions", json=body, timeout=120.0
        ) as resp:
            if resp.status_code != 200:
                error = f"HTTP {resp.status_code}"
                await resp.aread()
                return {"answer": "", "refs": [], "latency_ms": 0, "error": error}

            async for raw in resp.aiter_lines():
                if not raw or not raw.startswith("data:"):
                    continue
                payload = raw[len("data:"):].strip()
                if payload == "[DONE]":
                    break
                try:
                    evt = json.loads(payload)
                except json.JSONDecodeError:
                    continue
                if "content" in evt:
                    answer_parts.append(evt["content"])
                elif "parsed" in evt:
                    # xml_parser 输出：{content, refs: [...], recommend: [...]}
                    parsed = evt["parsed"]
                    if parsed.get("refs"):
                        refs = parsed["refs"]
                    if parsed.get("content"):
                        # parsed.content 覆盖累积 content（结构化模式下更干净）
                        answer_parts = [parsed["content"]]
                elif "error" in evt:
                    error = evt["error"]
    except Exception as e:
        error = f"{type(e).__name__}: {e}"

    return {
        "answer": "".join(answer_parts).strip(),
        "refs": refs,
        "latency_ms": int((time.time() - t0) * 1000),
        "error": error,
    }


# ── Runner ───────────────────────────────────────────────────────


def load_queries(max_queries: int | None) -> list[dict]:
    path = DATA_DIR / "queries.jsonl"
    if not path.exists():
        print(f"! queries.jsonl not found at {path}; run prep_crud_eval.py first")
        sys.exit(1)
    out = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            out.append(json.loads(line))
            if max_queries and len(out) >= max_queries:
                break
    return out


async def run(args) -> int:
    queries = load_queries(args.max_queries)
    configs = args.configs or list(CONFIGS.keys())
    for c in configs:
        if c not in CONFIGS:
            print(f"! unknown config: {c}; choices: {list(CONFIGS.keys())}")
            return 1

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_path = RESULTS_DIR / f"run_{ts}.jsonl"
    print(f"[bench] {len(configs)} configs × {len(queries)} queries → {out_path}")

    total = len(configs) * len(queries)
    done = 0
    t_start = time.time()

    async with httpx.AsyncClient(timeout=None) as client:
        # Preflight：embedding 必须 ready；graph 配置需要 index
        sys_r = await client.get(f"{API}/embedding/system-info")
        sys_r.raise_for_status()
        if not sys_r.json().get("embedding_ready"):
            print("! embedding not ready; open /knowledge and activate the model first")
            return 1

        any_graph = any(c.startswith("graph_") for c in configs)
        if any_graph:
            s = (await client.get(f"{API}/embedding/graph-rag/stats")).json()
            if s.get("nodes", 0) == 0:
                print("! Graph RAG index is empty; run ingest_eval_kb.py --build-graph first")
                return 1

        with open(out_path, "w", encoding="utf-8") as fout:
            for cfg_name in configs:
                print(f"\n[bench] ── applying config: {cfg_name} ──")
                await apply_config(client, cfg_name)
                await asyncio.sleep(0.2)  # 让后端配置落盘

                for q in queries:
                    done += 1
                    tag = f"[{done}/{total}]"
                    try:
                        result = await sse_chat(client, q["query"], use_reranker=True)
                    except Exception as e:
                        result = {"answer": "", "refs": [], "latency_ms": 0,
                                  "error": f"{type(e).__name__}: {e}"}

                    row = {
                        "config": cfg_name,
                        "qid": q["qid"],
                        "category": q["category"],
                        "query": q["query"],
                        "gold_answer": q["gold_answer"],
                        "gold_doc_ids": q["gold_doc_ids"],
                        "retrieved_refs": result["refs"],
                        "answer": result["answer"],
                        "latency_ms": result["latency_ms"],
                        "error": result["error"],
                    }
                    fout.write(json.dumps(row, ensure_ascii=False) + "\n")
                    fout.flush()

                    status = "!" if result["error"] else "✓"
                    print(f"{tag} {status} {cfg_name:<18} {q['qid']} {q['category']:<15} "
                          f"{result['latency_ms']:>5}ms "
                          f"{('err='+result['error'][:40]) if result['error'] else ''}")

    elapsed = time.time() - t_start
    print(f"\n[bench] {total} trials done in {elapsed/60:.1f} min → {out_path}")

    # 软链 latest.jsonl
    latest = RESULTS_DIR / "latest.jsonl"
    if latest.exists() or latest.is_symlink():
        latest.unlink()
    latest.symlink_to(out_path.name)
    print(f"[bench] symlinked {latest} -> {out_path.name}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--max-queries", type=int, default=None,
                    help="先跑前 N 条 query smoke 用（默认全部）")
    ap.add_argument("--configs", nargs="+", default=None,
                    help=f"选择要跑的 config；默认全部 10 个。可选：{list(CONFIGS.keys())}")
    args = ap.parse_args()
    return asyncio.run(run(args))


if __name__ == "__main__":
    sys.exit(main())
