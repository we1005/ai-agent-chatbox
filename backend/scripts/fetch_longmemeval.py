"""下载 LongMemEval 数据集到本地缓存。

用法：
    python scripts/fetch_longmemeval.py            # 下载全部 500 QA
    python scripts/fetch_longmemeval.py --sample 10  # 只取前 10 条（smoke）
    python scripts/fetch_longmemeval.py --oracle      # 取前 250 条（oracle 子集）

输出：
    tests/eval-data/longmemeval/full_questions.jsonl    全量（或 --sample N 限制的）
    tests/eval-data/longmemeval/oracle_questions.jsonl  前 250 条
    tests/eval-data/longmemeval/.cache/                 HF 下载缓存

注意：
    longmemeval_m_cleaned.json 超过 pyarrow int32 block_size 上限，
    改用直接读取 HF Hub cache JSON 文件绕过 datasets 预处理。
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
OUTPUT_DIR = PROJECT_ROOT / "tests" / "eval-data" / "longmemeval"
CACHE_DIR = OUTPUT_DIR / ".cache"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
CACHE_DIR.mkdir(parents=True, exist_ok=True)

HF_HUB_CACHE = Path.home() / ".cache" / "huggingface" / "hub"
HF_DATASET_GLOB = "datasets--xiaowu0162--longmemeval-cleaned"


def _write_synthetic_smoke() -> None:
    """无网络时写入 3 条合成 smoke 数据（用于验证 pipeline 流程，非真实评测）。"""
    synthetic = [
        {
            "session_id": "smoke_001",
            "question_type": "single_session_user",
            "question": "What programming language did I mention I prefer?",
            "answer": "Python",
            "haystack_sessions": [{"conversations": [
                {"role": "user", "content": "I've been coding for 5 years and I really prefer Python for data work."},
                {"role": "assistant", "content": "Python is an excellent choice for data work."},
                {"role": "user", "content": "Yes exactly, I also use it for web scraping."},
                {"role": "assistant", "content": "Python's requests and BeautifulSoup make web scraping easy."},
            ]}],
        },
        {
            "session_id": "smoke_002",
            "question_type": "knowledge_update",
            "question": "What is my current job title?",
            "answer": "Senior Data Engineer",
            "haystack_sessions": [
                {"conversations": [
                    {"role": "user", "content": "I just started a new job as a Data Analyst."},
                    {"role": "assistant", "content": "Congratulations on your new role as a Data Analyst!"},
                ]},
                {"conversations": [
                    {"role": "user", "content": "I got promoted! I am now a Senior Data Engineer."},
                    {"role": "assistant", "content": "Congratulations on your promotion to Senior Data Engineer!"},
                ]},
            ],
        },
        {
            "session_id": "smoke_003",
            "question_type": "multi_session",
            "question": "What two hobbies have I mentioned across our conversations?",
            "answer": "Hiking and photography",
            "haystack_sessions": [
                {"conversations": [
                    {"role": "user", "content": "I love going hiking on weekends."},
                    {"role": "assistant", "content": "Hiking is a wonderful hobby for staying active."},
                ]},
                {"conversations": [
                    {"role": "user", "content": "I also picked up photography recently."},
                    {"role": "assistant", "content": "Photography is a great complement to hiking!"},
                ]},
            ],
        },
    ]
    out = OUTPUT_DIR / "full_questions.jsonl"
    with open(out, "w", encoding="utf-8") as f:
        for r in synthetic:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(f"[fetch] 合成 smoke 数据（3 条）→ {out}（仅用于 pipeline 验证，非真实评测）")


def _find_s_cleaned_json() -> Path | None:
    """在 HF Hub cache 里找 longmemeval_s_cleaned.json（symlink 或实体文件均可）。"""
    candidates = list(HF_HUB_CACHE.glob(f"{HF_DATASET_GLOB}/snapshots/*/longmemeval_s_cleaned.json"))
    if candidates:
        return candidates[0].resolve()
    return None


def fetch(sample: int | None, oracle_only: bool) -> None:
    json_path = _find_s_cleaned_json()
    if json_path and json_path.exists():
        print(f"[fetch] 读取 HF Hub cache: {json_path}")
        with open(json_path, encoding="utf-8") as f:
            raw = json.load(f)
        # 数据集可能是 list-of-dicts 或 {"data": [...]} 格式
        if isinstance(raw, list):
            records = raw
        elif isinstance(raw, dict) and "data" in raw:
            records = raw["data"]
        else:
            # 尝试 JSON Lines 格式
            records = [json.loads(line) for line in json_path.read_text().splitlines() if line.strip()]
    else:
        # fallback: 用 datasets 库（需网络）
        try:
            from datasets import load_dataset
        except ImportError:
            print("ERROR: 请先安装 datasets>=3.0：pip install 'datasets>=3.0'")
            sys.exit(1)
        print(f"[fetch] 从 HuggingFace 下载 xiaowu0162/longmemeval-cleaned ...")
        os.environ.pop("HF_ENDPOINT", None)
        os.environ["HF_ENDPOINT"] = "https://huggingface.co"
        ds = load_dataset(
            "xiaowu0162/longmemeval-cleaned",
            split="longmemeval_s_cleaned",
            cache_dir=str(CACHE_DIR),
        )
        records = list(ds)

    total = len(records)
    print(f"[fetch] 数据集大小：{total} 条")

    if sample is not None:
        records = records[:sample]
        print(f"[fetch] --sample {sample}：截取前 {len(records)} 条")

    full_path = OUTPUT_DIR / "full_questions.jsonl"
    with open(full_path, "w", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(f"[fetch] 写入 {len(records)} 条 → {full_path}")

    if not oracle_only and sample is None:
        oracle = records[:250]
        oracle_path = OUTPUT_DIR / "oracle_questions.jsonl"
        with open(oracle_path, "w", encoding="utf-8") as f:
            for r in oracle:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")
        print(f"[fetch] oracle 250 条 → {oracle_path}")
    elif oracle_only:
        oracle = records[:250]
        oracle_path = OUTPUT_DIR / "oracle_questions.jsonl"
        with open(oracle_path, "w", encoding="utf-8") as f:
            for r in oracle:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")
        print(f"[fetch] oracle 250 条 → {oracle_path}")

    print("[fetch] Done.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--sample", type=int, default=None, help="只取前 N 条（smoke 用）")
    parser.add_argument("--oracle", action="store_true", help="同时写 oracle_questions.jsonl（前 250）")
    parser.add_argument("--synthetic", action="store_true", help="写 3 条合成 smoke 数据（无网络时用）")
    args = parser.parse_args()
    if args.synthetic:
        _write_synthetic_smoke()
    else:
        fetch(sample=args.sample, oracle_only=args.oracle)
