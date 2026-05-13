import logging
from serpapi import GoogleSearch
from app.core.config import get_settings

logger = logging.getLogger(__name__)


def web_search(query: str) -> str:
    """
    基于 SerpApi 的网页搜索工具。
    智能解析搜索结果，优先返回直接答案（answer_box / knowledge_graph），
    退而求其次返回前 3 条有机搜索结果摘要。
    """
    settings = get_settings()
    api_key = settings.SERPAPI_API_KEY
    if not api_key:
        return ""

    try:
        search = GoogleSearch({
            "q": query,
            "api_key": api_key,
            "gl": "cn",
            "hl": "zh-cn",
        })
        results = search.get_dict()

        if "answer_box_list" in results:
            return "\n".join(str(item) for item in results["answer_box_list"])

        if "answer_box" in results:
            ab = results["answer_box"]
            if "answer" in ab:
                return ab["answer"]
            if "snippet" in ab:
                return ab["snippet"]

        if "knowledge_graph" in results and "description" in results["knowledge_graph"]:
            return results["knowledge_graph"]["description"]

        if "organic_results" in results and results["organic_results"]:
            snippets = []
            for i, res in enumerate(results["organic_results"][:3]):
                title = res.get("title", "")
                snippet = res.get("snippet", "")
                link = res.get("link", "")
                snippets.append(f"[{i+1}] {title}\n{snippet}\n{link}")
            return "\n\n".join(snippets)

        return ""

    except Exception as e:
        logger.error(f"SerpApi search failed: {e}")
        return ""
