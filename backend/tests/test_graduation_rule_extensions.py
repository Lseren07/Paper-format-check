from backend.app.models.contracts import Document
from backend.app.rules.contracts import CheckRule
from backend.app.rules.detectors import detect_heading_numbering, detect_reference_baseline
from backend.app.rules.spec_detectors import (
    detect_abstract_consistency,
    detect_abstract_length,
    detect_formula_format,
    detect_keyword_format,
    detect_page_break_after_heading,
    detect_required_sections,
)
from backend.app.rules.targets import paragraph_targets


def _paragraph(text, *, structure="body", level=None, page_index=None, style="Normal", fmt=None, runs=None):
    result = {
        "paragraph_id": f"p-{abs(hash(text)) % 10000:04d}",
        "text": text,
        "structure": structure,
        "heading": {"level": level},
        "style": {"name": style},
        "format": fmt or {},
        "runs": runs or [{"text": text, "font": {"effective": "宋体"}, "size_pt": 12}],
    }
    if page_index is not None:
        result["page_index"] = page_index
    return result


def test_required_sections_checks_order_and_allows_optional_appendix():
    document = Document(document_id="D1", source_filename="x.docx", paragraphs=[
        _paragraph("目录", structure="toc"),
        _paragraph("摘要", structure="abstract"),
        _paragraph("参考文献", structure="references"),
    ])
    rule = CheckRule(id="sections", type="required_sections", expected={
        "titles": ["摘要", "目录", "参考文献"],
        "optional_titles": ["附录"],
        "ordered": True,
    })

    errors = detect_required_sections(document, rule)

    assert any(error.current == "out-of-order" for error in errors)


def test_required_sections_does_not_match_unrelated_text_prefix():
    document = Document(document_id="D1", source_filename="x.docx", paragraphs=[
        _paragraph("摘要方法可分为三类", structure="body"),
        _paragraph("目录", structure="toc"),
    ])
    errors = detect_required_sections(document, CheckRule(
        id="sections", type="required_sections", expected={"titles": ["摘要", "目录"]}
    ))

    assert any(error.content == "摘要" and error.current == "missing" for error in errors)


def test_optional_appendix_must_still_appear_before_foreign_original_when_present():
    document = Document(document_id="D1", source_filename="x.docx", paragraphs=[
        _paragraph("参考文献", structure="references"),
        _paragraph("致谢", structure="body"),
        _paragraph("外文资料原文", structure="foreign"),
        _paragraph("附录", structure="body"),
        _paragraph("译文", structure="foreign"),
    ])
    errors = detect_required_sections(document, CheckRule(
        id="sections", type="required_sections", expected={
            "titles": ["参考文献", "致谢", "外文资料原文", "译文"],
            "optional_titles": ["附录"],
            "order": ["参考文献", "致谢", "附录", "外文资料原文", "译文"],
            "ordered": True,
        }
    ))

    assert any(error.current == "out-of-order" for error in errors)


def test_abstract_length_counts_cjk_characters_only_and_pair_checks_both_languages():
    document = Document(document_id="D1", source_filename="x.docx", paragraphs=[
        _paragraph("摘要", structure="abstract", level=None),
        _paragraph("这是中文摘要。", structure="abstract"),
    ])

    length_errors = detect_abstract_length(document, CheckRule(
        id="abstract-length", type="abstract_length", target="abstract", expected={"min": 20, "max": 30}
    ))
    consistency_errors = detect_abstract_consistency(document, CheckRule(
        id="abstract-consistency", type="abstract_consistency", target="all", expected={}
    ))

    assert length_errors[0].type == "abstract_length_error"
    assert consistency_errors[0].type == "abstract_consistency_error"


def test_english_abstract_word_count_does_not_count_chinese_characters():
    document = Document(document_id="D1", source_filename="x.docx", paragraphs=[
        _paragraph("ABSTRACT", structure="abstract_en", level=None),
        _paragraph("This has Chinese characters: " + "研究" * 130, structure="abstract_en"),
    ])
    errors = detect_abstract_length(document, CheckRule(
        id="abstract-en-length", type="abstract_length", target="abstract-en-body", expected={"max": 250, "unit": "english_words"}
    ))

    assert errors == []


def test_abstract_pair_reports_missing_english_version_when_chinese_exists():
    document = Document(document_id="D1", source_filename="x.docx", paragraphs=[
        _paragraph("摘要", structure="abstract", level=None),
        _paragraph("这是一段中文摘要。", structure="abstract"),
    ])
    errors = detect_abstract_consistency(document, CheckRule(
        id="abstract-consistency", type="abstract_consistency", target="all", expected={}
    ))

    assert errors[0].type == "abstract_consistency_error"


def test_keyword_rule_rejects_comma_and_uppercase_english_keyword():
    document = Document(document_id="D1", source_filename="x.docx", paragraphs=[
        _paragraph("Keywords: Database, testing; system", structure="keywords_en", fmt={"first_line_indent_chars": 0}, runs=[
            {"text": "Keywords: Database, testing; system", "font": {"effective": "Times New Roman"}, "size_pt": 12, "bold": True},
        ]),
    ])
    rule = CheckRule(id="keywords-en", type="keyword_format", target="keywords-en", expected={
        "pattern": r"^Keywords\s*[：:]", "min": 3, "max": 8, "lowercase": True,
        "separator": "semicolon",
    })

    errors = detect_keyword_format(document, rule)

    assert any(error.current == "comma" for error in errors)
    assert any(error.current == "Database" for error in errors)


def test_heading_rule_rejects_number_without_heading_title():
    document = Document(document_id="D1", source_filename="x.docx", paragraphs=[
        _paragraph("第1章", level=1, style="Heading 1"),
    ])

    errors = detect_heading_numbering(document, CheckRule(
        id="heading", type="heading_numbering", expected={"require_title": True}
    ))

    assert any(error.current == "missing-title" for error in errors)


def test_heading_rule_accepts_word_numbering_label_and_nonspaced_decimal_title():
    first = _paragraph("绪论", level=1, style="Heading 1")
    first["numbering"] = {"label": "第1章"}
    second = _paragraph("1.1选题背景", level=2, style="Heading 2")
    document = Document(document_id="D1", source_filename="x.docx", paragraphs=[first, second])

    errors = detect_heading_numbering(document, CheckRule(
        id="heading", type="heading_numbering", expected={"require_title": True}
    ))

    assert not any(error.current == "missing-title" for error in errors)


def test_page_break_rule_requires_next_chapter_on_new_page():
    document = Document(document_id="D1", source_filename="x.docx", paragraphs=[
        _paragraph("第1章 绪论", level=1, page_index=0),
        _paragraph("正文", page_index=0),
        _paragraph("第2章 方法", level=1, page_index=0),
    ])

    errors = detect_page_break_after_heading(document, CheckRule(
        id="chapter-break", type="page_break_after_heading", expected={"heading_level": 1}
    ))

    assert errors[0].type == "page_break_after_heading_error"


def test_page_break_rule_ignores_estimated_pagination():
    document = Document(document_id="D1", source_filename="x.docx", paragraphs=[
        _paragraph("第1章 绪论", level=1, page_index=0),
        _paragraph("正文", page_index=0),
        _paragraph("第2章 方法", level=1, page_index=0),
    ], pages=[{"page_index": 0, "source": "estimated", "page_source": "estimated"}])

    assert detect_page_break_after_heading(document, CheckRule(
        id="chapter-break", type="page_break_after_heading", expected={"heading_level": 1}
    )) == []


def test_page_break_rule_uses_heading_page_break_before_not_blank_previous_paragraph():
    heading = _paragraph("第2章 方法", level=1, page_index=1)
    heading["format"]["page_break_before"] = True
    document = Document(document_id="D1", source_filename="x.docx", paragraphs=[
        _paragraph("第1章 绪论", level=1, page_index=0),
        _paragraph("正文", page_index=0),
        _paragraph("", page_index=1),
        heading,
    ], pages=[
        {"page_index": 0, "source": "last_rendered", "page_source": "last_rendered"},
        {"page_index": 1, "source": "last_rendered", "page_source": "last_rendered"},
    ])

    assert detect_page_break_after_heading(document, CheckRule(
        id="chapter-break", type="page_break_after_heading", expected={"heading_level": 1}
    )) == []


def test_formula_rule_requires_centered_spacing_and_parenthesized_end_number():
    document = Document(document_id="D1", source_filename="x.docx", paragraphs=[
        _paragraph("E = mc2 1", structure="body", fmt={"alignment": "left", "line_spacing": 18, "space_before_pt": 0, "space_after_pt": 0}),
    ])
    document.paragraphs[0]["paragraph_id"] = "p-0010"
    document.paragraphs[0]["formula"] = True
    rule = CheckRule(id="formula", type="formula_format", target="all", expected={
        "alignment": "center", "space_before_pt": 6, "space_after_pt": 6,
        "min_line_spacing": 20, "number_pattern": r"\(\d+(?:[-.]\d+)?\)$",
    })

    errors = detect_formula_format(document, rule)

    assert {error.location for error in errors} >= {"p-0010:alignment", "p-0010:line-spacing", "p-0010:number"}


def test_reference_rule_requires_terminal_period_and_known_body_citation():
    document = Document(document_id="D1", source_filename="x.docx", paragraphs=[
        _paragraph("第1章 绪论", level=1),
        _paragraph("已有观点[3]。"),
        _paragraph("参考文献", structure="references"),
        _paragraph("[1] 第一条", structure="references"),
        _paragraph("[2] 第二条.", structure="references"),
    ])
    rule = CheckRule(id="references", type="reference_baseline", target="all", expected={
        "entry_ending": ".", "check_citations": True,
    })

    errors = detect_reference_baseline(document, rule)

    assert any(error.location.endswith(":ending") for error in errors)
    assert any(error.location == "citation-order" for error in errors)


def test_caption_note_is_targeted_separately_from_body_text():
    document = Document(document_id="D1", source_filename="x.docx", paragraphs=[
        _paragraph("图1 结果", structure="figure_caption"),
        _paragraph("注：数据为实验结果", structure="body", style="Normal"),
    ])

    assert "caption-note" in paragraph_targets(document)[document.paragraphs[1]["paragraph_id"]]
