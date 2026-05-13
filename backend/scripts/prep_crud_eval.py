"""
CRUD-RAG mini eval set 构造脚本。

从 IAAR-Shanghai/CRUD_RAG GitHub 仓库下载 split_merged.json（~26MB），
按类别抽 60 条 query 导出：

  tests/eval-data/crud-mini/
    ├── .cache/split_merged.json           # 原始下载（幂等，存在即跳过）
    ├── docs/crud-NNNN.txt                 # 去重后的新闻文档
    ├── queries.jsonl                      # 60 条 query（带 gold_doc_ids）
    └── metadata.json                      # 抽样配置 / 分布 / 时间戳

用法：
  cd backend && venv/bin/python scripts/prep_crud_eval.py [--seed 42] [--force]

设计：
  - 纯 stdlib（urllib + hashlib + json + random），不依赖 httpx/datasets
  - 数据来源见 plan-doc-dir/RAG评测集落地规划.md
  - doc 去重按 news 文本的 sha1 前 12 位；同一 event 在 1/2/3-docs 中的 news1 通常一致
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import random
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]  # 项目根
OUT_DIR = ROOT / "tests" / "eval-data" / "crud-mini"
CACHE_DIR = OUT_DIR / ".cache"
DOCS_DIR = OUT_DIR / "docs"

CRUD_URL = (
    "https://raw.githubusercontent.com/IAAR-Shanghai/CRUD_RAG/main/"
    "data/crud_split/split_merged.json"
)
CACHE_FILE = CACHE_DIR / "split_merged.json"

# 抽样分布（总 60，见 plan-doc-dir/RAG评测集落地规划.md）
# 调整：用 1/2/3-docs 三档 + partial_context + kb_absent，最贴近 CRUD 原生任务
SAMPLE_PLAN: list[tuple[str, str, int]] = [
    # (category 标签, CRUD 源字段, 采样数)
    ("single_hop",      "questanswer_1doc",  15),
    ("multi_hop_2",     "questanswer_2docs", 15),
    ("multi_hop_3",     "questanswer_3docs", 15),
    # partial_context：从 3docs 抽样但只 ingest news1+news2，news3 作为"缺失证据"
    # 用来压测 Agentic grading 与 Graph RAG 对不完整上下文的鲁棒性
    ("partial_context", "questanswer_3docs", 10),
    # kb_absent 在后面手动生成
]
KB_ABSENT_COUNT = 5


# ── 1. 下载 ─────────────────────────────────────────────────────────


def download_if_missing(force: bool = False) -> None:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    if CACHE_FILE.exists() and not force:
        size_mb = CACHE_FILE.stat().st_size / 1024 / 1024
        print(f"[prep] cache hit: {CACHE_FILE} ({size_mb:.1f} MB)")
        return
    print(f"[prep] downloading {CRUD_URL} → {CACHE_FILE}")
    with urllib.request.urlopen(CRUD_URL, timeout=120) as resp, open(CACHE_FILE, "wb") as f:
        total = 0
        while True:
            chunk = resp.read(1 << 20)  # 1 MB
            if not chunk:
                break
            f.write(chunk)
            total += len(chunk)
            print(f"  ... {total / 1024 / 1024:.1f} MB", end="\r")
    print(f"\n[prep] downloaded {total / 1024 / 1024:.1f} MB")


# ── 2. 抽样 ─────────────────────────────────────────────────────────


def _doc_hash(text: str) -> str:
    return hashlib.sha1(text.strip().encode("utf-8")).hexdigest()[:12]


def sample(seed: int) -> tuple[list[dict], dict[str, str]]:
    """返回 (queries, doc_table)：
    - queries: list of {qid, query, category, gold_answer, gold_doc_ids, source, source_id}
    - doc_table: dict[hash -> text]，去重后的全量文档
    """
    rng = random.Random(seed)
    with open(CACHE_FILE, encoding="utf-8") as f:
        data = json.load(f)

    queries: list[dict] = []
    doc_table: dict[str, str] = {}
    qid_counter = 0

    for category, src_key, n in SAMPLE_PLAN:
        pool = data[src_key]
        picked = rng.sample(pool, n)
        for row in picked:
            qid_counter += 1
            qid = f"Q{qid_counter:03d}"

            # 收集 news 文本
            news_fields = [k for k in ("news1", "news2", "news3") if k in row and row[k]]
            news_texts = [row[k].strip() for k in news_fields]
            gold_hashes = [_doc_hash(t) for t in news_texts]
            for h, t in zip(gold_hashes, news_texts):
                doc_table.setdefault(h, t)

            # partial_context：gold 仍是三条，但 ingest_eval_kb 会按 gold_ingest_doc_ids 只传前两条
            gold_ingest = gold_hashes
            if category == "partial_context" and len(gold_hashes) >= 3:
                gold_ingest = gold_hashes[:2]

            queries.append({
                "qid": qid,
                "query": row["questions"].strip(),
                "category": category,
                "gold_answer": row["answers"].strip(),
                "gold_doc_ids": gold_hashes,       # 完整 gold（用于 Recall@K）
                "gold_ingest_doc_ids": gold_ingest,  # 实际入库（partial_context ≠ gold）
                "source": src_key,
                "source_id": row.get("ID", ""),
            })

    # KB-absent 合成：5 条问世界上不存在 / 不在任何已抽文档中的事实
    # 策略：从 event_summary 里随机抽 5 个 event，用其 headline 但改关键实体为虚构名
    absent_events = rng.sample(data["event_summary"], KB_ABSENT_COUNT)
    for ev in absent_events:
        qid_counter += 1
        # 用明显虚构的实体问 → 期望模型要么拒答要么说"KB 无记录"
        fake_query = (
            f"请根据知识库回答：2027 年火星殖民局局长张虚构在「{ev['title'][:15]}…」"
            "事件中发表了什么声明？"
        )
        queries.append({
            "qid": f"Q{qid_counter:03d}",
            "query": fake_query,
            "category": "kb_absent",
            "gold_answer": "根据知识库内容无法回答这个问题；知识库中没有张虚构或 2027 年火星殖民局的记录。",
            "gold_doc_ids": [],           # 空：期望模型拒答
            "gold_ingest_doc_ids": [],
            "source": "synthetic",
            "source_id": "",
        })

    return queries, doc_table


# ── 3. 导出 ─────────────────────────────────────────────────────────


def export(queries: list[dict], doc_table: dict[str, str], seed: int) -> None:
    DOCS_DIR.mkdir(parents=True, exist_ok=True)

    # 按 hash 的字典序稳定编号 crud-0001.txt ...
    hashes_sorted = sorted(doc_table.keys())
    hash_to_id: dict[str, str] = {h: f"crud-{i+1:04d}" for i, h in enumerate(hashes_sorted)}

    # 清掉旧 docs（避免遗留）
    for old in DOCS_DIR.glob("crud-*.txt"):
        old.unlink()

    for h, text in doc_table.items():
        doc_id = hash_to_id[h]
        (DOCS_DIR / f"{doc_id}.txt").write_text(text, encoding="utf-8")

    # 把 queries 里的 hash 替换成人读 doc_id
    for q in queries:
        q["gold_doc_ids"] = [hash_to_id[h] for h in q["gold_doc_ids"]]
        q["gold_ingest_doc_ids"] = [hash_to_id[h] for h in q["gold_ingest_doc_ids"]]

    with open(OUT_DIR / "queries.jsonl", "w", encoding="utf-8") as f:
        for q in queries:
            f.write(json.dumps(q, ensure_ascii=False) + "\n")

    # 统计 & metadata
    from collections import Counter
    cat_counts = Counter(q["category"] for q in queries)
    metadata = {
        "seed": seed,
        "total_queries": len(queries),
        "total_unique_docs": len(doc_table),
        "category_distribution": dict(cat_counts),
        "source": CRUD_URL,
        "generated_at": __import__("datetime").datetime.now().isoformat(timespec="seconds"),
    }
    (OUT_DIR / "metadata.json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    print(f"[prep] wrote {len(queries)} queries → {OUT_DIR / 'queries.jsonl'}")
    print(f"[prep] wrote {len(doc_table)} docs → {DOCS_DIR}/")
    print(f"[prep] category distribution: {dict(cat_counts)}")


# ── main ────────────────────────────────────────────────────────────


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--force", action="store_true", help="强制重新下载原始数据")
    args = ap.parse_args()

    download_if_missing(force=args.force)
    queries, doc_table = sample(seed=args.seed)
    export(queries, doc_table, seed=args.seed)
    return 0


if __name__ == "__main__":
    sys.exit(main())
