"""
Multi-Query 多路召回：从不同角度生成 N 个 query 变体，并行召回后合并。

仅用于 classic 路径的 RAG 检索前置。Solo 路径由 Planner 自主多次调用
`search_knowledge_base`（天然 Multi-Query），此处不介入。

设计见 plan-doc-dir/query改写方案汇总.md §九。

- 失败软着陆：LLM 超时 / JSON 解析失败 / 空结果 → 返回空 list，调用方降级到单 query
- 用 DeepSeek-chat（非 reasoner）；temperature 稍高以增加多样性；max_tokens 给足 variants
- variant 数量硬编码 3（DEFAULT_COUNT）；调用方可覆盖，但不推荐
"""

from __future__ import annotations

import logging

import json_repair

from app.core.config import get_settings
from app.services._langsmith import get_utility_openai

logger = logging.getLogger(__name__)
settings = get_settings()

DEFAULT_COUNT = 3

# 系统 prompt 要点：
#   - 明确只生成"改写版本"，不要加内容、不要改主题
#   - 要求多样：同义改写 / 上位概念 / 下位概念 / 英文同义词
#   - 严格 JSON 输出，避免混入中文引号导致 json_repair 还要兜底
_SYSTEM_PROMPT = """\
你是 query 多样化生成器。根据用户的原始 query，生成 N 个**不同角度**的检索变体用于向量数据库检索，以提升召回完整性。

要求：
1. **不改变主题**，只换表达角度；不要加入原 query 没有的新主题。
2. 每个变体都应是独立、完整、可单独检索的短句（10-30 字）。
3. 尽量覆盖不同角度，例如：
   - 同义改写（换近义词 / 换句式）
   - 上位概念（把问的东西放到它所属的更大类别里）
   - 下位概念 / 具体实例（把问的东西展开为它可能包含的关键子项）
   - 英文同义词（若原 query 是中文）
4. **不要**加"我想知道""请问""能否告诉我"等口水话；直接就是检索语句。
5. **不要**复述原 query；原 query 会在调用侧和变体并集在一起使用。

输出 JSON：{"variants": ["变体1", "变体2", ...]}

示例：
原 query："政治学相关的书有哪些？"
输出：{"variants": ["政治哲学 国家理论 民主理论", "自由主义 保守主义 马克思主义", "political science books"]}

示例：
原 query："BGE-M3 怎么用？"
输出：{"variants": ["BGE-M3 模型加载与推理示例", "sentence-transformers 使用 BAAI/bge-m3 步骤", "BGE-M3 sparse 与 dense embedding 调用"]}"""


async def generate_variants(original_query: str, n: int = DEFAULT_COUNT) -> list[str]:
    """生成 n 个 query 变体。失败返回空 list（调用方降级为单 query）。

    绝不抛异常 —— 上层（RagService.retrieve_with_multi_query）依赖这个契约。
    """
    if not original_query or not original_query.strip():
        return []
    n = max(1, min(int(n or DEFAULT_COUNT), 8))

    try:
        client = get_utility_openai(timeout=8.0)
        resp = await client.chat.completions.create(
            model=settings.UTILITY_LLM_MODEL,
            messages=[
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": f"原 query：{original_query}\n请生成 {n} 个变体。"},
            ],
            response_format={"type": "json_object"},
            # 每个变体上限约 30 字符 ≈ 30 tokens；给 n*40 + 结构冗余够用
            max_tokens=max(120, n * 60),
            temperature=0.4,  # 略升一点温度增加多样性，但不至于跑题
        )
        raw = resp.choices[0].message.content or ""
        parsed = json_repair.loads(raw)
        if not isinstance(parsed, dict):
            logger.warning(
                f"[MultiQuery] Unexpected json type={type(parsed).__name__}, fallback empty"
            )
            return []

        raw_variants = parsed.get("variants") or []
        if not isinstance(raw_variants, list):
            return []

        # 清洗：strip、去空、去重（保持顺序）、去等同于原 query 的
        seen: set[str] = set()
        original_stripped = original_query.strip()
        variants: list[str] = []
        for v in raw_variants:
            if not isinstance(v, str):
                continue
            v = v.strip()[:80]     # 上限 80 字符防爆
            if not v or v == original_stripped or v in seen:
                continue
            seen.add(v)
            variants.append(v)
            if len(variants) >= n:
                break

        return variants

    except Exception as e:
        logger.warning(f"[MultiQuery] generate_variants failed: {type(e).__name__}: {e}")
        return []


def rrf_fuse(
    ranked_lists: list[list],
    key_fn,
    k: int = 60,
    top_n: int = 4,
) -> list:
    """Reciprocal Rank Fusion：多个排序好的候选列表合并为单一排序。

    - ranked_lists：每个 list 内元素按相关度从高到低排列
    - key_fn(item) → hashable 键，用于跨列表去重（一般是 chunk_id / 内容指纹）
    - k=60：RRF 标准超参，与 Qdrant 内部 hybrid 融合默认值一致
    - 返回融合后按 fused_score 降序的 top_n 个原始元素

    公式：fused_score(d) = Σ 1 / (k + rank_i(d))  ，rank 从 1 开始
    """
    scores: dict = {}
    first_item: dict = {}  # key → 代表 item（第一个出现的）
    for ranked in ranked_lists:
        for rank, item in enumerate(ranked, start=1):
            try:
                key = key_fn(item)
            except Exception:
                continue
            if key is None:
                continue
            scores[key] = scores.get(key, 0.0) + 1.0 / (k + rank)
            first_item.setdefault(key, item)

    ordered_keys = sorted(scores.keys(), key=lambda x: scores[x], reverse=True)
    return [first_item[k_] for k_ in ordered_keys[:top_n]]
