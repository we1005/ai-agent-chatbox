from typing import Annotated, TypedDict

from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages


class SoloState(TypedDict):
    """Solo 模式 ReAct 图的运行时状态。

    messages:
      planner 与 tool_executor 之间来回传递的消息列表，
      使用 LangGraph `add_messages` reducer 累加而非替换。

    model_name:
      planner 使用的 LLM（来自前端 ChatRequest.model）。

    need_thinking:
      当 planner 调用 `request_thinking` 元工具后置 True，
      后续轮次在 system prompt 中追加 CoT 指令。

    iteration:
      planner 已经触发的轮数（含当前轮），用于 recursion_limit 之外的软保护。
    """

    messages: Annotated[list[BaseMessage], add_messages]
    model_name: str
    need_thinking: bool
    iteration: int
