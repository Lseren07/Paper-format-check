from pathlib import Path

from backend.app.models.contracts import Document
from backend.app.rules.service import check_document


def test_check_document_runs_default_rules_end_to_end() -> None:
    document = Document(document_id="D1", source_filename="x.docx", paragraphs=[{
        "paragraph_id": "p-0001", "text": "正文", "heading": {"level": None},
        "style": {"name": "Normal"}, "format": {},
        "runs": [{"text": "正文", "font": {"effective": "黑体"}, "size_pt": None, "bold": None}],
    }])
    errors = check_document(document, Path("rules/default.json"))
    assert any(error.type == "font_error" for error in errors)
    assert errors == sorted(errors, key=lambda error: (error.location, error.error_id))


def test_default_rules_enable_heading_toc_reference_and_page_margin_checks() -> None:
    from backend.app.rules.loader import load_rules

    rule_types = {rule.type for rule in load_rules(Path("rules/default.json")).checks}
    assert {"heading_numbering", "toc_consistency", "reference_baseline", "page_margin", "required_sections", "caption_format", "keyword_format", "header_text", "paragraph_spacing"}.issubset(rule_types)
    assert "table_figure_format" not in rule_types


def test_page_margin_detector_reports_nonmatching_section_margin() -> None:
    document = Document(document_id="D1", source_filename="x.docx", sections=[{
        "index": 0, "margins_pt": {"top": 72, "right": 72, "bottom": 72, "left": 72},
    }])
    errors = check_document(document, {"schema_version": "1.0", "name": "x", "checks": [{
        "id": "margin", "type": "page_margin", "expected": {"margin": {"top": "2.5cm"}},
    }]})
    assert errors[0].location == "section-0:margin-top"
    assert errors[0].expected == "2.5cm"


def test_default_rules_accept_normalized_body_size_and_indent() -> None:
    document = Document(document_id="D1", source_filename="x.docx", paragraphs=[{
        "paragraph_id": "p-0001", "text": "正文", "heading": {"level": None},
        "style": {"name": "Normal"},
        "format": {"alignment": "justify", "line_spacing": 20, "first_line_indent_pt": 24},
        "runs": [{"text": "正文", "font": {"effective": "宋体"}, "size_pt": 12, "bold": None}],
    }])
    errors = check_document(document, Path("rules/default.json"))
    assert {error.type for error in errors}.isdisjoint({"size_error", "paragraph_indent_error"})


def test_default_rules_do_not_apply_body_format_to_table_cell_paragraphs() -> None:
    document = Document(document_id="D1", source_filename="x.docx", paragraphs=[{
        "paragraph_id": "p-0001", "text": "表格正文", "heading": {"level": None},
        "style": {"name": "Normal"}, "location": {"part": "table"}, "format": {},
        "runs": [{"text": "表格正文", "font": {"effective": "黑体"}, "size_pt": 12, "bold": None}],
    }])
    errors = check_document(document, Path("rules/default.json"))
    assert not any(
        error.rule_id in {"body-font", "body-size", "body-alignment", "body-line-spacing"}
        and str(error.location).startswith("p-0001")
        for error in errors
    )
