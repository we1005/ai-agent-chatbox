"""
xml_parser.py 单元测试

覆盖场景：
  - 正常 XML 输出
  - 有知识库引用（<ref>）的输出
  - 引用序号越界 / 无 rag_docs
  - 重复引用去重
  - LLM 在 XML 前加自然语言前置文字
  - Markdown 代码块包裹
  - XML 声明头
  - 未闭合标签（截断场景）
  - 完全没有 XML（纯文本/Markdown 输出）
  - 空字符串输入
  - <recommend> 存在但 <content> 为空
  - 仅有 <content> 没有 <recommend>
  - 特殊字符 / Markdown 内容
  - 多个 <rec> 条目
"""

import sys
import os
import pytest
from unittest.mock import MagicMock

# ── 路径配置 ──────────────────────────────────────────────────────────────────
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from app.services.xml_parser import (
    preprocess_xml,
    _extract_with_regex,
    _build_refs,
    parse_llm_xml,
)


# ── Mock RAG Doc 工厂 ────────────────────────────────────────────────────────

def make_doc(filename: str, content: str) -> MagicMock:
    doc = MagicMock()
    doc.metadata = {"original_filename": filename}
    doc.page_content = content
    return doc


RAG_DOCS = [
    make_doc("深度学习入门.pdf", "卷积神经网络（CNN）是深度学习的重要组成部分，广泛用于图像识别任务。"),
    make_doc("Transformer论文.pdf", "注意力机制允许模型在处理序列时动态关注不同位置的信息，是 Transformer 的核心。"),
    make_doc("Python教程.pdf", "Python 是一门简单易学的编程语言，支持面向对象和函数式编程范式。"),
]


# ═══════════════════════════════════════════════════════════════════════════════
# preprocess_xml
# ═══════════════════════════════════════════════════════════════════════════════

class TestPreprocessXml:

    def test_strips_markdown_xml_fence(self):
        raw = "```xml\n<content>正文</content>\n```"
        result = preprocess_xml(raw)
        assert "<content>" in result
        assert "```" not in result

    def test_strips_plain_markdown_fence(self):
        raw = "```\n<content>正文</content>\n```"
        result = preprocess_xml(raw)
        assert "<content>" in result
        assert "```" not in result

    def test_strips_xml_declaration(self):
        raw = '<?xml version="1.0" encoding="UTF-8"?><content>正文</content>'
        result = preprocess_xml(raw)
        assert "<?xml" not in result
        assert "<content>" in result

    def test_skips_preamble_before_content_tag(self):
        raw = "好的，以下是我的回答：\n<content>正文内容</content>"
        result = preprocess_xml(raw)
        assert result.startswith("<content>")
        assert "好的" not in result

    def test_skips_preamble_before_recommend_tag(self):
        raw = "请参考以下问题：\n<recommend><rec>追问1</rec></recommend>"
        result = preprocess_xml(raw)
        assert result.startswith("<recommend>")

    def test_passthrough_when_no_preamble(self):
        raw = "<content>直接开始</content>"
        result = preprocess_xml(raw)
        assert result == raw

    def test_empty_string(self):
        assert preprocess_xml("") == ""

    def test_strips_all_wrappers_combined(self):
        raw = "```xml\n<?xml version=\"1.0\"?>\n好的：\n<content>正文</content>\n```"
        result = preprocess_xml(raw)
        assert result.startswith("<content>")
        assert "<?xml" not in result
        assert "好的" not in result
        assert "```" not in result


# ═══════════════════════════════════════════════════════════════════════════════
# _extract_with_regex
# ═══════════════════════════════════════════════════════════════════════════════

class TestExtractWithRegex:

    def test_normal_xml(self):
        raw = "<content>正文内容</content><recommend><rec>追问1</rec><rec>追问2</rec></recommend>"
        result = _extract_with_regex(raw)
        assert result["content"] == "正文内容"
        assert result["recommend"] == ["追问1", "追问2"]

    def test_no_xml_tags_returns_full_text(self):
        raw = "这是一段普通的 Markdown 回答，没有 XML 标签。"
        result = _extract_with_regex(raw)
        assert result["content"] == raw
        assert result["recommend"] == []

    def test_unclosed_content_tag(self):
        raw = "<content>被截断的正文"
        result = _extract_with_regex(raw)
        assert "被截断的正文" in result["content"]

    def test_content_only_no_recommend(self):
        raw = "<content>有正文没有推荐</content>"
        result = _extract_with_regex(raw)
        assert result["content"] == "有正文没有推荐"
        assert result["recommend"] == []

    def test_recommend_only_no_content(self):
        raw = "<recommend><rec>问题1</rec></recommend>"
        result = _extract_with_regex(raw)
        assert result["recommend"] == ["问题1"]

    def test_strips_html_from_plain_text_fallback(self):
        """LLM 输出了含 HTML 标签的内容但没有 XML 结构"""
        raw = "这是<b>加粗</b>文字，没有 content 标签"
        result = _extract_with_regex(raw)
        assert "<b>" not in result["content"]
        assert "加粗" in result["content"]


# ═══════════════════════════════════════════════════════════════════════════════
# _build_refs
# ═══════════════════════════════════════════════════════════════════════════════

class TestBuildRefs:

    def test_single_ref_matched(self):
        content = "这是正文<ref>1</ref>，结束。"
        refs = _build_refs(content, RAG_DOCS)
        assert len(refs) == 1
        assert refs[0]["index"] == 1
        assert refs[0]["source"] == "深度学习入门.pdf"
        assert "卷积" in refs[0]["snippet"]

    def test_multiple_refs_in_order(self):
        content = "正文<ref>1</ref>和<ref>2</ref>。"
        refs = _build_refs(content, RAG_DOCS)
        assert len(refs) == 2
        assert refs[0]["index"] == 1
        assert refs[1]["index"] == 2

    def test_duplicate_refs_deduplicated(self):
        content = "引用<ref>1</ref>多次<ref>1</ref>。"
        refs = _build_refs(content, RAG_DOCS)
        assert len(refs) == 1
        assert refs[0]["index"] == 1

    def test_out_of_range_ref(self):
        content = "引用了<ref>99</ref>这个不存在的文档。"
        refs = _build_refs(content, RAG_DOCS)
        assert len(refs) == 1
        assert refs[0]["index"] == 99
        assert refs[0]["source"] == "未知来源"
        assert refs[0]["snippet"] == ""

    def test_no_refs_in_content(self):
        content = "没有任何引用标记的正文。"
        refs = _build_refs(content, RAG_DOCS)
        assert refs == []

    def test_empty_rag_docs(self):
        content = "有引用<ref>1</ref>但没有文档。"
        refs = _build_refs(content, [])
        assert len(refs) == 1
        assert refs[0]["source"] == "未知来源"

    def test_snippet_truncated_to_150_chars(self):
        long_doc = make_doc("长文档.pdf", "A" * 300)
        content = "引用<ref>1</ref>长文档。"
        refs = _build_refs(content, [long_doc])
        assert len(refs[0]["snippet"]) <= 150


# ═══════════════════════════════════════════════════════════════════════════════
# parse_llm_xml — 集成测试（同时覆盖 sloppy-xml 和正则兜底路径）
# ═══════════════════════════════════════════════════════════════════════════════

class TestParseLlmXml:

    # ── 正常场景 ───────────────────────────────────────────────────────────────

    def test_well_formed_xml_no_refs(self):
        raw = (
            "<content>这是一段正常的回答。</content>"
            "<recommend><rec>追问问题1</rec><rec>追问问题2</rec></recommend>"
        )
        result = parse_llm_xml(raw, [])
        assert result["content"] == "这是一段正常的回答。"
        assert result["recommend"] == ["追问问题1", "追问问题2"]
        assert result["refs"] == []

    def test_well_formed_xml_with_refs(self):
        raw = (
            "<content>根据知识库<ref>1</ref>，Transformer<ref>2</ref>非常重要。</content>"
            "<recommend><rec>CNN 有哪些应用？</rec></recommend>"
        )
        result = parse_llm_xml(raw, RAG_DOCS)
        assert "<ref>1</ref>" in result["content"]
        assert "<ref>2</ref>" in result["content"]
        assert len(result["refs"]) == 2
        assert result["refs"][0]["source"] == "深度学习入门.pdf"
        assert result["refs"][1]["source"] == "Transformer论文.pdf"
        assert len(result["recommend"]) == 1

    def test_multiline_content(self):
        raw = (
            "<content>\n第一段。\n\n第二段，包含 **Markdown** 加粗。\n</content>"
            "<recommend><rec>追问</rec></recommend>"
        )
        result = parse_llm_xml(raw, [])
        assert "第一段" in result["content"]
        assert "第二段" in result["content"]

    # ── 错误恢复场景 ────────────────────────────────────────────────────────────

    def test_preamble_before_content(self):
        raw = "当然，以下是我的回答：\n<content>实际正文</content>\n<recommend><rec>问题</rec></recommend>"
        result = parse_llm_xml(raw, [])
        assert result["content"] == "实际正文"
        assert "当然" not in result["content"]

    def test_markdown_code_block_wrapper(self):
        raw = "```xml\n<content>被代码块包裹的正文</content>\n<recommend><rec>追问</rec></recommend>\n```"
        result = parse_llm_xml(raw, [])
        assert result["content"] == "被代码块包裹的正文"

    def test_xml_declaration_header(self):
        raw = '<?xml version="1.0"?><content>带 XML 声明的正文</content>'
        result = parse_llm_xml(raw, [])
        assert result["content"] == "带 XML 声明的正文"

    def test_unclosed_content_tag(self):
        """流式截断场景：</content> 丢失"""
        raw = "<content>流式截断，标签未闭合"
        result = parse_llm_xml(raw, [])
        assert "流式截断" in result["content"]

    def test_unclosed_recommend_tag(self):
        """<recommend> 未闭合"""
        raw = "<content>正文</content><recommend><rec>问题1</rec>"
        result = parse_llm_xml(raw, [])
        assert result["content"] == "正文"
        assert "问题1" in result["recommend"]

    def test_no_xml_at_all_plain_text(self):
        """LLM 完全忽略 XML 格式，直接输出纯文本"""
        raw = "这是一段没有任何 XML 标签的纯文本回答，包含 **Markdown**。"
        result = parse_llm_xml(raw, [])
        # 容错：整体作为 content，不崩溃
        assert isinstance(result["content"], str)
        assert len(result["content"]) > 0
        assert result["refs"] == []
        assert isinstance(result["recommend"], list)

    def test_no_xml_markdown_with_headers(self):
        raw = "## 标题\n\n- 列表项1\n- 列表项2\n\n正文段落。"
        result = parse_llm_xml(raw, [])
        assert isinstance(result["content"], str)

    # ── 边界场景 ────────────────────────────────────────────────────────────────

    def test_empty_string_input(self):
        result = parse_llm_xml("", [])
        assert result == {"content": "", "refs": [], "recommend": []}

    def test_whitespace_only_input(self):
        result = parse_llm_xml("   \n\t  ", [])
        assert result["content"] == ""
        assert result["refs"] == []

    def test_content_only_no_recommend(self):
        raw = "<content>只有正文，没有推荐问题。</content>"
        result = parse_llm_xml(raw, [])
        assert result["content"] == "只有正文，没有推荐问题。"
        assert result["recommend"] == []

    def test_recommend_only_content_empty(self):
        """content 标签里没有文字"""
        raw = "<content></content><recommend><rec>追问1</rec></recommend>"
        result = parse_llm_xml(raw, [])
        # content 为空时应回退到正则
        assert isinstance(result["recommend"], list)

    def test_multiple_recommend_items(self):
        raw = (
            "<content>正文</content>"
            "<recommend>"
            "<rec>问题A</rec>"
            "<rec>问题B</rec>"
            "<rec>问题C</rec>"
            "</recommend>"
        )
        result = parse_llm_xml(raw, [])
        assert len(result["recommend"]) == 3
        assert "问题A" in result["recommend"]
        assert "问题C" in result["recommend"]

    def test_ref_index_0_is_out_of_range(self):
        """<ref>0</ref> 序号从 1 开始，0 应视为越界"""
        raw = "<content>引用了<ref>0</ref>一个无效序号。</content>"
        result = parse_llm_xml(raw, RAG_DOCS)
        ref = next((r for r in result["refs"] if r["index"] == 0), None)
        assert ref is not None
        assert ref["source"] == "未知来源"

    def test_content_with_special_chars(self):
        raw = "<content>包含特殊字符：& ' \" < > 等符号。</content>"
        result = parse_llm_xml(raw, [])
        # 不应崩溃
        assert "特殊字符" in result["content"]

    def test_combined_ref_and_recommend_with_docs(self):
        raw = (
            "<content>Python<ref>3</ref>是很好的语言。</content>"
            "<recommend><rec>如何学习 Python？</rec><rec>Python 有哪些框架？</rec></recommend>"
        )
        result = parse_llm_xml(raw, RAG_DOCS)
        assert len(result["refs"]) == 1
        assert result["refs"][0]["source"] == "Python教程.pdf"
        assert len(result["recommend"]) == 2

    def test_refs_order_preserved_in_content(self):
        """<ref>2</ref> 先出现，<ref>1</ref> 后出现，顺序要按在正文中的出现顺序"""
        raw = "<content>先<ref>2</ref>后<ref>1</ref></content>"
        result = parse_llm_xml(raw, RAG_DOCS)
        assert result["refs"][0]["index"] == 2
        assert result["refs"][1]["index"] == 1

    def test_large_response_does_not_crash(self):
        """超长正文不应崩溃"""
        long_content = "这是很长的句子。" * 500
        raw = f"<content>{long_content}</content><recommend><rec>追问</rec></recommend>"
        result = parse_llm_xml(raw, [])
        assert len(result["content"]) > 100
        assert result["recommend"] == ["追问"]


# ═══════════════════════════════════════════════════════════════════════════════
# preprocess_xml + parse_llm_xml 组合场景
# ═══════════════════════════════════════════════════════════════════════════════

class TestCombinedPipeline:

    def test_all_wrappers_at_once(self):
        """Markdown 代码块 + XML 声明 + 自然语言前置 + 正常 XML"""
        raw = (
            "```xml\n"
            '<?xml version="1.0"?>\n'
            "好的，以下是分析：\n"
            "<content>核心内容<ref>1</ref>。</content>\n"
            "<recommend><rec>还有什么问题？</rec></recommend>\n"
            "```"
        )
        result = parse_llm_xml(raw, RAG_DOCS)
        assert "核心内容" in result["content"]
        assert result["refs"][0]["source"] == "深度学习入门.pdf"
        assert result["recommend"] == ["还有什么问题？"]

    def test_misspelled_tag_graceful(self):
        """标签名拼写错误，sloppy-xml 应尽量恢复，不崩溃"""
        raw = "<content>正文内容</contents><recommend><rec>追问</rec></recommend>"
        result = parse_llm_xml(raw, [])
        assert isinstance(result["content"], str)
        assert not result.get("error")

    def test_nested_tags_in_content(self):
        """LLM 在 content 内嵌套了额外标签"""
        raw = "<content>正文<b>加粗</b>内容</content><recommend><rec>问题</rec></recommend>"
        result = parse_llm_xml(raw, [])
        # 不崩溃，content 包含某些文字
        assert "正文" in result["content"] or "加粗" in result["content"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
