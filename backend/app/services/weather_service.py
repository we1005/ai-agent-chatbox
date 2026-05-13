import logging
from collections import defaultdict
from pathlib import Path

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# 模块级数据结构（启动时由 init_city_data 填充）
# ---------------------------------------------------------------------------
_adcode_to_name: dict[str, str] = {}
_name_to_adcodes: dict[str, list[str]] = {}
_adcode_to_fullpath: dict[str, str] = {}
_all_names: list[str] = []

_mcp_client = None
_weather_tool = None


# ---------------------------------------------------------------------------
# 1. Excel 数据加载
# ---------------------------------------------------------------------------

def _build_full_path(adcode: str) -> str:
    """利用 adcode 前缀规律还原省/市/区层级路径，例如 110105 → 北京市/朝阳区。"""
    province = adcode[:2] + "0000"
    city = adcode[:4] + "00"
    parts = []
    if province in _adcode_to_name and province != adcode:
        parts.append(_adcode_to_name[province])
    if city in _adcode_to_name and city != adcode and city != province:
        parts.append(_adcode_to_name[city])
    if adcode in _adcode_to_name:
        leaf = _adcode_to_name[adcode]
        if not parts or parts[-1] != leaf:
            parts.append(leaf)
    return "/".join(parts)


def init_city_data(excel_path: str) -> None:
    """
    启动时调用一次，将 AMap_adcode_citycode.xlsx 加载进内存。
    excel_path 相对于 backend/ 目录，例如 "data/AMap_adcode_citycode.xlsx"。
    """
    global _adcode_to_name, _name_to_adcodes, _adcode_to_fullpath, _all_names

    import pandas as pd

    resolved = Path(excel_path)
    if not resolved.is_absolute():
        # 相对路径以 backend/ 为基准（main.py 所在目录）
        backend_dir = Path(__file__).parent.parent.parent
        resolved = backend_dir / excel_path

    if not resolved.exists():
        logger.error(f"[Weather] Excel 文件不存在: {resolved}")
        return

    df = pd.read_excel(resolved)
    df["adcode"] = df["adcode"].astype(str).str.zfill(6)

    _adcode_to_name = dict(zip(df["adcode"], df["中文名"]))

    name_to_adcodes: dict[str, list[str]] = defaultdict(list)
    for _, row in df.iterrows():
        name_to_adcodes[str(row["中文名"])].append(str(row["adcode"]))
    _name_to_adcodes = dict(name_to_adcodes)

    _adcode_to_fullpath = {code: _build_full_path(code) for code in df["adcode"]}
    _all_names = list(_name_to_adcodes.keys())

    logger.info(f"[Weather] 城市编码表加载完成，共 {len(_adcode_to_name)} 条记录，"
                f"{len(_name_to_adcodes)} 个唯一地名。")


# ---------------------------------------------------------------------------
# 2. 地名解析（四级漏斗）
# ---------------------------------------------------------------------------

def resolve_location(keyword: str) -> list[tuple[str, str]]:
    """
    将用户输入的地名关键词解析为 [(full_path, adcode), ...] 列表。
    空列表表示未找到任何匹配（地名不存在或无法识别）。

    四级漏斗：
      级1 - 精确匹配
      级2 - 追加"市/区/县/省"后缀后精确匹配
      级3 - rapidfuzz 模糊匹配（score_cutoff=70）
      级4 - 返回空列表
    """
    if not _name_to_adcodes:
        logger.warning("[Weather] 城市数据未加载，请先调用 init_city_data()")
        return []

    # 级1：精确匹配
    candidates = _name_to_adcodes.get(keyword, [])

    # 级2：追加行政区划后缀重试（收集所有后缀的结果取并集，不能 break）
    if not candidates:
        all_suffix_candidates: list[str] = []
        matched_names: list[str] = []
        for suffix in ["市", "区", "县", "省"]:
            suffix_result = _name_to_adcodes.get(keyword + suffix, [])
            if suffix_result:
                all_suffix_candidates.extend(suffix_result)
                matched_names.append(keyword + suffix)
        if all_suffix_candidates:
            candidates = all_suffix_candidates
            logger.debug(f"[Weather] 后缀补全命中: {keyword} → {matched_names}")

    # 级3：rapidfuzz 模糊匹配
    if not candidates:
        try:
            from rapidfuzz import process
            result = process.extractOne(keyword, _all_names, score_cutoff=70)
            if result:
                matched_name = result[0]
                score = result[1]
                candidates = _name_to_adcodes[matched_name]
                logger.debug(f"[Weather] 模糊匹配命中: {keyword!r} → {matched_name!r} (score={score:.1f})")
        except Exception as e:
            logger.warning(f"[Weather] rapidfuzz 匹配失败: {e}")

    if not candidates:
        logger.info(f"[Weather] 地名未找到: {keyword!r}")
        return []

    return [((_adcode_to_fullpath.get(c) or c), c) for c in candidates]


# ---------------------------------------------------------------------------
# 3. MCP 客户端初始化与调用
# ---------------------------------------------------------------------------

async def init_weather_mcp(url: str = "http://127.0.0.1:8001/sse") -> None:
    """
    在 FastAPI lifespan 中调用，连接天气 MCP Server 并缓存工具引用。
    MCP Server 需要提前以 PORT=8001 启动。

    langchain-mcp-adapters >= 0.1.0 不再支持 context manager，
    直接调用 get_tools() 即可。
    """
    global _mcp_client, _weather_tool

    from langchain_mcp_adapters.client import MultiServerMCPClient

    _mcp_client = MultiServerMCPClient({
        "amap_weather": {
            "transport": "sse",
            "url": url,
        }
    })
    tools = await _mcp_client.get_tools()

    # 兼容 getweatherinfo / getWeatherInfo 两种工具名风格
    _weather_tool = next(
        (t for t in tools if "weather" in t.name.lower()),
        None
    )

    if _weather_tool is None:
        tool_names = [t.name for t in tools]
        logger.error(f"[Weather] 未找到天气工具，可用工具: {tool_names}")
        raise RuntimeError(f"Weather tool not found in MCP server. Available: {tool_names}")

    logger.info(f"[Weather] MCP 连接成功，使用工具: {_weather_tool.name}，地址: {url}")


async def shutdown_weather_mcp() -> None:
    """在 FastAPI lifespan 退出时调用，清理 MCP 客户端引用。"""
    global _mcp_client, _weather_tool
    _mcp_client = None
    _weather_tool = None
    logger.info("[Weather] MCP 客户端已清理。")


async def call_weather_mcp(adcode: str, extensions: str = "base") -> str:
    """
    调用天气 MCP 工具查询指定 adcode 的天气。
    extensions: "base"=实况天气，"all"=预报天气
    """
    if _weather_tool is None:
        raise RuntimeError("天气 MCP 工具未初始化，请确认 MCP Server 已启动。")

    result = await _weather_tool.ainvoke({"city": adcode, "extensions": extensions})
    return str(result)
