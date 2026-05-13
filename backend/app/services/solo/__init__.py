"""Solo 模式：基于 LangGraph 的自主 Agent 流水线。

公共能力（LLM、RAG、MCP、web_search、XML 解析）全部从现有服务 import 复用，
不修改任何既有代码。入口为 `graph.get_solo_graph()` 返回已编译的 StateGraph。
"""
