from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from jinja2 import Environment, FileSystemLoader, select_autoescape
from app.core.config import get_settings
from app.services._langsmith import get_openai, traceable, attach_run_metadata
from app.tools.web_search import web_search
from typing import AsyncGenerator
import asyncio
import logging
import os

_PROMPTS_DIR = os.path.join(os.path.dirname(__file__), "..", "prompts")
_jinja_env = Environment(
    loader=FileSystemLoader(_PROMPTS_DIR),
    autoescape=select_autoescape([]),
    trim_blocks=True,
    lstrip_blocks=True,
)

settings = get_settings()
logger = logging.getLogger(__name__)

class ChatService:
    def __init__(self, model_name: str = "kimi-k2-0905-preview"):
        self.model_name = model_name
        self.llm = self._get_llm(model_name)
        self._last_rag_docs: list = []

    def _get_llm(self, model_name: str):
        if model_name.startswith("moonshot") or model_name.startswith("kimi"):
            return ChatOpenAI(
                api_key=settings.MOONSHOT_API_KEY,
                base_url="https://api.moonshot.cn/v1",
                model=model_name,
                streaming=True
            )
        elif model_name.startswith("deepseek"):
            return ChatOpenAI(
                api_key=settings.DEEPSEEK_API_KEY,
                base_url="https://api.deepseek.com",
                model="deepseek-chat",
                streaming=True
            )
        elif model_name.startswith("qwen"):
            # 阿里云百炼 DashScope · OpenAI 兼容端点
            # 支持 qwen3.5-flash / qwen-plus / qwen-vl-plus 等所有 OpenAI-compatible 模型
            return ChatOpenAI(
                api_key=settings.DASHSCOPE_API_KEY,
                base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
                model=model_name,
                streaming=True
            )
        else:
            # Default to Kimi if unknown
            return ChatOpenAI(
                api_key=settings.MOONSHOT_API_KEY,
                base_url="https://api.moonshot.cn/v1",
                model="kimi-k2-0905-preview",
                streaming=True
            )

    @traceable(name="classic_chat_stream", run_type="chain")
    async def chat_stream(self, messages: list[dict], use_knowledge_base: bool = False, use_reranker: bool = False, use_web_search: bool = False, conversation_id: str | None = None, precomputed_intent: dict | None = None) -> AsyncGenerator[str, None]:
        # --- 0. Context Engine v2 · P1.2 + P2.3：服务端上下文主权 + Condenser Pipeline ---
        # 三档路径：
        #   a) CONTEXT_ENGINE_ENABLED=true  → events → Pipeline(RecentBuffer + LLMSummary) → View
        #   b) CHAT_REBUILD_HISTORY_FROM_EVENTS=true  → events 朴素展开（P1.2 行为）
        #   c) 两个都 false → 原样信前端 messages[]
        from app.core.config import get_settings
        _cfg = get_settings()
        _history_source = "client_payload"
        _ctx_trace: dict = {}
        if conversation_id and (_cfg.CONTEXT_ENGINE_ENABLED or _cfg.CHAT_REBUILD_HISTORY_FROM_EVENTS):
            try:
                # 找出前端传来的当前 user query（messages 尾部）
                _last_user = None
                for m in reversed(messages):
                    if m.get("role") == "user":
                        _last_user = m
                        break
                if _last_user is None:
                    raise RuntimeError("no user message in request")

                if _cfg.CONTEXT_ENGINE_ENABLED:
                    # 完整 Condenser Pipeline 路径
                    from app.services.conversation_service import (
                        load_events_for_conv, persist_summary_event,
                    )
                    from app.services.condenser import (
                        CondenseContext, LLMSummarizingCondenser,
                        PipelineCondenser, RecentBufferCondenser, events_to_messages,
                    )
                    raw_events = await load_events_for_conv(conversation_id)
                    # 过滤掉当前轮的 user_msg（P1.1 在 add_message 时已写入 events，
                    # 当前 user query 由 messages 尾部单独补上，避免重复）
                    if raw_events and raw_events[-1].kind == "user_msg":
                        raw_events = raw_events[:-1]

                    ctx = CondenseContext(conversation_id=conversation_id)
                    pipeline = PipelineCondenser([
                        LLMSummarizingCondenser(
                            max_size=_cfg.CONTEXT_SUMMARY_MAX_SIZE,
                            keep_first=_cfg.CONTEXT_SUMMARY_KEEP_FIRST,
                        ),
                        RecentBufferCondenser(max_recent_turns=_cfg.CONTEXT_RECENT_TURNS),
                    ])
                    view_events = await pipeline.condense(raw_events, ctx)

                    # 新生成的 summary 替身落盘为真 Event（下一轮 condense 可读）
                    # （duck-type 判断：真 Event Document 有 id 属性；替身 id=None）
                    for e in view_events:
                        if e.kind == "summary" and getattr(e, "id", None) is None:
                            await persist_summary_event(e)

                    rebuilt = events_to_messages(view_events)
                    messages = rebuilt + [_last_user]
                    _history_source = "context_engine"
                    _ctx_trace = ctx.trace
                    logger.info(
                        f"[ContextEngine] pipeline applied: "
                        f"conv={conversation_id} raw_events={len(raw_events)} "
                        f"view_events={len(view_events)} "
                        f"summary_fired={ctx.trace.get('llm_summary', {}).get('fired', False)}"
                    )
                else:
                    # P1.2 朴素 rebuild
                    from app.services.conversation_service import load_history_for_rebuild
                    rebuilt = await load_history_for_rebuild(conversation_id)
                    messages = rebuilt + [_last_user]
                    _history_source = "server_events"
                    logger.info(
                        f"[ContextEngine] rebuilt history from events: "
                        f"conv={conversation_id} turns={len(rebuilt)}"
                    )
            except Exception as e:
                logger.warning(
                    f"[ContextEngine] rebuild failed, falling back to client payload: "
                    f"{type(e).__name__}: {e}"
                )

        # --- 1. 拆分历史消息和当前 user query ---
        # 找到最后一条 user 消息作为当前问题，其余作为历史
        last_user_idx = None
        for i in range(len(messages) - 1, -1, -1):
            if messages[i]["role"] == "user":
                last_user_idx = i
                break

        if last_user_idx is None:
            # 没有 user 消息，直接透传
            langchain_messages = [SystemMessage(content=m["content"]) if m["role"] == "system"
                                  else HumanMessage(content=m["content"]) if m["role"] == "user"
                                  else AIMessage(content=m["content"])
                                  for m in messages]
            async for chunk in self.llm.astream(langchain_messages):
                if chunk.content:
                    yield chunk.content
            return

        user_query = messages[last_user_idx]["content"]
        history_messages = messages[:last_user_idx]

        # --- 1.5 意图识别：三分类路由 ---
        # 端点层 chat.py 已经先做过一次（修复 enable_thinking 绕过 weather 短路的 bug）
        # 时复用其结果，避免二次 LLM 调用
        if precomputed_intent is not None:
            intent_result = precomputed_intent
        else:
            from app.services.intent_service import detect_intent
            intent_result = await detect_intent(user_query)
        intent = intent_result["intent"]   # "code" | "weather" | "general"

        # 把业务维度挂到当前 LangSmith run，UI 里就能按 model / intent /
        # use_knowledge_base / use_reranker / multi_query 过滤对比。关闭追踪时空转。
        # Context Engine trace 拍平到 metadata（供 LangSmith A/B 分析）
        _ctx_meta: dict = {}
        if _ctx_trace:
            llm_sum = _ctx_trace.get("llm_summary", {})
            rb = _ctx_trace.get("recent_buffer", {})
            _ctx_meta = {
                "ctx_compaction_fired": llm_sum.get("fired", False),
                "ctx_summary_body_size": llm_sum.get("body_size"),
                "ctx_summary_forgotten": llm_sum.get("forgotten"),
                "ctx_summary_degraded": llm_sum.get("degraded", False),
                "ctx_recent_kept_turns": rb.get("kept_turns"),
                "ctx_recent_cutoff_turn": rb.get("cutoff_turn_id"),
                "ctx_recent_dropped_events": rb.get("dropped_event_count"),
            }

        # P3.3 · Memory 检索注入（规则路由命中时把 top-K memory 加到 system context）
        _memory_meta: dict = {"memory_hits": 0, "memory_router_fired": False}
        if _cfg.MEMORY_RETRIEVAL_ENABLED and conversation_id:
            try:
                from app.services.context_router import decide_memory_injection
                from app.services.memory_service import search_memory
                decision = decide_memory_injection(user_query, enabled=True)
                _memory_meta["memory_router_score"] = decision.rule_score
                _memory_meta["memory_router_hits"] = decision.rule_hits
                _memory_meta["memory_fallback_reason"] = decision.fallback_reason
                if decision.should_inject:
                    hits = await search_memory(
                        decision.search_query,
                        user_id=None,       # P3 阶段还没有 user 隔离，暂时共享
                        limit=_cfg.MEMORY_RETRIEVAL_TOP_K,
                    )
                    _memory_meta["memory_hits"] = len(hits)
                    _memory_meta["memory_router_fired"] = True
                    _memory_meta["memory_scores"] = [round(h["score"], 3) for h in hits[:5]]
                    if hits:
                        # 作为 system message 追加到 history 头部（紧随原 system，
                        # 让 LLM 优先看到"我们知道的用户事实"）
                        memory_block = "[用户相关的长期记忆]\n" + "\n".join(
                            f"- {h['text']}" for h in hits
                        )
                        history_messages = [
                            {"role": "system", "content": memory_block},
                            *history_messages,
                        ]
                        logger.info(
                            f"[MemoryRouter] injected {len(hits)} memory hits "
                            f"(score={decision.rule_score}, hits={decision.rule_hits})"
                        )
            except Exception as e:
                logger.warning(
                    f"[MemoryRouter] injection failed (non-fatal): "
                    f"{type(e).__name__}: {e}"
                )
                _memory_meta["memory_fallback_reason"] = f"error:{type(e).__name__}"

        attach_run_metadata(
            model=self.model_name,
            intent=intent,
            use_knowledge_base=use_knowledge_base,
            use_reranker=use_reranker,
            use_web_search=use_web_search,
            history_source=_history_source,              # P1.2: client_payload|server_events|context_engine
            history_turns=len(history_messages) if last_user_idx is not None else 0,
            **_ctx_meta,                                 # P2.3: compaction / buffer 指标
            **_memory_meta,                              # P3.3: memory router + retrieval 指标
        )

        # 天气查询：短路路径，跳过 RAG / 联网 / Prompt 渲染
        if intent == "weather":
            logger.info(f"[Intent] Weather intent detected, city={intent_result.get('city')!r}")
            async for chunk in self._handle_weather_query(
                city_keyword=intent_result.get("city") or user_query,
                original_query=user_query,
            ):
                yield chunk
            return

        use_doubao_code = (intent == "code")
        if use_doubao_code:
            logger.info("[Intent] Coding intent detected → routing to doubao-seed-2-0-code-preview-260215")

        # --- 2. 按需联网搜索 ---
        web_results = ""
        if use_web_search:
            try:
                web_results = web_search(user_query) or ""
                if web_results:
                    logger.info(f"Web search injected for query: {user_query}")
            except Exception as e:
                logger.error(f"Web search failed: {e}")

        # --- 3. 按需 RAG 检索（保留完整 doc 对象供模板使用） ---
        rag_docs = []
        kb_info = None
        if use_knowledge_base:
            try:
                from app.models.knowledge_document import KnowledgeDocument
                done_docs = await KnowledgeDocument.find(
                    KnowledgeDocument.vectorize_status == "done"
                ).to_list()
                if done_docs:
                    kb_info = {
                        "doc_count": len(done_docs),
                        "file_names": ", ".join(d.original_name for d in done_docs),
                    }
            except Exception as e:
                logger.error(f"Failed to fetch KB metadata: {e}")

            try:
                from app.services.rag_service import get_rag_service
                from app.services.query_rewrite import rewrite_query_if_needed

                rag = get_rag_service()

                # Graph RAG（LightRAG）最高优先级：启用时覆盖 Agentic / Multi-Query。
                # 仅走 retrieve 阶段，拿到 context 后仍喂给项目自己的 self.llm.astream()，
                # 保留 XML <content>/<recommend> 解析管道与引用注入。
                graph_rag_enabled = bool(getattr(rag, "graph_rag_enabled", False))
                graph_rag_mode = getattr(rag, "graph_rag_query_mode", "hybrid")
                _graph_trace: dict = {}
                if graph_rag_enabled:
                    from app.services.graph_rag import graph_rag_retrieve
                    logger.info(f"[GraphRAG] enabled, mode={graph_rag_mode!r}")
                    rag_docs, _graph_trace = await graph_rag_retrieve(
                        query=user_query,
                        mode=graph_rag_mode,
                        rag_service=rag,
                    )
                    logger.info(
                        f"--- RAG Retrieval Debug (Graph RAG {graph_rag_mode}) --- "
                        f"docs={len(rag_docs)} degraded={_graph_trace.get('degraded')} "
                        f"reason={_graph_trace.get('reason')}"
                    )
                    attach_run_metadata(
                        graph_rag_enabled=True,
                        graph_rag_mode=graph_rag_mode,
                        graph_rag_docs_count=len(rag_docs),
                        graph_rag_degraded=bool(_graph_trace.get("degraded")),
                    )
                    if _graph_trace.get("degraded"):
                        # 降级：继续落到下面的 agentic / multi-query / classical 路径
                        graph_rag_enabled = False

                # Agentic RAG 档位：仅在 intent=general + use_kb 时分支出去。
                # 注：classic 路径进 chat_stream 的分支已经经过 intent 判定，
                # code 路径早已 use_doubao_code 标记，weather 是短路 return；
                # 所以走到这里的 use_knowledge_base=True 场景 intent 必为 general。
                agentic_mode = getattr(rag, "agentic_rag_mode", "off")
                use_agentic = agentic_mode != "off"

                # 为 hallucination check 做准备：记一下本轮是否进入 full 档
                _agentic_full = (agentic_mode == "full")

                if graph_rag_enabled:
                    # Graph RAG 已拿到 rag_docs，跳过 Agentic / Multi-Query / Rewrite
                    pass
                elif use_agentic:
                    # Agentic RAG：跳启发式 rewrite（Agentic 的 rewrite 是 grading-driven 循环）
                    from app.services.agentic_rag import agentic_rag_retrieve
                    logger.info(f"[AgenticRAG] mode={agentic_mode!r} bypassing heuristic rewrite")
                    rag_docs, _agentic_trace = await agentic_rag_retrieve(
                        query=user_query,
                        rag=rag,
                        use_reranker=use_reranker,
                        mode=agentic_mode,
                        history_messages=history_messages,
                    )
                    logger.info(
                        f"--- RAG Retrieval Debug (Agentic {agentic_mode}) ---"
                    )
                    logger.info(
                        f"Original Query: {user_query} | "
                        f"rounds={_agentic_trace['rounds']} "
                        f"pass_rate={_agentic_trace['pass_rate']} "
                        f"degraded={_agentic_trace['degraded']} "
                        f"rewrite_history={_agentic_trace['rewrite_history']}"
                    )
                    # 把 agentic trace 挂到 LangSmith run metadata
                    attach_run_metadata(
                        agentic_rag_mode=agentic_mode,
                        agentic_grading_pass_rate=_agentic_trace["pass_rate"],
                        agentic_rewrite_rounds=_agentic_trace["rounds"] - 1,
                        agentic_degraded=_agentic_trace["degraded"],
                    )
                elif rag.multi_query_enabled:
                    # Multi-Query 开启：LLM 生成 3 个 variant，并行召回 → 合并 → rerank/RRF
                    # 与狭义 Rewrite 互斥（variants 已包含多角度，不再额外 rewrite）
                    logger.info(f"[MultiQuery] enabled, bypassing single-query rewrite")
                    rag_docs = await rag.retrieve_with_multi_query(
                        original_query=user_query,
                        use_reranker=use_reranker,
                    )
                    logger.info(f"--- RAG Retrieval Debug (Multi-Query) ---")
                    logger.info(f"Original Query: {user_query}")
                    logger.info(f"Chunks retrieved (after merge + rerank/RRF): {len(rag_docs)}")
                else:
                    # 默认路径：Query Rewrite 启发式 + 单 query 召回
                    retrieval_query, rewrite_reason = await rewrite_query_if_needed(
                        user_query, history_messages
                    )
                    logger.info(
                        f"[Rewrite] reason={rewrite_reason} | "
                        f"original={user_query!r} → retrieval={retrieval_query!r}"
                    )
                    retriever = rag.get_retriever(use_reranker=use_reranker)
                    rag_docs = await retriever.ainvoke(retrieval_query)
                    logger.info(f"--- RAG Retrieval Debug ---")
                    logger.info(f"Query: {retrieval_query}")
                    logger.info(f"Chunks retrieved: {len(rag_docs)}")
                for i, doc in enumerate(rag_docs):
                    logger.info(f"Chunk {i+1} Metadata: {doc.metadata}")
                    logger.info(f"Chunk {i+1} Snippet: {doc.page_content[:100]}...")
                logger.info(f"---------------------------")
            except Exception as e:
                logger.error(f"RAG retrieval failed: {e}")

        # --- 3.5 按文件名分组 rag_docs，同一文件共享一个 index ---
        from collections import OrderedDict
        grouped_map: OrderedDict[str, dict] = OrderedDict()
        for doc in rag_docs:
            fname = doc.metadata.get("original_filename", "未知文件")
            if fname not in grouped_map:
                grouped_map[fname] = {"filename": fname, "chunks": []}
            grouped_map[fname]["chunks"].append(doc)
        grouped_rag_docs = list(grouped_map.values())
        self._last_rag_docs = grouped_rag_docs

        # --- 4. Jinja2 渲染 system message ---
        system_tmpl = _jinja_env.get_template("chat_system.j2")
        system_content = system_tmpl.render(kb_info=kb_info).strip()

        # --- 5. Jinja2 渲染当前轮 user message（XML 嵌入 RAG + web 结果） ---
        query_tmpl = _jinja_env.get_template("chat_query.j2")
        user_content = query_tmpl.render(
            grouped_rag_docs=grouped_rag_docs,
            web_results=web_results,
            user_query=user_query,
        ).strip()

        # --- 6. 组装最终 messages 数组 ---
        langchain_messages = [SystemMessage(content=system_content)]
        for msg in history_messages:
            if msg["role"] == "user":
                langchain_messages.append(HumanMessage(content=msg["content"]))
            elif msg["role"] == "assistant":
                langchain_messages.append(AIMessage(content=msg["content"]))
            elif msg["role"] == "system":
                langchain_messages.append(SystemMessage(content=msg["content"]))
        langchain_messages.append(HumanMessage(content=user_content))

        # --- 7. 流式调用（根据意图选择模型） ---
        # 若 agentic_rag_mode=="full" 且 intent=general+use_kb，则累加 full_content 用于
        # 后续 Hallucination Check；其它场景不累加（省内存）。
        # Graph RAG 接管时跳过 hallucination check：两套校验语义不同且会双倍 LLM 成本。
        _graph_rag_active = "graph_rag_enabled" in locals() and graph_rag_enabled
        _need_hallu_check = (
            "_agentic_full" in locals() and _agentic_full
            and use_knowledge_base and rag_docs
            and not use_doubao_code
            and not _graph_rag_active
        )
        _accumulated = [] if _need_hallu_check else None

        if use_doubao_code:
            async for chunk in self._stream_doubao_code(langchain_messages):
                yield chunk
        else:
            async for chunk in self.llm.astream(langchain_messages):
                if chunk.content:
                    if _accumulated is not None:
                        _accumulated.append(chunk.content)
                    yield chunk.content

        # --- 8. Hallucination Check（仅 Agentic RAG full 档）---
        # 流完后对累加的答案做一次事实性校验；失败不重生成，只追加警告 banner。
        # 详见 plan-doc-dir/本项目是否真的实现了Agentic-RAG.md §失败降级。
        if _need_hallu_check and _accumulated:
            try:
                from app.services.agentic_rag import check_hallucination
                full_answer = "".join(_accumulated)
                verdict = await check_hallucination(full_answer, rag_docs)
                attach_run_metadata(
                    hallucination_verdict=(
                        "grounded" if verdict.get("grounded") else "unsupported"
                    ),
                    hallucination_reason=verdict.get("reason", ""),
                )
                logger.info(
                    f"[AgenticRAG/hallucination] grounded={verdict.get('grounded')} "
                    f"reason={verdict.get('reason')!r}"
                )
                if not verdict.get("grounded", True):
                    banner = (
                        "\n\n---\n"
                        "⚠️ **事实性校验提示**：本回答的部分声明在当前检索到的资料中未找到直接支撑，建议自行核实以下要点：\n"
                    )
                    claims = verdict.get("unsupported_claims") or []
                    if claims:
                        for c in claims[:3]:
                            banner += f"- {c}\n"
                    else:
                        banner += f"- {verdict.get('reason', '（无具体定位）')}\n"
                    yield banner
            except Exception as e:
                logger.warning(f"[AgenticRAG/hallucination] skipped due to exception: {e}")

    async def chat_stream_with_thinking(self, messages: list[dict]) -> AsyncGenerator[dict[str, str], None]:
        """
        DeepSeek 思考模式：模型保持 deepseek-chat，通过 extra_body 启用 thinking。
        绕过 LangChain 使用原生 OpenAI SDK 以获取 reasoning_content 字段。
        """
        client = get_openai(
            api_key=settings.DEEPSEEK_API_KEY,
            base_url="https://api.deepseek.com"
        )

        openai_messages: list[dict] = [{"role": m["role"], "content": m["content"]} for m in messages]

        stream = await client.chat.completions.create(
            model="deepseek-chat",
            messages=openai_messages,
            stream=True,
            extra_body={"thinking": {"type": "enabled"}}
        )

        async for chunk in stream:
            if not chunk.choices:
                continue
            delta = chunk.choices[0].delta
            if hasattr(delta, "reasoning_content") and delta.reasoning_content:
                yield {"type": "reasoning", "text": delta.reasoning_content}
            if delta.content:
                yield {"type": "content", "text": delta.content}

    async def _handle_weather_query(
        self, city_keyword: str, original_query: str
    ) -> AsyncGenerator[str, None]:
        """
        天气查询专用处理器。
        流程：地名解析 → 并行 MCP 调用 → LLM 自然语言化 → 流式输出。
        """
        from app.services.weather_service import resolve_location, call_weather_mcp

        matches = resolve_location(city_keyword)
        if not matches:
            yield f"抱歉，未找到「{city_keyword}」对应的地区，请确认地名是否正确。"
            return

        logger.info(f"[Weather] 查询 {len(matches)} 个地区: {[fp for fp, _ in matches]}")

        weather_data_list = await asyncio.gather(
            *[call_weather_mcp(adcode) for _, adcode in matches],
            return_exceptions=True,
        )

        context_parts = []
        for (full_path, _), data in zip(matches, weather_data_list):
            if isinstance(data, Exception):
                logger.warning(f"[Weather] MCP 调用失败 ({full_path}): {data}")
                continue
            context_parts.append(f"【{full_path}】{data}")

        if not context_parts:
            yield "天气查询失败，请稍后重试。"
            return

        weather_context = "\n".join(context_parts)
        async for chunk in self.llm.astream([
            SystemMessage(content="你是一个天气播报助手，请用自然、简洁的语言回答用户的天气问题。如果有多个地区，逐一列出。"),
            HumanMessage(content=f"用户问题：{original_query}\n\n天气数据：\n{weather_context}"),
        ]):
            if chunk.content:
                yield chunk.content

    @traceable(name="doubao_code_stream", run_type="llm")
    async def _stream_doubao_code(self, langchain_messages) -> AsyncGenerator[str, None]:
        """
        火山引擎 Doubao 代码模型流式输出。
        使用官方 AsyncArk 客户端，避免直接用 AsyncOpenAI 带来的接口兼容性风险。
        AsyncArk 不走 wrap_openai 路径，通过 @traceable 让 LangSmith 看到这次 LLM 调用。
        """
        from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
        from volcenginesdkarkruntime import AsyncArk

        client = AsyncArk(
            base_url="https://ark.cn-beijing.volces.com/api/v3",
            api_key=settings.ARK_API_KEY,
        )
        openai_messages = []
        for msg in langchain_messages:
            if isinstance(msg, SystemMessage):
                openai_messages.append({"role": "system", "content": msg.content})
            elif isinstance(msg, HumanMessage):
                openai_messages.append({"role": "user", "content": msg.content})
            elif isinstance(msg, AIMessage):
                openai_messages.append({"role": "assistant", "content": msg.content})

        stream = await client.chat.completions.create(
            model="doubao-seed-2-0-code-preview-260215",
            messages=openai_messages,
            stream=True,
        )
        async for chunk in stream:
            if not chunk.choices:
                continue
            content = chunk.choices[0].delta.content
            if content:
                yield content

    async def generate_title(self, user_query: str) -> str:
        prompt = (
            "请用10个中文字以内总结以下用户问题的核心主题，"
            "只输出标题本身，不要引号和标点：\n\n"
            f"{user_query}"
        )
        response = await self.llm.ainvoke([HumanMessage(content=prompt)])
        title = response.content.strip().strip('"\'""「」【】')
        if not title:
            title = user_query[:10]
        elif len(title) > 10:
            title = title[:10]
        return title
