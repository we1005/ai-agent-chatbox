# RAG 策略对比报告

- 数据源：`latest.jsonl`
- 生成时间：2026-04-22 15:33:59
- 评测集：CRUD-RAG mini（60 query × 3 策略）
- Judge：DeepSeek-chat（faithfulness / answer_correctness）
- 注：`Recall@K` 对 `kb_absent` 类别不适用；Graph RAG 的 refs 若未解析到真实 file_path 会被计为 None（从均值中剔除）

## 汇总（全量）

| 配置 | n | Recall@K | Faithfulness | Correctness | 平均延迟 | 错误 |
|---|---|---|---|---|---|---|
| `off` | 5 | 1.000 | 0.820 | 0.818 | 4.62s | 0 |
| `multi_query` | 5 | 1.000 | 1.000 | 0.828 | 6.86s | 0 |
| `agentic_grading` | 5 | 1.000 | 0.933 | 0.848 | 8.02s | 0 |

## 分类下钻 · `single_hop`（n=5）

| 配置 | n | Recall@K | Faithfulness | Correctness |
|---|---|---|---|---|
| `off` | 5 | 1.000 | 0.820 | 0.818 |
| `multi_query` | 5 | 1.000 | 1.000 | 0.828 |
| `agentic_grading` | 5 | 1.000 | 0.933 | 0.848 |
