# RAG 策略对比报告

- 数据源：`latest.jsonl`
- 生成时间：2026-04-22 21:15:55
- 评测集：CRUD-RAG mini（60 query × 10 策略）
- Judge：DeepSeek-chat（faithfulness / answer_correctness）
- 注：`Recall@K` 对 `kb_absent` 类别不适用；Graph RAG 的 refs 若未解析到真实 file_path 会被计为 None（从均值中剔除）

## 汇总（全量）

| 配置 | n | Recall@K | Faithfulness | Correctness | 平均延迟 | 错误 |
|---|---|---|---|---|---|---|
| `off` | 60 | 0.933 | 0.606 | 0.679 | 7.08s | 0 |
| `multi_query` | 60 | 0.921 | 0.590 | 0.625 | 9.78s | 0 |
| `agentic_grading` | 60 | 0.897 | 0.583 | 0.702 | 10.36s | 0 |
| `agentic_rewrite` | 60 | 0.906 | 0.594 | 0.669 | 12.76s | 0 |
| `agentic_full` | 60 | 0.918 | 0.576 | 0.665 | 14.97s | 0 |
| `graph_naive` | 60 | 0.000 | 0.147 | 0.664 | 7.83s | 0 |
| `graph_local` | 60 | 0.230 | 0.211 | 0.648 | 38.45s | 8 |
| `graph_global` | 60 | 0.113 | 0.083 | 0.675 | 31.29s | 8 |
| `graph_hybrid` | 60 | 0.000 | 0.110 | 0.653 | 21.66s | 1 |
| `graph_mix` | 60 | 0.000 | 0.110 | 0.640 | 22.06s | 0 |

## 分类下钻 · `kb_absent`（n=5）

| 配置 | n | Recall@K | Faithfulness | Correctness |
|---|---|---|---|---|
| `off` | 5 | — | 0.176 | 0.547 |
| `multi_query` | 5 | — | 0.630 | 0.527 |
| `agentic_grading` | 5 | — | 0.320 | 0.646 |
| `agentic_rewrite` | 5 | — | 0.214 | 0.595 |
| `agentic_full` | 5 | — | 0.000 | 0.510 |
| `graph_naive` | 5 | — | 0.376 | 0.598 |
| `graph_local` | 5 | — | 0.420 | 0.647 |
| `graph_global` | 5 | — | 0.125 | 0.550 |
| `graph_hybrid` | 5 | — | 0.326 | 0.507 |
| `graph_mix` | 5 | — | 0.156 | 0.539 |

## 分类下钻 · `multi_hop_2`（n=15）

| 配置 | n | Recall@K | Faithfulness | Correctness |
|---|---|---|---|---|
| `off` | 15 | 0.933 | 0.657 | 0.679 |
| `multi_query` | 15 | 0.933 | 0.523 | 0.587 |
| `agentic_grading` | 15 | 0.867 | 0.563 | 0.686 |
| `agentic_rewrite` | 15 | 0.900 | 0.599 | 0.686 |
| `agentic_full` | 15 | 0.900 | 0.522 | 0.669 |
| `graph_naive` | 15 | 0.000 | 0.092 | 0.670 |
| `graph_local` | 15 | 0.300 | 0.177 | 0.577 |
| `graph_global` | 15 | 0.125 | 0.116 | 0.658 |
| `graph_hybrid` | 15 | 0.000 | 0.034 | 0.659 |
| `graph_mix` | 15 | 0.000 | 0.019 | 0.649 |

## 分类下钻 · `multi_hop_3`（n=15）

| 配置 | n | Recall@K | Faithfulness | Correctness |
|---|---|---|---|---|
| `off` | 15 | 0.889 | 0.659 | 0.643 |
| `multi_query` | 15 | 0.867 | 0.609 | 0.622 |
| `agentic_grading` | 15 | 0.844 | 0.587 | 0.670 |
| `agentic_rewrite` | 15 | 0.867 | 0.660 | 0.627 |
| `agentic_full` | 15 | 0.889 | 0.656 | 0.631 |
| `graph_naive` | 15 | 0.000 | 0.127 | 0.636 |
| `graph_local` | 15 | 0.296 | 0.199 | 0.558 |
| `graph_global` | 15 | 0.000 | 0.026 | 0.630 |
| `graph_hybrid` | 15 | 0.000 | 0.029 | 0.604 |
| `graph_mix` | 15 | 0.000 | 0.078 | 0.570 |

## 分类下钻 · `partial_context`（n=10）

| 配置 | n | Recall@K | Faithfulness | Correctness |
|---|---|---|---|---|
| `off` | 10 | 0.900 | 0.596 | 0.667 |
| `multi_query` | 10 | 0.867 | 0.514 | 0.642 |
| `agentic_grading` | 10 | 0.867 | 0.576 | 0.676 |
| `agentic_rewrite` | 10 | 0.833 | 0.539 | 0.609 |
| `agentic_full` | 10 | 0.867 | 0.590 | 0.593 |
| `graph_naive` | 10 | 0.000 | 0.110 | 0.614 |
| `graph_local` | 10 | 0.111 | 0.103 | 0.649 |
| `graph_global` | 10 | 0.000 | 0.020 | 0.601 |
| `graph_hybrid` | 10 | 0.000 | 0.019 | 0.605 |
| `graph_mix` | 10 | 0.000 | 0.124 | 0.633 |

## 分类下钻 · `single_hop`（n=15）

| 配置 | n | Recall@K | Faithfulness | Correctness |
|---|---|---|---|---|
| `off` | 15 | 1.000 | 0.652 | 0.768 |
| `multi_query` | 15 | 1.000 | 0.676 | 0.689 |
| `agentic_grading` | 15 | 1.000 | 0.691 | 0.788 |
| `agentic_rewrite` | 15 | 1.000 | 0.685 | 0.760 |
| `agentic_full` | 15 | 1.000 | 0.730 | 0.793 |
| `graph_naive` | 15 | 0.000 | 0.170 | 0.738 |
| `graph_local` | 15 | 0.000 | 0.247 | 0.766 |
| `graph_global` | 15 | 1.000 | 0.136 | 0.825 |
| `graph_hybrid` | 15 | 0.000 | 0.267 | 0.783 |
| `graph_mix` | 15 | 0.000 | 0.206 | 0.738 |
