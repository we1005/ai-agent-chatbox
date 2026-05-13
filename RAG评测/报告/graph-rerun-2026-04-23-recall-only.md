# RAG 策略对比报告

- 数据源：`run_20260422_235759.jsonl`
- 生成时间：2026-04-23 01:30:41
- 评测集：CRUD-RAG mini（60 query × 5 策略）
- Judge：DeepSeek-chat（faithfulness / answer_correctness）
- 注：`Recall@K` 对 `kb_absent` 类别不适用；Graph RAG 的 refs 若未解析到真实 file_path 会被计为 None（从均值中剔除）

## 汇总（全量）

| 配置 | n | Recall@K | Faithfulness | Correctness | 平均延迟 | 错误 |
|---|---|---|---|---|---|---|
| `graph_naive` | 60 | 0.961 | — | — | 19.68s | 0 |
| `graph_local` | 60 | 0.942 | — | — | 18.99s | 0 |
| `graph_global` | 60 | 0.936 | — | — | 18.31s | 0 |
| `graph_hybrid` | 60 | 0.941 | — | — | 17.80s | 0 |
| `graph_mix` | 60 | 0.970 | — | — | 17.65s | 0 |

## 分类下钻 · `kb_absent`（n=5）

| 配置 | n | Recall@K | Faithfulness | Correctness |
|---|---|---|---|---|
| `graph_naive` | 5 | — | — | — |
| `graph_local` | 5 | — | — | — |
| `graph_global` | 5 | — | — | — |
| `graph_hybrid` | 5 | — | — | — |
| `graph_mix` | 5 | — | — | — |

## 分类下钻 · `multi_hop_2`（n=15）

| 配置 | n | Recall@K | Faithfulness | Correctness |
|---|---|---|---|---|
| `graph_naive` | 15 | 0.900 | — | — |
| `graph_local` | 15 | 0.900 | — | — |
| `graph_global` | 15 | 0.900 | — | — |
| `graph_hybrid` | 15 | 0.900 | — | — |
| `graph_mix` | 15 | 0.933 | — | — |

## 分类下钻 · `multi_hop_3`（n=15）

| 配置 | n | Recall@K | Faithfulness | Correctness |
|---|---|---|---|---|
| `graph_naive` | 15 | 0.956 | — | — |
| `graph_local` | 15 | 0.933 | — | — |
| `graph_global` | 15 | 0.911 | — | — |
| `graph_hybrid` | 15 | 0.929 | — | — |
| `graph_mix` | 15 | 0.956 | — | — |

## 分类下钻 · `partial_context`（n=10）

| 配置 | n | Recall@K | Faithfulness | Correctness |
|---|---|---|---|---|
| `graph_naive` | 10 | 1.000 | — | — |
| `graph_local` | 10 | 0.933 | — | — |
| `graph_global` | 10 | 0.933 | — | — |
| `graph_hybrid` | 10 | 0.933 | — | — |
| `graph_mix` | 10 | 1.000 | — | — |

## 分类下钻 · `single_hop`（n=15）

| 配置 | n | Recall@K | Faithfulness | Correctness |
|---|---|---|---|---|
| `graph_naive` | 15 | 1.000 | — | — |
| `graph_local` | 15 | 1.000 | — | — |
| `graph_global` | 15 | 1.000 | — | — |
| `graph_hybrid` | 15 | 1.000 | — | — |
| `graph_mix` | 15 | 1.000 | — | — |
