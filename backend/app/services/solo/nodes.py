"""Solo 模式 LangGraph 节点实现。

节点：
  - classify_complexity_node：首轮分类用户问题是否需要深度思考，写 state.need_thinking。
  - planner_node：绑定工具的 LLM 调用，产生 AIMessage（可能含 tool_calls）。
  - tool_node：由 langgraph.prebuilt.ToolNode 直接使用，见 graph.py。
  - should_continue：条件边，判断是否还有 tool_calls 要执行。
"""

from __future__ import annotations

import logging

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

from app.core.config import get_settings
from app.services.solo.complexity import classify_complexity
from app.services.solo.state import SoloState
from app.services.solo.tools import SOLO_TOOLS

logger = logging.getLogger(__name__)
settings = get_settings()


# ---------------------------------------------------------------------------
# LLM 工厂（与 ChatService._get_llm 保持一致的模型路由规则）
# 额外参数 enable_thinking：仅当模型是 DeepSeek 时生效——通过 extra_body 开启原生
# 思考模式，响应 chunk 会带 reasoning_content 字段，由 events.py 翻译成 reasoning SSE 事件。
# ---------------------------------------------------------------------------

def _build_llm(model_name: str, enable_thinking: bool = False) -> ChatOpenAI:
    """根据 model_name 返回带 streaming 的 ChatOpenAI 实例。"""
    if model_name.startswith("moonshot") or model_name.startswith("kimi"):
        return ChatOpenAI(
            api_key=settings.MOONSHOT_API_KEY,
            base_url="https://api.moonshot.cn/v1",
            model=model_name,
            streaming=True,
        )
    if model_name.startswith("deepseek"):
        kwargs = dict(
            api_key=settings.DEEPSEEK_API_KEY,
            base_url="https://api.deepseek.com",
            model="deepseek-chat",
            streaming=True,
        )
        if enable_thinking:
            # DeepSeek 原生思考模式：模型保持 deepseek-chat，通过 extra_body 开启；
            # 响应 delta 会额外带 reasoning_content，LangChain 把它透传到 additional_kwargs。
            kwargs["extra_body"] = {"thinking": {"type": "enabled"}}
        return ChatOpenAI(**kwargs)
    if model_name.startswith("qwen"):
        return ChatOpenAI(
            api_key=settings.DASHSCOPE_API_KEY,
            base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
            model=model_name,
            streaming=True,
        )
    # 未知模型降级到 Kimi
    return ChatOpenAI(
        api_key=settings.MOONSHOT_API_KEY,
        base_url="https://api.moonshot.cn/v1",
        model="kimi-k2-0905-preview",
        streaming=True,
    )


# ---------------------------------------------------------------------------
# classify_complexity_node：在图的第一跳给 planner 提供 need_thinking hint
# ---------------------------------------------------------------------------

async def classify_complexity_node(state: SoloState) -> dict:
    """首轮分类用户问题是否需要深度思考。

    - 只在 iteration==0 执行，后续回合沿用首轮判定，不重复开销
    - 从 state.messages 里找最后一条 HumanMessage 作为待分类文本
    - 分类失败 / 超时 / 找不到 user 消息 → need_thinking=False（快速路径）
    """
    if int(state.get("iteration") or 0) > 0:
        return {}

    user_text = ""
    for msg in reversed(state["messages"]):
        if isinstance(msg, HumanMessage):
            content = msg.content
            if isinstance(content, str):
                user_text = content.strip()
            break

    if not user_text:
        logger.info("[solo/complexity] no user message found, skip classification")
        return {"need_thinking": False}

    result = await classify_complexity(user_text)
    return {"need_thinking": bool(result.get("complex"))}


# ---------------------------------------------------------------------------
# 工具网关：按运行时状态动态挑选真正可用的工具
# ---------------------------------------------------------------------------

# 工具简介行：用于在 system prompt 顶部动态枚举可用工具。
# 刻意只放一行描述，让 prompt 更紧凑；详细触发条件由每个工具自身的 docstring（即 OpenAI schema 的 description）承担。
_TOOL_ONE_LINERS = {
    "search_knowledge_base": "search_knowledge_base(query): 在本地项目知识库中语义检索文档内容",
    "query_knowledge_base_catalog": "query_knowledge_base_catalog(filter): 查询本地知识库的文档目录（列出有哪些文件）",
    "search_web": "search_web(query): 联网搜索实时或公网信息",
    "get_weather": "get_weather(city): 查询某城市实况天气",
    "request_thinking": "request_thinking(reason): 切换到深度思考模式（仅在复杂推理题时调用）",
}


def _available_tools():
    """根据后端当前能力过滤 SOLO_TOOLS。

    规则：
      - search_knowledge_base 依赖 Embedding 模型 + 向量库；RagService 未 initialize 时剔除，
        避免 LLM 看到一个注定返回 [ERROR] 的工具 schema，造成无意义的 tool_call 轮次。
      - query_knowledge_base_catalog 只查 Mongo 元数据，与 embedding 无关，始终保留。
      - 其它工具始终可用。
    """
    try:
        from app.services.rag_service import get_rag_service
        rag_ready = get_rag_service().is_ready()
    except Exception as e:
        logger.warning(f"[solo] could not probe rag readiness: {e}")
        rag_ready = False

    available = []
    for t in SOLO_TOOLS:
        if t.name == "search_knowledge_base" and not rag_ready:
            continue
        available.append(t)
    return available


def _build_system_prompt(tools, need_thinking: bool) -> str:
    """把工具枚举段动态生成，再拼上固定的行为守则和示例。"""
    tool_lines = []
    for i, t in enumerate(tools, 1):
        tool_lines.append(f"{i}. {_TOOL_ONE_LINERS.get(t.name, t.name)}")
    tools_block = "\n".join(tool_lines)

    # 当 search_knowledge_base 不可用时，加一段明确提示，防止 LLM 试图"凭记忆"回答本该查 RAG 的问题
    rag_unavailable_note = ""
    tool_names = {t.name for t in tools}
    if "search_knowledge_base" not in tool_names:
        rag_unavailable_note = (
            "\n## 本次会话的特殊限制\n\n"
            "本地知识库的**语义检索**工具（search_knowledge_base）当前不可用"
            "（Embedding 模型未加载）。如果用户问题涉及具体文档内容，请如实告知"
            "「语义检索暂不可用」，并建议用户去后台管理中加载 Embedding 模型，"
            "或者用 query_knowledge_base_catalog 至少列出文档目录。"
            "**严禁**编造知识库里的具体文档内容。\n"
        )

    base = f"""你是一个具备自主决策能力的智能助手（Solo 模式）。你可以使用以下工具来获取信息或执行动作：

{tools_block}
{rag_unavailable_note}
## 非常重要 —— 调用工具的正确方式"""
    return base + _SYSTEM_PROMPT_TAIL + (THINKING_HINT if need_thinking else "")


# ---------------------------------------------------------------------------
# System Prompt（固定部分；工具枚举和 RAG 不可用提示由 _build_system_prompt 动态拼）
# ---------------------------------------------------------------------------

_SYSTEM_PROMPT_TAIL = """

当你判断需要使用某个工具时，**必须通过 function calling 真正发起 tool_call**（即 assistant 消息里带 tool_calls 字段），**不要**只是在文字里写"我将调用 X"却没有实际发起调用——那样后台拿不到数据，你也就无法回答。

你可以在同一条 assistant 消息里同时输出文字内容（例如下面的 `<intent>` / `<plan>`）**和** tool_calls，这两者不冲突。

## 工作方式

### 第 1 轮（收到用户问题）

1. 先输出两段结构化说明（这是文字内容的一部分）：

```
<intent>
一两句话说明你对用户问题的理解，问题类型属于什么。
</intent>
<plan>
一两句话说明你接下来打算做什么：要调用哪些工具、为什么；或者直接回答。
</plan>
```

2. 紧接着：
   - **如果需要信息** → 在同一条消息里发起真正的 tool_calls（function calling）。
   - **如果不需要工具** → 直接给出下面"最终答案格式"的内容。

### 第 2 轮及以后（工具已返回结果）

- 判断信息是否够：
  - 还缺信息 → 继续发起新的 tool_calls（可以换关键词或换工具）。
  - 已经够 → 按下面的"最终答案格式"输出。

### 最终答案格式

```
<content>
面向用户的最终回答正文。如果引用了 search_knowledge_base 的结果，用 <ref>N</ref> 标注（N 是 1 开始的来源编号）。
</content>
<recommend>
<rec>相关追问 1</rec>
<rec>相关追问 2</rec>
</recommend>
```

注意：最终答案必须用 `<content>...</content>` 包起来。即使内容很简短（比如"知识库里共有 3 个文件：xxx"），也要包在 `<content>` 里。

## 工具选择优先级（重要，按此顺序判断）

不同问题用不同工具，**选一个最专用的，拿到数据后就停**：

| 问题类型 | 使用工具 | 不要用 |
|---|---|---|
| 天气/气温/下雨/湿度 + 地名 | `get_weather`（高德实时数据，已含温度/湿度/风向/报告时间，**视为权威**） | 绝不要再调 `search_web` 交叉验证 |
| "我有哪些文档 / 几个 PDF" 目录型 | `query_knowledge_base_catalog`（Mongo 元数据，即是真相） | 不要调语义检索 |
| 本地文档内容检索 | `search_knowledge_base` | 除非返回空，才考虑 `search_web` 补充 |
| 实时新闻 / 时间敏感信息 | `search_web`（知识库一定没有的公网数据） | — |

## 决策原则

- 能用工具确认事实时，不要凭空猜测；但简单闲聊、通用常识可以直接回答。
- **拿到足够回答用户问题的数据就立即 `<content>` 作答**——不要"保险起见再查一次"。
- **同一个工具在单次对话里最多调用 2 次**，且两次的参数必须显著不同（换 query / 换城市），否则立即停下作答。
- **不同工具之间不做交叉验证**：`get_weather` 返回的天气就是最新的，`query_knowledge_base_catalog` 返回的目录就是真实的，不需要 `search_web` 再查。
- 深度思考（request_thinking）谨慎使用，仅用于真正复杂的推理场景。
- 工具调用失败（返回以 [ERROR] 开头）时，告诉用户原因，不要伪造结果。

## 查询改写纪律（调用检索类工具前先做）

调用 `search_knowledge_base` / `search_web` 等检索类工具时，**传入的 query 必须是一个独立、完整、明确的检索式**，不要直接把用户的原话扔进去：

- **代词 / 省略必须解引用**：用户问"它怎么装？"而上一轮在讨论 LangGraph，那你的 `search_knowledge_base(query="LangGraph 安装方法")`，而不是 `query="它怎么装"`。
- **太短 / 口语化的要补全**：用户问"再说说"，应该结合上下文补成具体主题，比如 `query="LangGraph StateGraph 节点定义"`，而不是 `query="再说说"`。
- **主题 / 分类型查询优先走目录**：用户问"和 X 相关的书有哪些"，直接调 `query_knowledge_base_catalog(topic="X")`，不要用 `search_knowledge_base`（那是 chunk 级语义检索，会漏书）。
- **保持意图不变**：改写只是让表达更适合检索，**不要添加用户没问的新话题**。
- **原样够清晰就别改**：如果用户已经给出一句独立可检索的话（如"LangGraph StateGraph 节点怎么定义？"），直接用原样，不要强行改写。

## 严禁虚构

你**绝对不允许**在没有实际拿到工具返回结果的情况下，编造任何事实性数据（文件数量、文件名、天气数据、网页摘要等）。
一旦你决定"需要工具才能回答"，就必须真的发起 function call；在拿到工具的真实返回之前，**不要**用 <content> 输出任何数字/具体内容。
如果工具调用失败，如实告诉用户"查询失败"，不要猜测结果。

## 示例（抽象示意，具体数据以工具返回为准，不要照搬示例里的占位文字）

用户问："知识库里有几个文件？"

第 1 轮你的输出（文字 + 真实 tool_calls 同时产生）：
- 文字：`<intent>用户想知道本地知识库中已有多少文件。</intent><plan>需要调用 query_knowledge_base_catalog 获取真实目录后再统计。</plan>`
- tool_calls：`[{"name": "query_knowledge_base_catalog", "args": {}}]`  ← 必须真发起！

第 2 轮（工具已返回真实目录数据后）你的输出：
- 文字：`<content>…（基于工具返回的真实结果如实回答，不要编造）…</content><recommend><rec>…</rec></recommend>`
- tool_calls：无
"""


THINKING_HINT = (
    "\n\n## 深度思考已启用\n\n"
    "用户当前问题需要分步推理。下一轮回答时请先在 <thinking>...</thinking> 中"
    "展示完整的推理过程，再在 <content>...</content> 中给出最终答案。"
)


# ---------------------------------------------------------------------------
# 目录型 query 规则识别（零 LLM 调用，用于 planner 注入强路由 hint）
# ---------------------------------------------------------------------------

# "列举"语义的动词/量词/疑问词
_CATALOG_LIST_VERBS = (
    "有哪些", "哪些", "几个", "多少", "多少个", "列出", "都有什么", "都是什么",
    "收录", "包含了", "包含哪", "存了哪",
)

# 指代知识库文档的名词
_CATALOG_DOC_REFS = (
    "文档", "文件", "书", "资料", "pdf", "PDF", "知识库", "项目里",
    "库里", "库内", "kb", "KB", "笔记",
)

# "与 X 相关的 <文档/书>" 这种主题型请求的关键片段
_CATALOG_TOPIC_PATTERNS = (
    "相关的书", "相关的文档", "相关的资料", "相关的 pdf", "相关的PDF",
    "讲过的", "提到的",
)


def _detect_catalog_intent(user_text: str) -> tuple[bool, str]:
    """纯关键词规则：判断用户 query 是否是目录型查询（document-level enumeration）。

    False-positive 代价：多一条路由 hint，planner 还是会综合判断。
    False-negative 代价：靠基础 prompt 软引导 catch。
    所以规则偏**保守**——必须同时含列举动词 + 文档指代，或命中显式主题模板。

    返回 (is_catalog, matched_reason)；未命中时 reason 为空串。
    """
    if not user_text:
        return False, ""

    txt = user_text.lower()
    # 把中文里也常见的标点归一，避免 "知识库里" 和 "知识库 里" 差异
    compact = txt.replace(" ", "").replace(",", "").replace("，", "")

    # 规则 A：列举动词 + 文档指代，同现
    has_list_verb = next((v for v in _CATALOG_LIST_VERBS if v in compact), "")
    has_doc_ref = next((r for r in _CATALOG_DOC_REFS if r.lower() in compact), "")
    if has_list_verb and has_doc_ref:
        return True, f"list_verb={has_list_verb!r}+doc_ref={has_doc_ref!r}"

    # 规则 B：显式主题模板
    for pattern in _CATALOG_TOPIC_PATTERNS:
        if pattern in compact:
            return True, f"topic_pattern={pattern!r}"

    return False, ""


_CATALOG_ROUTING_HINT = """

## ⚠️ 本轮规则路由提示（由前置关键词检测触发）

用户问题疑似**目录型查询**（document-level，关心"哪些文档 / 哪些书"而非 chunk 级内容）。
本轮请**优先**调用 `query_knowledge_base_catalog`（Mongo 元数据，含 summary / topics），
**不要**先调 `search_knowledge_base`（chunk 级语义检索对目录型问题会漏书）。

- 若用户问"和 X 相关的书/文档/资料" → `query_knowledge_base_catalog(topic="X")`
- 若用户问"有哪些 PDF / 几个文件" → `query_knowledge_base_catalog(filter=".pdf")` 或 `filter="all"`
- 若 `query_knowledge_base_catalog` 返回已足够信息就立即作答，不要再调 `search_knowledge_base`
"""


# ---------------------------------------------------------------------------
# planner_node
# ---------------------------------------------------------------------------

async def planner_node(state: SoloState) -> dict:
    """调用 LLM，返回一条新的 AIMessage（可能含 tool_calls）。

    - 每轮都重建 system message（内容可能随 need_thinking 变化）。
    - 从 messages 里扫描：若上一轮 planner 调用过 request_thinking，则 need_thinking=True。
    """
    model_name = state.get("model_name") or "kimi-k2-0905-preview"
    need_thinking = bool(state.get("need_thinking"))
    iteration = int(state.get("iteration") or 0) + 1

    # 扫描历史消息检测 request_thinking 调用（若 state 里尚未置位）
    if not need_thinking:
        for msg in state["messages"]:
            if isinstance(msg, AIMessage) and getattr(msg, "tool_calls", None):
                for tc in msg.tool_calls:
                    if tc.get("name") == "request_thinking":
                        need_thinking = True
                        break
            if need_thinking:
                break

    # 运行时按能力动态构建工具清单和 system prompt，保证 LLM 看到的 schema
    # 和实际可用工具一致（Embedding 未加载时不暴露 search_knowledge_base）
    tools = _available_tools()
    system_content = _build_system_prompt(tools, need_thinking)

    # 首轮（iteration==0）对用户最新 HumanMessage 做一次纯规则的目录型 query 检测。
    # 命中则往 system prompt 末尾注入强路由 hint，让 Planner 优先调用
    # query_knowledge_base_catalog 而不是 search_knowledge_base。
    # 只首轮注入，避免 ReAct 后续回合里反复触发相同路由指令。
    is_first_round = int(state.get("iteration") or 0) == 0
    latest_user_text = ""
    catalog_hit = False
    catalog_reason = ""
    if is_first_round:
        for msg in reversed(state["messages"]):
            if isinstance(msg, HumanMessage):
                c = msg.content
                if isinstance(c, str):
                    latest_user_text = c.strip()
                break
        catalog_hit, catalog_reason = _detect_catalog_intent(latest_user_text)
        if catalog_hit:
            logger.info(f"[solo/planner] catalog routing hint injected: {catalog_reason}")
            system_content = system_content + _CATALOG_ROUTING_HINT

    # DeepSeek 原生思考模式：仅当 need_thinking=True 且模型是 DeepSeek 时启用
    # （Kimi 模型不支持 reasoning_content，启用无效果还浪费参数）
    use_native_thinking = need_thinking and model_name.startswith("deepseek")
    llm = _build_llm(model_name, enable_thinking=use_native_thinking).bind_tools(tools)

    # 把 system message 拼在最前，历史消息保持不变
    full_messages = [SystemMessage(content=system_content), *state["messages"]]

    logger.info(
        f"[solo/planner] iter={iteration} model={model_name} "
        f"need_thinking={need_thinking} native_thinking={use_native_thinking} "
        f"history_len={len(state['messages'])} tools={[t.name for t in tools]}"
    )
    response = await llm.ainvoke(full_messages)

    # 诊断日志：看清楚 planner 这一轮到底产出了什么
    content_preview = (response.content or "")[:300].replace("\n", " | ")
    tool_calls_summary = [
        {"name": tc.get("name"), "args_keys": list((tc.get("args") or {}).keys())}
        for tc in (getattr(response, "tool_calls", None) or [])
    ]
    logger.info(
        f"[solo/planner] output: content_len={len(response.content or '')} "
        f"tool_calls={tool_calls_summary} content_preview={content_preview!r}"
    )

    # 兜底：若 LLM 既没输出 tool_calls，又没输出任何 <content>...</content>
    # （只输出了 <intent>/<plan>/闲聊文字），说明它把"打算做什么"写成了文字但没真的调用工具。
    # 立即在同一节点再做一次 LLM 调用，**强制**它发起真正的 function call，
    # 而不允许它"用 <content> 直接给答案"——因为它本没拿到数据，给出的只会是幻觉。
    import re as _re
    has_content_block = bool(_re.search(r"<content>", response.content or "", _re.IGNORECASE))

    # 首轮决策的事后日志采集：写入 logs/catalog_intent.jsonl 用于离线分析
    # 规则触发率 / 命中场景 Planner 是否按路由调用 / 漏检场景 Planner 自主调用了啥
    if is_first_round:
        try:
            from app.services.solo.catalog_intent_log import log_detection
            log_detection(
                query=latest_user_text,
                is_catalog=catalog_hit,
                reason=catalog_reason,
                planner_tools=[tc["name"] for tc in tool_calls_summary],
                planner_has_content=has_content_block,
                model_name=model_name,
            )
        except Exception as _log_e:
            logger.debug(f"[solo/planner] catalog log failed: {_log_e}")
    if not response.tool_calls and not has_content_block and (response.content or "").strip():
        # 尝试从 <plan>...</plan> 里抽出它自己提到的工具名，让 nudge 更有针对性
        plan_text = ""
        plan_match = _re.search(r"<plan>([\s\S]*?)</plan>", response.content or "", _re.IGNORECASE)
        if plan_match:
            plan_text = plan_match.group(1).strip()
        mentioned_tools = [
            t.name for t in tools
            if t.name in (plan_text + (response.content or ""))
        ]
        logger.warning(
            f"[solo/planner] LLM emitted planning text without real tool_calls; "
            f"mentioned_tools={mentioned_tools}; nudging for real function call."
        )

        from langchain_core.messages import HumanMessage as _HM
        if mentioned_tools:
            tool_hint = "、".join(mentioned_tools)
            refuse_template = (
                f"<content>抱歉，我在本次回答中未能成功调用 {tool_hint} 工具，"
                f"为避免向你提供编造的答案，暂不直接作答。你可以点击「重新生成」重试，"
                f"或切换到 DeepSeek 模型后再试。</content>"
            )
            nudge_body = (
                f"【系统提醒】你上一条消息声称要调用工具（提到：{tool_hint}），"
                f"但并没有真正发起 function call——assistant 消息的 tool_calls 字段是空的，"
                f"后台因此拿不到任何真实数据。\n\n"
                f"现在**必须**从以下两个选项中选一个，不要输出其它内容：\n"
                f"A) 通过 tool_calls 字段真正发起 function call 调用 {tool_hint}（不要文字描述，直接发起调用）。\n"
                f"B) 如果你确实无法发起调用，**一字不改**地输出以下拒绝模板（不要加任何 <intent>/<plan>/前缀/解释）：\n"
                f"   {refuse_template}\n\n"
                f"严禁用 <content> 给出没有工具返回数据支撑的事实性回答——那会被视为幻觉。"
            )
        else:
            nudge_body = (
                "【系统提醒】你上一条消息是规划性/过渡性文字，既没有发起 function call，"
                "也没有用 <content>...</content> 给出最终答案。\n"
                "请立即选择：\n"
                "A) 如果回答用户问题需要外部信息，通过 tool_calls 字段真正发起 function call（不要只描述）。\n"
                "B) 如果这是常识/闲聊类问题，用 <content>...</content> 直接作答。\n"
                "严禁在没有工具返回数据的情况下编造事实。"
            )

        nudge_messages = [
            SystemMessage(content=system_content),
            *state["messages"],
            response,
            _HM(content=nudge_body),
        ]
        try:
            response2 = await llm.ainvoke(nudge_messages)
            content2_preview = (response2.content or "")[:200].replace("\n", " | ")
            tool_calls2 = [tc.get("name") for tc in (getattr(response2, "tool_calls", None) or [])]
            logger.info(
                f"[solo/planner] nudge retry: content_len={len(response2.content or '')} "
                f"tool_calls={tool_calls2} preview={content2_preview!r}"
            )

            # 记录幻觉嫌疑（nudge 已经通过 refuse_template 给模型提供了"合法拒绝"路径，
            # 模型仍然不用 template 而输出 <content> + 没 tool_call、且原 plan 点名了工具 →
            # 大概率是在凭空编）。但不再用 safe_msg 直接替换——因为直接构造的 AIMessage 不
            # 会产生 on_chat_model_stream 事件，前端收不到。端点层有空内容兜底负责最终保底。
            r2_has_content = bool(_re.search(r"<content>", response2.content or "", _re.IGNORECASE))
            if mentioned_tools and not response2.tool_calls and r2_has_content:
                logger.warning(
                    "[solo/planner] HALLUCINATION SUSPECTED: model refused to call the "
                    f"promised tool ({mentioned_tools}) and emitted <content> anyway. "
                    "Letting it through; endpoint-level empty-content fallback will "
                    "catch the nothing-at-all case."
                )

            # 保留原 response（给前端看到 intent/plan 流），再附上 response2
            return {
                "messages": [response, response2],
                "need_thinking": need_thinking,
                "iteration": iteration,
            }
        except Exception as e:
            logger.error(f"[solo/planner] nudge retry failed: {e}", exc_info=True)
            return {
                "messages": [response],
                "need_thinking": need_thinking,
                "iteration": iteration,
            }

    return {
        "messages": [response],
        "need_thinking": need_thinking,
        "iteration": iteration,
    }


# ---------------------------------------------------------------------------
# 条件边
# ---------------------------------------------------------------------------

def should_continue(state: SoloState) -> str:
    """判断 planner 产出的最后一条消息是否还有 tool_calls。

    返回 "tools" 表示继续工具循环；"end" 表示结束。
    """
    last = state["messages"][-1] if state.get("messages") else None
    if isinstance(last, AIMessage) and last.tool_calls:
        return "tools"
    return "end"
