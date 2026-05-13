"""Solo 模式的工具集合（薄包装层）。

约定：
- 每个 @tool 只做"现有能力 → LangChain Tool"的薄包装，不放业务逻辑。
- 工具描述（docstring）必须明确"用途"和"何时调用"——Planner 依赖这段文本决策。
- 输出字符串，超长时内部截断为约 4KB，避免把上下文撑爆。
- 失败时返回带"[ERROR] ..."前缀的字符串而不是抛异常，让 Planner 能看到并恢复。
"""

from __future__ import annotations

import asyncio
import logging

from langchain_core.tools import tool

logger = logging.getLogger(__name__)

_MAX_TOOL_RESULT_CHARS = 4000


def _truncate(text: str, limit: int = _MAX_TOOL_RESULT_CHARS) -> str:
    if text is None:
        return ""
    text = str(text)
    if len(text) <= limit:
        return text
    return text[:limit] + f"\n\n...[truncated, total {len(text)} chars]"


# ---------------------------------------------------------------------------
# 1. 知识库语义检索
# ---------------------------------------------------------------------------

@tool
def search_knowledge_base(query: str) -> str:
    """在本地项目知识库中进行语义检索，返回与 query 最相关的文档片段。

    用途：
      当用户问题涉及项目内部文档内容、私有资料、需要查找具体片段时调用。
    何时调用：
      - 用户提到"文档里""知识库里""项目里"等表述
      - 问题涉及具体名词、术语，本地 KB 可能有
      - 可以用不同角度的 query 多次调用，提高召回
    参数:
      query: 检索语句（改写过的更精确表达优于用户原始口语）
    """
    try:
        from app.services.rag_service import get_rag_service

        rag = get_rag_service()
        if not rag.is_ready():
            return "[ERROR] 知识库未就绪——Embedding 模型尚未加载。请在后台管理中加载 Embedding 模型后重试。"

        retriever = rag.get_retriever(use_reranker=True)
        docs = retriever.invoke(query)
        if not docs:
            return f"知识库中未检索到与「{query}」相关的内容。"

        parts = []
        for i, doc in enumerate(docs, 1):
            fname = doc.metadata.get("original_filename", "未知文件")
            snippet = doc.page_content.strip()
            parts.append(f"[{i}] 来源: {fname}\n{snippet}")
        return _truncate("\n\n---\n\n".join(parts))
    except Exception as e:
        logger.error(f"[solo/search_knowledge_base] failed: {e}", exc_info=True)
        return f"[ERROR] 知识库检索失败: {e}"


# ---------------------------------------------------------------------------
# 2. 知识库目录查询（Mongo 元数据）
# ---------------------------------------------------------------------------

@tool
async def query_knowledge_base_catalog(
    filter: str = "all",
    topic: str | None = None,
) -> str:
    """查询本地知识库的文档目录（Mongo 元数据，不做向量召回）。

    用途：
      回答"知识库里有哪些文档""有几个 PDF""和 X 相关的书有哪些""列出所有讲 Y 的资料"
      这类 document-level 查询。匹配单元是「整篇文档」，不是「chunk 片段」。
    何时调用：
      - 用户问"有哪些 / 有没有 / 几个 / 都是什么"等列举类
      - 用户问"和 X 相关的书籍/文档/资料是哪些"（主题维度的文档集合查询）
      - 判断某名称是否在知识库中、向量检索前先缩小范围
    参数:
      filter: 结构化过滤（可不填，默认 "all"）：
        - "all"         : 不按状态/类型过滤
        - "done"        : 仅已向量化
        - "pending"     : 仅待向量化
        - "failed"      : 仅失败
        - 形如 ".pdf" / ".txt" / ".docx" : 仅该扩展名
      topic: 主题关键词，按字面子串匹配 summary / topics / filename（可不填）：
        - 例："政治学"、"机器学习"、"红楼梦"
        - 应传**单个核心词**，而非完整句子；必要时拆成多次调用
    组合规则：
      filter 和 topic 可同时传，二者 AND 叠加（如"找 .pdf 里讲机器学习的"）。
    返回：
      匹配文档列表，每条含文件名、扩展名、chunks、状态、上传日期、
      LLM 生成的 topics 与 summary（若已生成）。
    """
    try:
        import re
        from app.models.knowledge_document import KnowledgeDocument

        query: dict = {}

        # 结构化过滤
        f = (filter or "all").strip().lower()
        if f and f != "all":
            if f in ("done", "processing", "pending", "failed"):
                query["vectorize_status"] = f
            elif f.startswith("."):
                query["extension"] = f
            else:
                return (
                    f"[ERROR] 未识别的 filter 值: {filter!r}。"
                    "可用值：all / done / pending / failed / .pdf / .txt / .docx 等。"
                )

        # 语义子串过滤（topic）：在 topics 数组 / summary / original_name 三处任一命中即可。
        # 不走 $text：MongoDB 默认 text index 不切中文词，"政治学" 匹配不上 topics 里的
        # "政治学基础"。改用 $regex 做字面子串匹配，对 10^2-10^3 量级的 collection
        # 全表扫描完全没感；大规模时再换 jieba + 预切分字段。
        t = (topic or "").strip()
        if t:
            pattern = re.escape(t)
            query["$or"] = [
                {"topics": {"$elemMatch": {"$regex": pattern, "$options": "i"}}},
                {"summary": {"$regex": pattern, "$options": "i"}},
                {"original_name": {"$regex": pattern, "$options": "i"}},
            ]

        docs = await KnowledgeDocument.find(query).to_list()
        if not docs:
            total = await KnowledgeDocument.find_all().count()
            if total == 0:
                return "知识库为空，尚无已上传的文档。"
            cond = f"filter={filter!r}" + (f", topic={topic!r}" if t else "")
            return f"没有匹配的文档（{cond}），知识库共有 {total} 个文档。"

        header_cond = f"filter={filter!r}" + (f", topic={topic!r}" if t else "")
        lines = [f"匹配的文档共 {len(docs)} 个（{header_cond}）："]
        for d in docs:
            status_zh = {
                "done": "已向量化",
                "processing": "向量化中",
                "pending": "待向量化",
                "failed": "失败",
            }.get(d.vectorize_status, d.vectorize_status)
            uploaded = d.uploaded_at.strftime("%Y-%m-%d") if d.uploaded_at else "-"
            head = (
                f"- {d.original_name} [{d.extension}] "
                f"chunks={d.chunk_count} status={status_zh} uploaded={uploaded}"
            )
            if d.topics:
                head += f"\n  topics: {', '.join(d.topics)}"
            if d.summary:
                # summary 控长 180 字，避免多文档时结果爆炸
                head += f"\n  摘要: {d.summary[:180]}"
            lines.append(head)
        return _truncate("\n".join(lines))
    except Exception as e:
        logger.error(f"[solo/query_knowledge_base_catalog] failed: {e}", exc_info=True)
        return f"[ERROR] 目录查询失败: {e}"


# ---------------------------------------------------------------------------
# 3. 联网搜索
# ---------------------------------------------------------------------------

@tool
async def search_web(query: str) -> str:
    """联网搜索，获取实时或本地知识库外的信息（基于 SerpApi）。

    用途：
      当问题涉及实时信息、新闻、知识库里不太可能有的内容时调用。
    何时调用：
      - 问题包含"最新""最近""今天""2024 / 2025 年"等时间敏感词
      - 用户明确要求联网 / 搜索
      - search_knowledge_base 未命中但问题明显指向公网信息
    参数:
      query: 搜索关键词（适度缩减为关键实体，避免完整句子）
    """
    try:
        from app.tools.web_search import web_search

        # web_search 是同步函数，在线程池执行避免阻塞 event loop
        result = await asyncio.to_thread(web_search, query)
        if not result:
            return f"联网搜索「{query}」未返回有效结果。"
        return _truncate(result)
    except Exception as e:
        logger.error(f"[solo/search_web] failed: {e}", exc_info=True)
        return f"[ERROR] 联网搜索失败: {e}"


# ---------------------------------------------------------------------------
# 4. 天气查询（走现有高德 MCP）
# ---------------------------------------------------------------------------

def _format_weather_payload(raw: str) -> str:
    """把高德 MCP 返回的 Python-list-repr-嵌-JSON 拆出来，格式化成人类 / LLM 友好的单行。

    MCP 返回结构（字符串形式）大致：
      [{'type': 'text', 'text': '{"status":"1","lives":[{"province":"北京","city":"北京市",
        "weather":"霾","temperature":"22","winddirection":"东北","windpower":"≤3",
        "humidity":"54","reporttime":"2026-04-18 21:03:32"}]}', 'id': '...'}]
    解析失败时退回原字符串（宁可让 LLM 看原始数据，也不丢数据）。
    """
    import ast
    import json as _json

    if not raw:
        return ""
    try:
        outer = ast.literal_eval(raw) if raw.lstrip().startswith("[") else None
        text_blob = None
        if isinstance(outer, list) and outer and isinstance(outer[0], dict):
            text_blob = outer[0].get("text")
        if not text_blob:
            return raw
        payload = _json.loads(text_blob)
        lives = payload.get("lives") or []
        if not lives:
            return raw
        l = lives[0]
        return (
            f"天气={l.get('weather','?')}, "
            f"温度={l.get('temperature','?')}°C, "
            f"湿度={l.get('humidity','?')}%, "
            f"风向={l.get('winddirection','?')}风, "
            f"风力={l.get('windpower','?')}级, "
            f"报告时间={l.get('reporttime','?')}"
        )
    except Exception:
        return raw


@tool
async def get_weather(city: str) -> str:
    """查询某个城市的实况天气（通过高德 MCP Server，返回实时气象数据）。

    用途：
      用户询问天气、温度、是否下雨等。**这是天气问题的权威数据源**，
      返回的结果已经是高德实况数据，**不要**再调用 search_web 交叉验证。
    何时调用：
      - 问题里出现"天气""气温""下雨""冷不冷"等关键词 + 地名
    参数:
      city: 中文地名，支持省/市/区，例如"北京"/"朝阳区"/"杭州"/"上海/浦东新区"。
    """
    try:
        from app.services.weather_service import call_weather_mcp, resolve_location

        matches = resolve_location(city)
        if not matches:
            return f"未找到「{city}」对应的地区，请确认地名是否正确。"

        # 多个同名地区并行查
        results = await asyncio.gather(
            *[call_weather_mcp(adcode) for _, adcode in matches],
            return_exceptions=True,
        )
        parts = []
        for (full_path, _), data in zip(matches, results):
            if isinstance(data, Exception):
                parts.append(f"【{full_path}】查询失败: {data}")
            else:
                parts.append(f"【{full_path}】{_format_weather_payload(str(data))}")
        return _truncate("\n".join(parts))
    except Exception as e:
        logger.error(f"[solo/get_weather] failed: {e}", exc_info=True)
        return f"[ERROR] 天气查询失败: {e}"


# ---------------------------------------------------------------------------
# 5. 深度思考元工具
# ---------------------------------------------------------------------------

@tool
def request_thinking(reason: str) -> str:
    """当当前问题需要更深入、更分步的推理时调用（元工具）。

    用途：
      切换到"深度思考"模式，让下一轮生成带有显式的分步推理过程。
    何时调用：
      - 多步数学 / 逻辑推理题
      - 代码设计或架构权衡
      - 需要细致权衡多个因素的问题
      - 仅当常规回答不足以覆盖时才调用，避免简单问题过度思考
    参数:
      reason: 一句简短中文说明为什么需要深度思考（会展示给用户）
    """
    # 实际的 need_thinking 状态位由 nodes.planner_node 在检测到该 tool_call 后设置；
    # 此处只负责返回一段给 Planner 看的提示，让它在下一轮确实按 CoT 方式作答。
    return (
        f"已进入深度思考模式（原因：{reason}）。"
        "请在下一轮回答时，先用 <thinking>...</thinking> 逐步拆解推理过程，"
        "再在 <content>...</content> 中给出最终结论。"
    )


# ---------------------------------------------------------------------------
# 导出：供 graph.py bind 给 LLM
# ---------------------------------------------------------------------------

SOLO_TOOLS = [
    search_knowledge_base,
    query_knowledge_base_catalog,
    search_web,
    get_weather,
    request_thinking,
]

SOLO_TOOLS_BY_NAME = {t.name: t for t in SOLO_TOOLS}
