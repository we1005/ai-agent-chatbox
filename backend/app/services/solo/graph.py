"""Solo 模式 LangGraph StateGraph 构建与单例管理。"""

from __future__ import annotations

import logging

from langgraph.graph import END, START, StateGraph
from langgraph.prebuilt import ToolNode

from app.services.solo.nodes import (
    classify_complexity_node,
    planner_node,
    should_continue,
)
from app.services.solo.state import SoloState
from app.services.solo.tools import SOLO_TOOLS

logger = logging.getLogger(__name__)

# Recursion limit 控制 planner ↔ tools 的循环次数上限。
# 一个完整循环 = planner + tools = 2 次 node 调用，所以 16 约等于 8 个完整回合。
# +1 给 classify_complexity（首跳），略放宽。
SOLO_RECURSION_LIMIT = 18

_compiled_graph = None


def _build_graph():
    graph = StateGraph(SoloState)

    graph.add_node("classify_complexity", classify_complexity_node)
    graph.add_node("planner", planner_node)
    graph.add_node("tools", ToolNode(SOLO_TOOLS))

    # 入口先过 complexity 分类，再进 planner；后续 planner ⇄ tools 循环
    graph.add_edge(START, "classify_complexity")
    graph.add_edge("classify_complexity", "planner")
    graph.add_conditional_edges(
        "planner",
        should_continue,
        {"tools": "tools", "end": END},
    )
    graph.add_edge("tools", "planner")

    return graph.compile()


def get_solo_graph():
    """返回编译后的 Solo 图（模块级单例）。"""
    global _compiled_graph
    if _compiled_graph is None:
        logger.info("Compiling Solo LangGraph...")
        _compiled_graph = _build_graph()
        logger.info("Solo LangGraph compiled.")
    return _compiled_graph
