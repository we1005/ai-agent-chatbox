"""
离线分析 logs/catalog_intent.jsonl：统计目录型 query 规则识别的触发率、规则 vs
Planner 实际选择的关联矩阵，并抽样打印每个象限的用户 query 供人工复核。

用法：
    python -m scripts.analyze_catalog_intent                      # 默认读项目 logs/
    python -m scripts.analyze_catalog_intent --path /other.jsonl  # 自定义路径
    python -m scripts.analyze_catalog_intent --sample 10          # 每象限抽 10 条

统计逻辑：
  - is_catalog=True / False              × (Planner 是否调了 query_knowledge_base_catalog)
  - 划 2x2 四象限：
      TP = 规则命中  & Planner 确实调了 catalog 工具  → 规则与 LLM 一致
      FP = 规则命中  & Planner 没调 catalog 工具     → 规则可能误触（或 LLM 偏离引导）
      FN = 规则漏检  & Planner 却调了 catalog 工具   → 规则漏检（Planner 靠基础 prompt 救回）
      TN = 规则漏检  & Planner 也没调 catalog 工具   → 双方一致认为非目录型

注意：TP/FP 是"与 Planner 的行为一致性"，不是真正的 ground truth；
真正的 precision/recall 需要抽样人工标注（脚本输出每象限样本便于打标）。
"""

from __future__ import annotations

import argparse
import json
import os
import random
import sys
from collections import Counter
from pathlib import Path

CATALOG_TOOL = "query_knowledge_base_catalog"

_HERE = Path(__file__).resolve().parent
_PROJECT_ROOT = _HERE.parent.parent
_DEFAULT_PATH = _PROJECT_ROOT / "logs" / "catalog_intent.jsonl"


def _load(path: Path) -> list[dict]:
    if not path.exists():
        print(f"日志文件不存在：{path}", file=sys.stderr)
        print("（Solo 模式至少跑过一次首轮才会产生事件。）", file=sys.stderr)
        return []
    records = []
    with path.open(encoding="utf-8") as f:
        for i, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError as e:
                print(f"[WARN] 第 {i} 行解析失败: {e}", file=sys.stderr)
    return records


def _classify_quadrant(rec: dict) -> str:
    """把每条事件归入 TP/FP/FN/TN 四象限（对照定义见模块 docstring）。"""
    is_catalog = bool(rec.get("is_catalog"))
    planner_called_catalog = CATALOG_TOOL in (rec.get("planner_tools") or [])
    if is_catalog and planner_called_catalog:
        return "TP"
    if is_catalog and not planner_called_catalog:
        return "FP"
    if not is_catalog and planner_called_catalog:
        return "FN"
    return "TN"


def _print_section(title: str) -> None:
    print(f"\n{'=' * 60}\n  {title}\n{'=' * 60}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--path", default=str(_DEFAULT_PATH), help="JSON-L 日志路径")
    parser.add_argument("--sample", type=int, default=5, help="每象限抽几条 query 样本")
    args = parser.parse_args()

    records = _load(Path(args.path))
    if not records:
        return

    _print_section(f"总览（来源：{args.path}）")
    print(f"总事件数: {len(records)}")

    # 基础触发率
    trig = sum(1 for r in records if r.get("is_catalog"))
    print(f"规则触发数: {trig} ({trig/len(records):.1%})")
    planner_catalog = sum(1 for r in records if CATALOG_TOOL in (r.get("planner_tools") or []))
    print(f"Planner 实际调 catalog: {planner_catalog} ({planner_catalog/len(records):.1%})")
    no_tool = sum(1 for r in records if not (r.get("planner_tools") or []))
    print(f"Planner 零工具调用: {no_tool} ({no_tool/len(records):.1%})")

    # 模型分布
    model_counter = Counter(r.get("model_name", "unknown") for r in records)
    print(f"模型分布: {dict(model_counter)}")

    # 命中原因分布（仅 is_catalog=True）
    _print_section("规则命中原因分布")
    reason_counter = Counter(r.get("reason", "") for r in records if r.get("is_catalog"))
    for reason, cnt in reason_counter.most_common():
        print(f"  {cnt:3d}  {reason}")

    # 2x2 象限
    _print_section("规则 vs Planner 一致性矩阵")
    quadrants = {q: [] for q in ("TP", "FP", "FN", "TN")}
    for rec in records:
        quadrants[_classify_quadrant(rec)].append(rec)

    print(f"  TP (规则命中 & Planner 调 catalog):    {len(quadrants['TP']):3d}")
    print(f"  FP (规则命中 & Planner 没调 catalog):  {len(quadrants['FP']):3d}")
    print(f"  FN (规则漏检 & Planner 调了 catalog):  {len(quadrants['FN']):3d}")
    print(f"  TN (规则漏检 & Planner 也没调 catalog): {len(quadrants['TN']):3d}")

    if trig > 0:
        precision = len(quadrants["TP"]) / trig
        print(f"\n  规则-Planner Precision (TP/(TP+FP)): {precision:.1%}")
        print(f"    = 规则命中的场景中，Planner 确实按路由调了 catalog 的比例")
    if planner_catalog > 0:
        recall = len(quadrants["TP"]) / planner_catalog
        print(f"  规则-Planner Recall    (TP/(TP+FN)): {recall:.1%}")
        print(f"    = Planner 调了 catalog 的场景中，规则提前正确识别的比例")

    # 每象限抽样
    _print_section(f"每象限抽样（各 {args.sample} 条；供人工复核真正假阳/假阴）")
    for q, items in quadrants.items():
        if not items:
            print(f"\n[{q}] （空）")
            continue
        sample = random.sample(items, min(args.sample, len(items)))
        print(f"\n[{q}] 抽样 {len(sample)}/{len(items)}：")
        for r in sample:
            tools = ",".join(r.get("planner_tools") or []) or "(none)"
            print(f"  - query   : {r.get('query')!r}")
            print(f"    reason  : {r.get('reason')!r}")
            print(f"    tools   : {tools}")
            print(f"    has_ans : {r.get('planner_has_content')}")
            print(f"    ts      : {r.get('ts')}")

    print()  # 末尾空行


if __name__ == "__main__":
    main()
