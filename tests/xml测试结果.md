```bash
(venv) PS D:\FastAPI-chatbox-langraph-version> pytest tests/test_xml_parser.py -v
============================================== test session starts ===============================================
platform win32 -- Python 3.12.6, pytest-9.0.2, pluggy-1.6.0 -- D:\FastAPI-chatbox-langraph-version\backend\venv\Scripts\python.exe
cachedir: .pytest_cache
rootdir: D:\FastAPI-chatbox-langraph-version
plugins: anyio-4.12.1, langsmith-0.7.22
collected 44 items

tests/test_xml_parser.py::TestPreprocessXml::test_strips_markdown_xml_fence PASSED                          [  2%]
tests/test_xml_parser.py::TestPreprocessXml::test_strips_plain_markdown_fence PASSED                        [  4%]
tests/test_xml_parser.py::TestPreprocessXml::test_strips_xml_declaration PASSED                             [  6%]
tests/test_xml_parser.py::TestPreprocessXml::test_skips_preamble_before_content_tag PASSED                  [  9%]
tests/test_xml_parser.py::TestPreprocessXml::test_skips_preamble_before_recommend_tag PASSED                [ 11%]
tests/test_xml_parser.py::TestPreprocessXml::test_passthrough_when_no_preamble PASSED                       [ 13%]
tests/test_xml_parser.py::TestPreprocessXml::test_empty_string PASSED                                       [ 15%]
tests/test_xml_parser.py::TestPreprocessXml::test_strips_all_wrappers_combined PASSED                       [ 18%]
tests/test_xml_parser.py::TestExtractWithRegex::test_normal_xml PASSED                                      [ 20%]
tests/test_xml_parser.py::TestExtractWithRegex::test_no_xml_tags_returns_full_text PASSED                   [ 22%]
tests/test_xml_parser.py::TestExtractWithRegex::test_unclosed_content_tag PASSED                            [ 25%]
tests/test_xml_parser.py::TestExtractWithRegex::test_content_only_no_recommend PASSED                       [ 27%]
tests/test_xml_parser.py::TestExtractWithRegex::test_recommend_only_no_content PASSED                       [ 29%]
tests/test_xml_parser.py::TestExtractWithRegex::test_strips_html_from_plain_text_fallback PASSED            [ 31%]
tests/test_xml_parser.py::TestBuildRefs::test_single_ref_matched PASSED                                     [ 34%]
tests/test_xml_parser.py::TestBuildRefs::test_multiple_refs_in_order PASSED                                 [ 36%]
tests/test_xml_parser.py::TestBuildRefs::test_duplicate_refs_deduplicated PASSED                            [ 38%]
tests/test_xml_parser.py::TestBuildRefs::test_out_of_range_ref PASSED                                       [ 40%]
tests/test_xml_parser.py::TestBuildRefs::test_no_refs_in_content PASSED                                     [ 43%]
tests/test_xml_parser.py::TestBuildRefs::test_empty_rag_docs PASSED                                         [ 45%]
tests/test_xml_parser.py::TestBuildRefs::test_snippet_truncated_to_150_chars PASSED                         [ 47%]
tests/test_xml_parser.py::TestParseLlmXml::test_well_formed_xml_no_refs PASSED                              [ 50%]
tests/test_xml_parser.py::TestParseLlmXml::test_well_formed_xml_with_refs PASSED                            [ 52%]
tests/test_xml_parser.py::TestParseLlmXml::test_multiline_content PASSED                                    [ 54%]
tests/test_xml_parser.py::TestParseLlmXml::test_preamble_before_content PASSED                              [ 56%]
tests/test_xml_parser.py::TestParseLlmXml::test_markdown_code_block_wrapper PASSED                          [ 59%]
tests/test_xml_parser.py::TestParseLlmXml::test_xml_declaration_header PASSED                               [ 61%]
tests/test_xml_parser.py::TestParseLlmXml::test_unclosed_content_tag PASSED                                 [ 63%]
tests/test_xml_parser.py::TestParseLlmXml::test_unclosed_recommend_tag PASSED                               [ 65%]
tests/test_xml_parser.py::TestParseLlmXml::test_no_xml_at_all_plain_text PASSED                             [ 68%]
tests/test_xml_parser.py::TestParseLlmXml::test_no_xml_markdown_with_headers PASSED                         [ 70%]
tests/test_xml_parser.py::TestParseLlmXml::test_empty_string_input PASSED                                   [ 72%]
tests/test_xml_parser.py::TestParseLlmXml::test_whitespace_only_input PASSED                                [ 75%]
tests/test_xml_parser.py::TestParseLlmXml::test_content_only_no_recommend PASSED                            [ 77%]
tests/test_xml_parser.py::TestParseLlmXml::test_recommend_only_content_empty PASSED                         [ 79%]
tests/test_xml_parser.py::TestParseLlmXml::test_multiple_recommend_items PASSED                             [ 81%]
tests/test_xml_parser.py::TestParseLlmXml::test_ref_index_0_is_out_of_range PASSED                          [ 84%]
tests/test_xml_parser.py::TestParseLlmXml::test_content_with_special_chars PASSED                           [ 86%]
tests/test_xml_parser.py::TestParseLlmXml::test_combined_ref_and_recommend_with_docs PASSED                 [ 88%]
tests/test_xml_parser.py::TestParseLlmXml::test_refs_order_preserved_in_content PASSED                      [ 90%]
tests/test_xml_parser.py::TestParseLlmXml::test_large_response_does_not_crash PASSED                        [ 93%]
tests/test_xml_parser.py::TestCombinedPipeline::test_all_wrappers_at_once PASSED                            [ 95%]
tests/test_xml_parser.py::TestCombinedPipeline::test_misspelled_tag_graceful PASSED                         [ 97%]
tests/test_xml_parser.py::TestCombinedPipeline::test_nested_tags_in_content PASSED                          [100%]

=============================================== 44 passed in 0.23s ===============================================
```





`pytest tests/test_xml_parser.py -v`

测试文件已创建。运行方式：

```bash
# 在项目根目录执行（需先安装 pytest 和 sloppy-xml）
cd D:\FastAPI-chatbox-langraph-version
pip install pytest sloppy-xml
pytest tests/test_xml_parser.py -v
```

---

**覆盖的 34 个测试场景：**

| 测试类                 | 覆盖场景                                                     |
| ---------------------- | ------------------------------------------------------------ |
| `TestPreprocessXml`    | Markdown 代码块、XML 声明、自然语言前置文字、空字符串、多种包装组合 |
| `TestExtractWithRegex` | 正常 XML、无 XML 标签纯文本、未闭合标签、只有 content/recommend、HTML 标签剥离 |
| `TestBuildRefs`        | 单引用、多引用顺序、重复引用去重、序号越界、无 rag_docs、snippet 截断 150 字 |
| `TestParseLlmXml`      | 正常 XML（有/无 refs）、多行内容、各种 LLM 不遵守格式场景、空输入、特殊字符、`<ref>0</ref>` 边界、超长输入不崩溃 |
| `TestCombinedPipeline` | 多种包装器叠加、标签拼写错误、content 内嵌套 HTML 标签       |

**设计重点：**
- 所有测试用 `MagicMock` 模拟 LangChain Document 对象，无需启动数据库或加载真实文件
- 容错类测试只断言"不崩溃 + 返回合理结构"，不强求完美解析结果
- `if __name__ == "__main__"` 支持直接 `python test_xml_parser.py` 运行