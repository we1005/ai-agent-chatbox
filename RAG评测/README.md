# RAG 策略评测

本文件夹集中存放本项目的 RAG 策略横向对比评测资料：**数据集说明、评测方法、执行手册、历史报告**。

## 背景

项目目前并行了 **10 种 RAG 策略**（见 `评测方法.md §策略矩阵`）：
classical / Multi-Query / Agentic(3 档) / Graph RAG(5 档)。本评测目的是用同一份
中文多跳数据集横评这些策略，产出可复现、可追踪的对比结论。

## 导航

| 文件 | 内容 |
|---|---|
| [`数据集说明.md`](./数据集说明.md) | CRUD-RAG mini 的来源、抽样逻辑、60 条 query 的分布、文档路径 |
| [`评测方法.md`](./评测方法.md) | 10 策略 × 4 指标矩阵、SSE runner 机制、RAGAS 配置、成本防护 |
| [`执行手册.md`](./执行手册.md) | 从零到一跑完整套评测的命令清单 + 排错 |
| [`报告/`](./报告/) | 每次评测的 markdown 报告（按日期归档）|

## 关联文档

- 规划：[`plan-doc-dir/RAG评测集落地规划.md`](../plan-doc-dir/RAG评测集落地规划.md)
- Graph RAG 场景边界：[`plan-doc-dir/Graph-RAG适合的文档特征与开源评测集.md`](../plan-doc-dir/Graph-RAG适合的文档特征与开源评测集.md)
- LightRAG 实现：[`plan-doc-dir/LightRAG集成落地.md`](../plan-doc-dir/LightRAG集成落地.md)
- Agentic RAG 实现：[`plan-doc-dir/Agentic-RAG档位开关落地.md`](../plan-doc-dir/Agentic-RAG档位开关落地.md)

## 关键路径速查

```
# 脚本
backend/scripts/prep_crud_eval.py          # 下载 CRUD + 抽 60 条
backend/scripts/ingest_eval_kb.py          # 批量上传 + 可选建 Graph RAG 索引
backend/scripts/run_rag_bench.py           # 10 × 60 SSE runner
backend/scripts/score_rag_bench.py         # Recall@K + RAGAS → markdown 报告

# 数据
tests/eval-data/crud-mini/.cache/split_merged.json   # CRUD 原始（26MB，gitignore 建议）
tests/eval-data/crud-mini/docs/crud-NNNN.txt         # 118 篇去重新闻
tests/eval-data/crud-mini/queries.jsonl              # 60 条标注 query
tests/eval-data/crud-mini/metadata.json              # 抽样元数据

# 输出
tests/eval-data/results/run_<ts>.jsonl               # 原始 trial 记录
tests/eval-data/results/latest.jsonl  → run_*        # 最新 run 软链
tests/eval-data/results/scored_<ts>.jsonl            # 带 RAGAS 分的明细
tests/eval-data/results/report_<ts>.md               # 汇总 + 分类下钻表
```
