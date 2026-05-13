"""
把 tests/eval-data/crud-mini/docs/ 批量灌进运行中的后端知识库。

- 幂等：先查 /api/documents，filename 已存在则跳过
- 上传后轮询 /api/documents/{file_id}/status 直到 done / failed
- 可选 --build-graph：全部 done 后触发 Graph RAG 索引构建，轮询进度
- --yes：跳过 Graph RAG 构建的二次确认

用法：
  cd backend && venv/bin/python scripts/ingest_eval_kb.py [--build-graph] [--yes] [--concurrency 2]

前置：
  1. bash start-all.sh 启动所有服务
  2. /knowledge 页已激活 Embedding 模型
  3. 已跑过 prep_crud_eval.py 生成 tests/eval-data/crud-mini/docs/

详见 plan-doc-dir/RAG评测集落地规划.md。
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
import time
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[2]
DOCS_DIR = ROOT / "tests" / "eval-data" / "crud-mini" / "docs"
API = "http://localhost:8000/api"

POLL_INTERVAL_S = 2.0
POLL_TIMEOUT_S = 120.0


# ── Upload + poll ──────────────────────────────────────────────────


async def list_existing(client: httpx.AsyncClient) -> set[str]:
    r = await client.get(f"{API}/documents")
    r.raise_for_status()
    return {d["filename"] for d in r.json()}


async def upload_one(client: httpx.AsyncClient, file_path: Path) -> str | None:
    """返回 file_id；失败返回 None。"""
    with open(file_path, "rb") as f:
        files = {"file": (file_path.name, f, "text/plain")}
        r = await client.post(f"{API}/upload", files=files)
    if r.status_code != 200:
        print(f"[ingest]   ! upload failed {file_path.name}: {r.status_code} {r.text[:200]}")
        return None
    data = r.json()
    return (data.get("details") or {}).get("file_id")


async def wait_done(client: httpx.AsyncClient, file_id: str, name: str) -> bool:
    t0 = time.time()
    while time.time() - t0 < POLL_TIMEOUT_S:
        r = await client.get(f"{API}/documents/{file_id}/status")
        if r.status_code != 200:
            await asyncio.sleep(POLL_INTERVAL_S)
            continue
        s = r.json()
        st = s.get("status")
        if st == "done":
            return True
        if st == "failed":
            print(f"[ingest]   ! {name} failed: {s.get('error_message')}")
            return False
        await asyncio.sleep(POLL_INTERVAL_S)
    print(f"[ingest]   ! {name} timeout after {POLL_TIMEOUT_S}s")
    return False


async def ingest_all(concurrency: int) -> list[str]:
    """返回成功 done 的文件 id 列表。"""
    files = sorted(DOCS_DIR.glob("crud-*.txt"))
    if not files:
        print(f"[ingest] no docs in {DOCS_DIR}; run prep_crud_eval.py first")
        return []

    print(f"[ingest] {len(files)} candidate docs in {DOCS_DIR}")

    async with httpx.AsyncClient(timeout=60.0) as client:
        existing = await list_existing(client)
        to_upload = [f for f in files if f.name not in existing]
        print(f"[ingest] skipping {len(files) - len(to_upload)} already-uploaded files")
        print(f"[ingest] uploading {len(to_upload)}...")

        sem = asyncio.Semaphore(concurrency)

        async def _one(f: Path) -> tuple[str, bool]:
            async with sem:
                fid = await upload_one(client, f)
                if not fid:
                    return (f.name, False)
                ok = await wait_done(client, fid, f.name)
                status = "✓" if ok else "✗"
                print(f"[ingest]   {status} {f.name}")
                return (f.name, ok)

        results = await asyncio.gather(*[_one(f) for f in to_upload])
        ok_count = sum(1 for _, ok in results if ok)
        print(f"[ingest] uploaded {ok_count}/{len(to_upload)} OK; "
              f"total in KB: {ok_count + len(files) - len(to_upload)}")

        # 验证
        final = await list_existing(client)
        done = [f.name for f in files if f.name in final]
        return done


# ── Graph RAG build ──────────────────────────────────────────────


async def build_graph(client: httpx.AsyncClient) -> None:
    stats_r = await client.get(f"{API}/embedding/graph-rag/stats")
    stats = stats_r.json() if stats_r.status_code == 200 else {}
    if stats.get("nodes", 0) > 0:
        print(f"[graph] existing index: nodes={stats['nodes']} edges={stats['edges']} "
              f"docs={stats['documents']} — LightRAG 会增量更新")

    r = await client.post(f"{API}/embedding/graph-rag/build")
    if r.status_code != 200:
        print(f"[graph] ! build kickoff failed: {r.status_code} {r.text[:300]}")
        return
    print(f"[graph] build started; polling /graph-rag/build/status")

    t0 = time.time()
    last_processed = -1
    while True:
        await asyncio.sleep(3.0)
        s = (await client.get(f"{API}/embedding/graph-rag/build/status")).json()
        if s["processed"] != last_processed:
            last = s.get("current_doc") or ""
            print(f"[graph]   {s['processed']}/{s['total']} ({s.get('phase')}) {last[:40]}")
            last_processed = s["processed"]
        if s["status"] in ("done", "error", "idle"):
            elapsed = time.time() - t0
            print(f"[graph] {s['status']} in {elapsed:.1f}s — {s.get('message')}")
            break

    final = (await client.get(f"{API}/embedding/graph-rag/stats")).json()
    print(f"[graph] final index: nodes={final['nodes']} edges={final['edges']} "
          f"docs={final['documents']}")


# ── main ─────────────────────────────────────────────────────────


async def _main_async(args) -> int:
    done_files = await ingest_all(concurrency=args.concurrency)
    if not done_files:
        return 1

    if not args.build_graph:
        print("[ingest] done. Pass --build-graph to also build LightRAG index.")
        return 0

    if not args.yes:
        print("\n[graph] 即将对 KB 中全部文档构建 Graph RAG 索引。")
        print("[graph] 预估：~118 次 LLM 抽取调用（DeepSeek-chat），成本 <$1，耗时 5-15 min")
        reply = input("[graph] 继续？(y/N) ").strip().lower()
        if reply != "y":
            print("[graph] skipped")
            return 0

    async with httpx.AsyncClient(timeout=None) as client:
        await build_graph(client)
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--build-graph", action="store_true",
                    help="上传完成后触发 LightRAG 索引构建")
    ap.add_argument("--yes", action="store_true",
                    help="跳过 Graph RAG 构建的二次确认")
    ap.add_argument("--concurrency", type=int, default=2,
                    help="上传并发（默认 2；Embedding 模型本地运行时别开太高）")
    args = ap.parse_args()
    return asyncio.run(_main_async(args))


if __name__ == "__main__":
    sys.exit(main())
