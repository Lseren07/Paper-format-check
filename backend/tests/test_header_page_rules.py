from pathlib import Path

from backend.app.models.contracts import Document
from backend.app.rules.contracts import CheckRule, RuleSet
from backend.app.rules.engine import RuleEngine
from backend.app.rules.loader import load_rules


def _paragraph(text: str, *, font: str, size: float, alignment: str, field: bool = False) -> dict:
    return {
        "text": text,
        "format": {"alignment": alignment},
        "runs": [{
            "text": text,
            "font": {"effective": font, "ascii": font, "east_asia": font},
            "size_pt": size,
            "fields": ["PAGE"] if field else [],
        }],
    }


def _run(document: Document, rule_type: str, expected: dict) -> list:
    rule = CheckRule(id="check", type=rule_type, expected=expected)
    return RuleEngine(document, RuleSet(schema_version="1.0", name="test", checks=[rule])).run()


def test_header_footer_format_checks_only_confirmed_styles_and_odd_even_setting() -> None:
    document = Document(
        document_id="D1", source_filename="x.docx",
        paragraphs=[{"paragraph_id": "p1", "text": "摘 要", "structure": "abstract", "structure_role": "title", "page_index": 0}],
        sections=[{"index": 0, "odd_and_even_pages_header_footer": False}],
        pages=[{"page_index": 0, "section_index": 0, "paragraph_ids": ["p1"], "header_variant": "odd", "footer_variant": "odd", "page_source": "last_rendered"}],
        headers=[{"section_index": 0, "variant": "odd", "text": "摘 要", "paragraphs": [_paragraph("摘 要", font="黑体", size=10.5, alignment="left")]}],
        footers=[{"section_index": 0, "variant": "odd", "paragraphs": [_paragraph("Ⅰ", font="Arial", size=12, alignment="right", field=True)]}],
    )
    errors = _run(document, "header_footer_format", {
        "front_header": {"font": "宋体", "size_pt": 10.5, "alignment": "center"},
        "page_number": {"font": "Times New Roman", "size_pt": 10.5, "alignment": "center"},
        "odd_even": True,
    })
    assert {error.type for error in errors} == {"header_footer_format_error"}
    assert all(error.rule_id == "check" for error in errors)
    assert any(error.location == "section-0:odd-even" for error in errors)
    assert any(error.location == "header" and error.current == "黑体" for error in errors)
    assert any(error.location == "page-number" and error.current == "Arial" for error in errors)


def test_header_footer_format_accepts_matching_styles_without_body_header_style_checks() -> None:
    document = Document(
        document_id="D1", source_filename="x.docx",
        paragraphs=[{"paragraph_id": "p1", "text": "摘要", "structure": "abstract", "structure_role": "title", "page_index": 0}],
        sections=[{"index": 0, "odd_and_even_pages_header_footer": True}],
        pages=[{"page_index": 0, "section_index": 0, "paragraph_ids": ["p1"], "header_variant": "odd", "footer_variant": "odd", "page_source": "last_rendered"}],
        headers=[{"section_index": 0, "variant": "odd", "text": "摘 要", "paragraphs": [_paragraph("摘 要", font="宋体", size=10.5, alignment="center")]}],
        footers=[{"section_index": 0, "variant": "odd", "paragraphs": [_paragraph("Ⅰ", font="Times New Roman", size=10.5, alignment="center", field=True)]}],
    )
    assert _run(document, "header_footer_format", {
        "front_header": {"font": "宋体", "size_pt": 10.5, "alignment": "center"},
        "page_number": {"font": "Times New Roman", "size_pt": 10.5, "alignment": "center"},
        "odd_even": True,
    }) == []


def test_page_number_segments_reports_wrong_front_format_and_body_restart() -> None:
    document = Document(
        document_id="D1", source_filename="x.docx",
        paragraphs=[
            {"paragraph_id": "p1", "text": "摘要", "structure": "abstract", "structure_role": "title", "page_index": 0},
            {"paragraph_id": "p2", "text": "绪论", "page_index": 1, "heading": {"level": 1}},
        ],
        pages=[
            {"page_index": 0, "section_index": 0, "paragraph_ids": ["p1"], "page_number": 1, "number_format": "decimal", "position": "footer", "page_source": "last_rendered", "fields": [{"instruction": "PAGE", "part": "footer"}]},
            {"page_index": 1, "section_index": 1, "paragraph_ids": ["p2"], "page_number": 2, "number_format": "decimal", "position": "footer", "page_source": "last_rendered", "fields": [{"instruction": "PAGE", "part": "footer"}]},
        ],
    )
    errors = _run(document, "page_number_segments", {"front_format": "roman", "body_format": "decimal", "start": 1})
    assert {error.location for error in errors} == {"section-0:page-number", "section-1:page-number"}
    assert all(error.type == "page_number_segments_error" for error in errors)


def test_page_number_segments_accepts_lower_roman_and_skips_unknown_body_start() -> None:
    document = Document(
        document_id="D1", source_filename="x.docx",
        paragraphs=[{"paragraph_id": "p1", "text": "摘要", "structure": "abstract", "structure_role": "title", "page_index": 0}],
        pages=[{"page_index": 0, "section_index": 0, "paragraph_ids": ["p1"], "page_number": 1, "number_format": "lowerRoman", "position": "footer", "page_source": "last_rendered", "fields": [{"instruction": "PAGE", "part": "footer"}]}],
    )
    assert _run(document, "page_number_segments", {"front_format": "roman", "body_format": "decimal", "start": 1}) == []


def test_page_number_segments_ignores_cover_without_page_field() -> None:
    document = Document(
        document_id="D1", source_filename="x.docx",
        paragraphs=[{"paragraph_id": "p1", "text": "封面", "structure": "cover", "page_index": 0}],
        pages=[{"page_index": 0, "section_index": 0, "paragraph_ids": ["p1"], "page_number": 1, "number_format": None, "position": "none", "page_source": "section_settings", "fields": []}],
    )
    assert _run(document, "page_number_segments", {"front_format": "roman", "body_format": "decimal", "start": 1}) == []


def test_page_header_pattern_checks_current_chapter_on_reliable_pages_only() -> None:
    document = Document(
        document_id="D1", source_filename="x.docx",
        paragraphs=[
            {"paragraph_id": "p1", "text": "绪论", "page_index": 0, "heading": {"level": 1}},
            {"paragraph_id": "p2", "text": "第1章 研究背景", "page_index": 0, "heading": {"level": 1}},
            {"paragraph_id": "p3", "text": "正文", "page_index": 1},
            {"paragraph_id": "p4", "text": "第2章 系统设计", "page_index": 2, "heading": {"level": 1}},
            {"paragraph_id": "p5", "text": "第3章 实验", "page_index": 3, "heading": {"level": 1}},
        ],
        pages=[
            {"page_index": 0, "section_index": 0, "paragraph_ids": ["p1", "p2"], "header_text": "第1章 研究背景", "page_source": "last_rendered"},
            {"page_index": 1, "section_index": 0, "paragraph_ids": ["p3"], "header_text": "错误校名", "page_source": "last_rendered"},
            {"page_index": 2, "section_index": 0, "paragraph_ids": ["p4"], "header_text": "第1章 研究背景", "page_source": "last_rendered"},
            {"page_index": 3, "section_index": 0, "paragraph_ids": ["p5"], "header_text": "错误校名", "page_source": "estimated"},
        ],
    )
    errors = _run(document, "page_header_pattern", {"even_text": "电子科技大学成都学院本科毕业论文"})
    assert {error.location for error in errors} == {"header:page-2", "header:page-3"}


def test_default_rules_register_confirmed_header_page_checks_without_unstated_styles() -> None:
    rules = load_rules(Path("rules/default.json"))
    checks = {check.id: check for check in rules.checks}
    assert checks["front-header-format"].type == "header_footer_format"
    assert checks["page-number-segments"].expected == {"front_format": "roman", "body_format": "decimal", "start": 1}
    assert checks["page-header-pattern"].expected["even_text"] == "电子科技大学成都学院本科毕业论文"
    assert all("character_spacing" not in check.type for check in rules.checks)
    assert "body_header_font" not in checks
