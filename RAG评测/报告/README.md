# 评测报告归档

按时间倒序列。每次 run 存：

---

## 2026-04-23 · graph_* 重跑（parser 修复后）

- **范围**：只重跑 5 个 graph_* 配置 × 60 query = 300 trials
- **动机**：首轮 full run（2026-04-22）发现 graph_* 的 Recall@K 全部接近 0 —— 诊断是 LightRAG 1.4.x 的输出格式从 `---Sources---` 变成 `Knowledge Graph Data (Entity) + Reference Document List`，`graph_rag._split_by_sources` 老 regex 匹配不上。修完新增 `_split_by_reference_list` 并加测试（提交 `496097e` 后续）。
- **时长**：~1.5 h，0 errors（对比首轮 17 个 timeout）
- **成本**：~$1（300 次 chat LLM 调用）

### Recall@K 前后对比（🔥 修复效果炸裂）

| 配置 | 首轮（parser bug）| 重跑（parser 修好）| Δ |
|---|---:|---:|---:|
| `graph_naive`  | 0.000 | **0.961** | +0.961 |
| `graph_local`  | 0.230 | **0.942** | +0.712 |
| `graph_global` | 0.113 | **0.936** | +0.823 |
| `graph_hybrid` | 0.000 | **0.941** | +0.941 |
| `graph_mix`    | 0.000 | **0.970** 🏆 | +0.970 |

**对比非-graph 配置（首轮数据）**：

| 配置 | Recall@K | 排名 |
|---|---:|---|
| **`graph_mix`**     | **0.970** | 🥇 新冠军 |
| `graph_naive`       | 0.961 | 🥈 |
| `graph_local`       | 0.942 |  |
| `graph_hybrid`      | 0.941 |  |
| `graph_global`      | 0.936 |  |
| `off` (classical)   | 0.933 |  |
| `multi_query`       | 0.921 |  |
| `agentic_full`      | 0.918 |  |
| `agentic_rewrite`   | 0.906 |  |
| `agentic_grading`   | 0.897 | 🥉 末位 |

→ 修复后 **graph_mix / graph_naive 是 Recall@K 前两名**；agentic 三档反而排末位。

### 其他观察

- **单跳（single_hop）**：所有 5 个 graph config 都打到 **Recall@K = 1.000**，与 classical/agentic 持平
- **多跳 3（multi_hop_3）**：graph_naive / graph_mix 0.956，其它 graph_* 0.911-0.933；对比 agentic_grading 的 0.844、off 的 0.889——**graph_naive/mix 在多跳场景确实领先**，量级 +5-7 pts
- **partial_context**：graph_naive / graph_mix 双双 1.000，胜过 agentic_grading 的 0.867
- **延迟**：17-19s 稳定（首轮 local 38s / global 31s），parser fix 顺带绕开某些 retry 路径让链路更快
- **0 errors**：首轮 17 个 timeout（graph_local 8 + graph_global 8 + graph_hybrid 1）全消失

### 重要提醒 · 这是否推翻了 "agentic_grading 最稳" 的首轮结论？

**Recall@K 层面**：是，graph_mix 现在是新冠军。但：
- Correctness / Faithfulness 需等 RAGAS 跑完（后台中，~70 min）后才能定结论
- 首轮报告的 **agentic_grading Correctness 0.702 跨类别最稳** 仍是既有事实；新 Recall 高 ≠ Correctness 高（answer 生成阶段才决定）

### RAGAS 完整结果（Faithfulness + Correctness）

| 配置 | Recall@K | Faithfulness（新 / 旧）| Correctness（新 / 旧）|
|---|---:|---|---|
| `graph_naive`  | 0.961 | **0.626** / 旧 0.147 ↑ +0.48 | **0.667** / 旧 0.664 ≈ |
| `graph_local`  | 0.942 | **0.629** / 旧 0.211 ↑ +0.42 | **0.651** / 旧 0.648 ≈ |
| `graph_global` | 0.936 | **0.614** / 旧 0.083 ↑ +0.53 | **0.633** / 旧 0.675 ↓ |
| `graph_hybrid` | 0.941 | **0.668** / 旧 0.110 ↑ +0.56（见下注）| **0.683** / 旧 0.653 ↑（见下注） |
| `graph_mix`    | 0.970 | **— / 旧 0.110**（见下注）| **— / 旧 0.640**（见下注） |

⚠️ **RAGAS 数据缺口警告**：
- `graph_mix`：**所有 60 trial 的 Faithfulness/Correctness 全为 None**（judge 失败）
- `graph_hybrid`：60 trial 中 **33 faith / 32 corr 有值**，27 条判定失败

大概率原因：hybrid 合并 local+global、mix 合并 naive+hybrid，聚合 context 结构更复杂，DeepSeek-chat 作 judge 时 JSON 格式解析失败累积触发 RAGAS 重试上限。不是 bench 本身的问题（bench 那边 0 errors）。**Recall@K 数据对这两个 config 完全可信**；Correctness/Faithfulness 需要重跑 RAGAS 或换更稳的 judge。

### 关键发现

1. **Faithfulness 全面翻盘**（0.08-0.21 → 0.61-0.67）：parser 修好后 RAGAS 能看到真实 `crud-*` 来源 chunk，校验"答案陈述是否来自 context"不再误判。旧数据所有 graph config Faithfulness 都在 0.2 以下是**评分系统幻觉**（context 就是一坨 "graph_rag:mode" 占位符），不是 Graph RAG 本身不行。
2. **Correctness 小幅波动** 未显著上升：从 0.64-0.68 → 0.63-0.68，仅 graph_hybrid 从 0.653 → 0.683（+3 pts）。即 **Graph RAG 的生成质量对 parser 修复不敏感**——LLM 拿到的 context 内容其实没变（之前错在 metadata.source 字段，raw content 仍被喂给 LLM 了）。
3. **vs 非-graph（首轮数据）综合排行**：
   - Correctness：`agentic_grading` 0.702 🥇 > `graph_hybrid` 0.683 🥈 > `off` 0.679 🥉 > ...
   - Faithfulness（single_hop 最严格场景）：`graph_hybrid` 0.743 🏆 > `agentic_full` 0.730 > ...
   - **结论**：agentic_grading 仍是跨类别 Correctness 冠军；graph_hybrid 是 single_hop faithfulness 冠军；没有绝对赢家，**按场景选档**

### 文件

- [`graph-rerun-2026-04-23-recall-only.md`](./graph-rerun-2026-04-23-recall-only.md) — 初版仅 Recall@K
- [`graph-rerun-2026-04-23-with-ragas.md`](./graph-rerun-2026-04-23-with-ragas.md) — 含 RAGAS（部分缺口）
- [`graph-rerun-2026-04-23-run.jsonl`](./graph-rerun-2026-04-23-run.jsonl) — 300 条原始 trial
- [`graph-rerun-2026-04-23-scored.jsonl`](./graph-rerun-2026-04-23-scored.jsonl) — 带 RAGAS 分的明细（可用作 diagnosing graph_mix 全缺的原因）

---



| 文件名格式 | 内容 |
|---|---|
| `<date>-<scope>-recall-only.md` | 不含 RAGAS 的轻量报告 |
| `<date>-<scope>-with-ragas.md`  | 含 RAGAS faithfulness / correctness |
| `<date>-<scope>-run.jsonl`      | 原始 trial 记录 |
| `<date>-<scope>-scored.jsonl`   | trial + RAGAS 分明细 |

---

## 2026-04-22 · full（10 配置 × 60 queries = 600 trials）

- **范围**：全量 10 策略 × 60 query
- **时长**：bench 3h59min + RAGAS 1h17min = 5h16min
- **成本**：~$6（含构图 ~$1 + chat 600 次 + 1200 judge calls）
- **失败**：17 / 600（全部是 graph_local / graph_global 的 LightRAG timeout）

### 汇总结果

| 配置 | Recall@K | Faithfulness | Correctness | 平均延迟 | 错误 |
|---|---|---|---|---|---|
| `off`              | **0.933** | 0.606 | 0.679 | 7.08s  | 0 |
| `multi_query`      | 0.921 | 0.590 | 0.625 | 9.78s  | 0 |
| `agentic_grading`  | 0.897 | 0.583 | **0.702** 🥇 | 10.36s | 0 |
| `agentic_rewrite`  | 0.906 | 0.594 | 0.669 | 12.76s | 0 |
| `agentic_full`     | 0.918 | 0.576 | 0.665 | 14.97s | 0 |
| `graph_naive`      | 0.000 ⚠️ | 0.147 | 0.664 | 7.83s  | 0 |
| `graph_local`      | 0.230 ⚠️ | 0.211 | 0.648 | 38.45s | 8 |
| `graph_global`     | 0.113 ⚠️ | 0.083 | 0.675 | 31.29s | 8 |
| `graph_hybrid`     | 0.000 ⚠️ | 0.110 | 0.653 | 21.66s | 1 |
| `graph_mix`        | 0.000 ⚠️ | 0.110 | 0.640 | 22.06s | 0 |

### 🚨 重要警告：Graph RAG 的 Recall@K 数字不可信

**问题**：LightRAG 1.4.x 返回的 context 格式是：
```
Knowledge Graph Data (Entity):
```json
{"entity": "...", "type": "..."}
```
```
而不是我们 `graph_rag._split_by_sources` 匹配的 `---Sources---` markdown table 格式。结果：

| graph config | 真实 `crud-*` source 数 | `graph_rag:*` 伪 source 数 |
|---|---|---|
| graph_naive  |  **0** | 57 |
| graph_local  | 20 | 40 |
| graph_global |  5 | 43 |
| graph_hybrid |  **0** | 58 |
| graph_mix    |  **0** | 57 |

- `graph_local` 0.230 Recall 的来源是**那 8 条 timeout 后降级到 classical 的 trial**，不是真的 graph retrieval
- `graph_naive / hybrid / mix` 基本完全没解析到真实 source → 全部算 None 或 0

**结论**：本次评测对 **Graph RAG 的检索质量无效**。Correctness 和 Faithfulness 仍部分可信（RAGAS 不依赖 refs），但 Recall@K 必须修 parser 后重跑。

### 分类下钻 · 按 Correctness 选冠军

| 类别 | n | 冠军配置 | Correctness | 相对 off 提升 |
|---|---|---|---|---|
| `single_hop`       | 15 | **graph_global** | 0.825 | +5.7% vs off(0.768) |
| `multi_hop_2`      | 15 | **agentic_grading** / agentic_rewrite | 0.686 | +1.0% vs off(0.679) |
| `multi_hop_3`      | 15 | **agentic_grading** | 0.670 | +4.2% vs off(0.643) |
| `partial_context`  | 10 | **agentic_grading** | 0.676 | +1.3% vs off(0.667) |
| `kb_absent`        |  5 | **graph_local** / agentic_grading | 0.647 | — (off 0.547) |

### 关键发现

1. **`agentic_grading` 是跨类别最稳的赢家**——5 个类别中 4 个拿到或接近冠军，综合 Correctness 0.702 全场最高
2. **`off`（classical RAG）已经非常强**——Recall@K 0.933，Correctness 0.679，并不落后太多；延迟最低 7.08s
3. **Multi-Query 本次意外落败**——Correctness 0.625 < off 的 0.679，且延迟多 2.7s。可能原因：CRUD-RAG 的 query 都是完整句式，Multi-Query 生成的 variants 反而引入噪声
4. **Agentic 三档并非单调递增**：grading(0.702) > rewrite(0.669) > full(0.665)——**full 档的 hallucination check 没给 correctness 加分**，反而可能因为额外的 LLM 交互引入偏差（或者 CRUD query 本来就很"硬"，不太需要 hallucination check）
5. **`agentic_full` 在 single_hop 的 Faithfulness 最高 (0.730)**——这是 CRAG 设计的本意（防止编造），但代价是延迟最高 14.97s
6. **`graph_global` 在 single_hop Correctness 惊艳（0.825）**——这唯一一个 graph config 在 single-hop 的 Recall 也拿到了 1.000（不是解析失败？需要进一步查）
7. **Graph RAG 延迟代价大**：graph_local 38.45s、graph_global 31.29s，是 off 的 4-5 倍。加上现在 timeout 错误率 13%（8/60），生产环境不可用
8. **`kb_absent`（5 条）场景数据太少**无法下结论；但 agentic_full 的 Faithfulness 0.000 值得关注——hallucination check 判所有都"不可信"反而拉低分数

### 待办（P0）

- [ ] 修 `backend/app/services/graph_rag.py::_split_by_sources`，适配 LightRAG 1.4.x 的 `Knowledge Graph Data (Entity):` + JSON blocks 格式；增加一个 fallback 把 json 里的 `file_path` 字段提取出来作为 source
- [ ] 修完后**仅重跑 5 个 graph_* 配置的 60 条**（~30 min，~$0.5），不必重跑其他 5 个 non-graph 配置（数据已存档）
- [ ] 考虑把 `use_reranker` 也作为一个维度：当前全部开启，可能对 graph_* 不公平（LightRAG 返回的 Knowledge Graph entity 不应被 CrossEncoder reranker 按"文档相关性"重排）
- [ ] 对 graph_* 的超时（8 次 / 60）：把 `graph_rag_retrieve` 的 timeout 从 15s 调到 30s，或在前端增加一个 graph-ready 提示

### 文件

- [full-2026-04-22-with-ragas.md](./full-2026-04-22-with-ragas.md) — 完整报告（推荐首读）
- [full-2026-04-22-run.jsonl](./full-2026-04-22-run.jsonl) — 600 条原始 trial
- [full-2026-04-22-scored.jsonl](./full-2026-04-22-scored.jsonl) — trial + RAGAS 分

---

## 2026-04-22 · smoke（3 配置 × 5 queries = 15 trials）

- **范围**：`off` / `multi_query` / `agentic_grading` 三档 × single_hop 5 条
- **目的**：验证 SSE 解析 + 档位切换 + RAGAS judge 全链路通畅
- **结论**：链路通畅；但仅 single_hop，无法下 RAG 能力结论（已被上面的 full run 替代）

文件：
- [smoke-2026-04-22-with-ragas.md](./smoke-2026-04-22-with-ragas.md)
- [smoke-2026-04-22-recall-only.md](./smoke-2026-04-22-recall-only.md)
- [smoke-2026-04-22-run.jsonl](./smoke-2026-04-22-run.jsonl)
- [smoke-2026-04-22-scored.jsonl](./smoke-2026-04-22-scored.jsonl)
