# RAG 策略对比报告

- 数据源：`run_20260422_235759.jsonl`
- 生成时间：2026-04-23 02:02:48
- 评测集：CRUD-RAG mini（60 query × 5 策略）
- Judge：DeepSeek-chat（faithfulness / answer_correctness）
- 注：`Recall@K` 对 `kb_absent` 类别不适用；Graph RAG 的 refs 若未解析到真实 file_path 会被计为 None（从均值中剔除）

## 汇总（全量）

| 配置 | n | Recall@K | Faithfulness | Correctness | 平均延迟 | 错误 |
|---|---|---|---|---|---|---|
| `graph_naive` | 60 | 0.961 | 0.626 | 0.667 | 19.68s | 0 |
| `graph_local` | 60 | 0.942 | 0.629 | 0.651 | 18.99s | 0 |
| `graph_global` | 60 | 0.936 | 0.614 | 0.633 | 18.31s | 0 |
| `graph_hybrid` | 60 | 0.941 | 0.668 | 0.683 | 17.80s | 0 |
| `graph_mix` | 60 | 0.970 | — | — | 17.65s | 0 |

## 分类下钻 · `kb_absent`（n=5）

| 配置 | n | Recall@K | Faithfulness | Correctness |
|---|---|---|---|---|
| `graph_naive` | 5 | — | 0.518 | 0.533 |
| `graph_local` | 5 | — | 0.568 | 0.521 |
| `graph_global` | 5 | — | 0.474 | 0.446 |
| `graph_hybrid` | 5 | — | — | — |
| `graph_mix` | 5 | — | — | — |

## 分类下钻 · `multi_hop_2`（n=15）

| 配置 | n | Recall@K | Faithfulness | Correctness |
|---|---|---|---|---|
| `graph_naive` | 15 | 0.900 | 0.549 | 0.652 |
| `graph_local` | 15 | 0.900 | 0.619 | 0.623 |
| `graph_global` | 15 | 0.900 | 0.554 | 0.610 |
| `graph_hybrid` | 15 | 0.900 | 0.603 | 0.627 |
| `graph_mix` | 15 | 0.933 | — | — |

## 分类下钻 · `multi_hop_3`（n=15）

| 配置 | n | Recall@K | Faithfulness | Correctness |
|---|---|---|---|---|
| `graph_naive` | 15 | 0.956 | 0.680 | 0.648 |
| `graph_local` | 15 | 0.933 | 0.625 | 0.591 |
| `graph_global` | 15 | 0.911 | 0.702 | 0.639 |
| `graph_hybrid` | 15 | 0.929 | 0.611 | 0.561 |
| `graph_mix` | 15 | 0.956 | — | — |

## 分类下钻 · `partial_context`（n=10）

| 配置 | n | Recall@K | Faithfulness | Correctness |
|---|---|---|---|---|
| `graph_naive` | 10 | 1.000 | 0.625 | 0.655 |
| `graph_local` | 10 | 0.933 | 0.583 | 0.675 |
| `graph_global` | 10 | 0.933 | 0.647 | 0.613 |
| `graph_hybrid` | 10 | 0.933 | — | — |
| `graph_mix` | 10 | 1.000 | — | — |

## 分类下钻 · `single_hop`（n=15）

| 配置 | n | Recall@K | Faithfulness | Correctness |
|---|---|---|---|---|
| `graph_naive` | 15 | 1.000 | 0.683 | 0.753 |
| `graph_local` | 15 | 1.000 | 0.695 | 0.768 |
| `graph_global` | 15 | 1.000 | 0.615 | 0.722 |
| `graph_hybrid` | 15 | 1.000 | 0.743 | 0.760 |
| `graph_mix` | 15 | 1.000 | — | — |
