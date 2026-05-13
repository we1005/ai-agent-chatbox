"""
多级容错 LLM XML 解析器。

解析 LLM 输出中的结构化 XML：
  <content>正文，引用<ref>1</ref>...</content>
  <recommend><rec>追问1</rec><rec>追问2</rec></recommend>

降级策略：
  1. sloppy-xml（容错 SAX 解析，推荐）
  2. 正则兜底（完全无法解析时）
  3. 全量作为 content 纯文本
"""
import re
import logging
from typing import Any

logger = logging.getLogger(__name__)

try:
    import sloppy_xml
    _HAS_SLOPPY = True
except ImportError:
    _HAS_SLOPPY = False
    logger.warning("sloppy-xml not installed; XML parsing will use regex fallback only.")


def preprocess_xml(raw: str) -> str:
    """清理 LLM 输出中的常见非 XML 包装。"""
    raw = raw.strip()
    # 仅去除最外层 markdown 代码块包裹，避免误删正文中的 ```python 代码块。
    # 例如：
    # ```xml
    # <content>...</content>
    # ```
    outer_fence = re.match(r"^```(?:xml)?\s*\n?(.*)\n?```$", raw, re.DOTALL)
    if outer_fence:
        raw = outer_fence.group(1).strip()
    # 去除 XML 声明
    raw = re.sub(r"<\?xml[^?]*\?>", "", raw).strip()
    # 跳过 XML 第一个结构标签前的自然语言前置文字
    match = re.search(r"<(?:content|recommend|ref)\b", raw)
    if match:
        raw = raw[match.start():]
    return raw


def _extract_with_regex(raw: str) -> dict:
    """正则兜底提取，处理完全无法解析的情况。"""
    result: dict[str, Any] = {"content": "", "recommend": []}

    m = re.search(r"<content>(.*?)(?:</content>|$)", raw, re.DOTALL)
    if m:
        result["content"] = m.group(1).strip()
    else:
        # 完全没有 XML 标签，整体作为 content
        result["content"] = re.sub(r"<[^>]+>", "", raw).strip()

    result["recommend"] = [
        s.strip() for s in re.findall(r"<rec>(.*?)</rec>", raw, re.DOTALL) if s.strip()
    ]
    return result


def _build_refs(content: str, rag_docs: list) -> list[dict]:
    """从 content 中提取 <ref>N</ref>，映射到按文件分组的 rag_docs。

    rag_docs 支持两种格式：
      - 分组格式（推荐）: [{"filename": str, "chunks": [Document, ...]}, ...]
      - 扁平格式（兼容）: [Document, ...]
    """
    indices = [int(x) for x in re.findall(r"<ref>(\d+)</ref>", content)]
    seen: set[int] = set()
    refs = []
    for idx in indices:
        if idx in seen:
            continue
        seen.add(idx)
        if 0 < idx <= len(rag_docs):
            item = rag_docs[idx - 1]
            if isinstance(item, dict) and "filename" in item:
                all_text = " … ".join(c.page_content.strip() for c in item["chunks"])
                snippet = all_text[:200].strip()
                refs.append({
                    "index": idx,
                    "source": item["filename"],
                    "snippet": snippet,
                })
            else:
                refs.append({
                    "index": idx,
                    "source": item.metadata.get("original_filename", "未知文件"),
                    "snippet": item.page_content[:150].strip(),
                })
        else:
            refs.append({"index": idx, "source": "未知来源", "snippet": ""})
    return refs


def parse_llm_xml(raw: str, rag_docs: list) -> dict:
    """
    解析 LLM 的 XML 格式输出。

    返回：
        {
            "content":   str,          # 正文（保留 <ref>N</ref> 标记）
            "refs":      list[dict],   # [{index, source, snippet}, ...]
            "recommend": list[str],    # 推荐追问问题
        }
    """
    raw = preprocess_xml(raw)

    if not raw:
        return {"content": "", "refs": [], "recommend": []}

    # ── 级别 1：sloppy-xml 解析 ─────────────────────────────────────
    if _HAS_SLOPPY:
        try:
            content_parts: list[str] = []
            rec_parts: list[str] = []
            recommend: list[str] = []
            tag_stack: list[str] = []

            for event in sloppy_xml.stream_parse(f"<root>{raw}</root>"):
                if isinstance(event, sloppy_xml.StartElement):
                    tag_stack.append(event.name)
                elif isinstance(event, sloppy_xml.EndElement):
                    if event.name == "rec" and rec_parts:
                        text = "".join(rec_parts).strip()
                        if text:
                            recommend.append(text)
                        rec_parts = []
                    if tag_stack and tag_stack[-1] == event.name:
                        tag_stack.pop()
                elif isinstance(event, sloppy_xml.Text):
                    current = tag_stack[-1] if tag_stack else None
                    if current == "content":
                        content_parts.append(event.content)
                    elif current == "rec":
                        rec_parts.append(event.content)
                    elif current == "ref" and tag_stack:
                        # ref 内的文本（数字），注入回 content
                        parent = tag_stack[-2] if len(tag_stack) >= 2 else None
                        if parent == "content":
                            content_parts.append(f"<ref>{event.content}</ref>")
                elif isinstance(event, sloppy_xml.ParseError):
                    logger.debug(f"sloppy-xml recovered: {event.message}")

            content = "".join(content_parts).strip()
            if content:
                refs = _build_refs(content, rag_docs)
                return {"content": content, "refs": refs, "recommend": recommend}
        except Exception as e:
            logger.warning(f"sloppy-xml parse failed, falling back to regex: {e}")

    # ── 级别 2：正则兜底 ───────────────────────────────────────────
    fallback = _extract_with_regex(raw)
    content = fallback["content"]
    refs = _build_refs(content, rag_docs)
    return {"content": content, "refs": refs, "recommend": fallback["recommend"]}
