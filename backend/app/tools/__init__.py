from typing import Dict, Callable, Any


class ToolRegistry:
    """
    工具注册表：统一管理所有外挂工具。
    未来可适配 MCP Tool Provider 或 A2A 协议。
    """
    _tools: Dict[str, Dict[str, Any]] = {}

    @classmethod
    def register(cls, name: str, description: str, func: Callable):
        cls._tools[name] = {"description": description, "func": func}

    @classmethod
    def get(cls, name: str) -> Callable:
        tool = cls._tools.get(name)
        return tool["func"] if tool else None

    @classmethod
    def list_tools(cls) -> Dict[str, str]:
        return {name: info["description"] for name, info in cls._tools.items()}
