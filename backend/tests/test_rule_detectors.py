from backend.app.models.contracts import Document
from backend.app.rules.contracts import CheckRule, RuleTarget
from backend.app.rules.detectors import detect_alignment, detect_bold, detect_font, detect_line_spacing, detect_paragraph_indent, detect_size


def check_rule(rule_id: str, rule_type: str, expected: dict) -> CheckRule:
    return CheckRule(id=rule_id, type=rule_type, target="all", expected=expected)


def document_with_paragraph(*, text="正文", font="黑体", alignment=None, line_spacing=None) -> Document:
    return Document(document_id="D1", source_filename="x.docx", paragraphs=[{
        "paragraph_id": "p-0001", "text": text, "style": {"name": "Normal"},
        "heading": {"level": None}, "format": {"alignment": alignment, "line_spacing": line_spacing},
        "runs": [{"text": text, "font": {"effective": font}, "size_pt": None, "bold": None}],
    }])


def test_font_detector_reports_run_font_mismatch() -> None:
    errors = detect_font(document_with_paragraph(font="黑体"), check_rule("body-font", "font", {"font": "宋体"}))
    assert len(errors) == 1
    assert errors[0].current == "黑体"
    assert errors[0].expected == "宋体"


def test_alignment_and_spacing_detectors_accept_matching_values() -> None:
    document = document_with_paragraph(alignment="justify", line_spacing=1.5)
    assert detect_alignment(document, check_rule("a", "alignment", {"alignment": "justify"})) == []
    assert detect_line_spacing(document, check_rule("s", "line_spacing", {"line_spacing": 1.5})) == []


def test_size_detector_normalizes_chinese_size_to_points() -> None:
    document = document_with_paragraph()
    document.paragraphs[0]["runs"][0]["size_pt"] = 12
    assert detect_size(document, check_rule("body-size", "size", {"size": "小四"})) == []


def test_paragraph_indent_converts_two_characters_using_run_size() -> None:
    document = document_with_paragraph()
    document.paragraphs[0]["runs"][0]["size_pt"] = 12
    document.paragraphs[0]["format"]["first_line_indent_pt"] = 12
    errors = detect_paragraph_indent(document, check_rule("indent", "paragraph_indent", {"first_line_indent": "2字符"}))
    assert errors[0].current == "12"
    assert errors[0].expected == "24"


def test_paragraph_indent_prefers_word_character_indent_over_mixed_run_sizes() -> None:
    document = document_with_paragraph()
    document.paragraphs[0]["runs"] = [
        {"text": "甲", "font": {"effective": "宋体"}, "size_pt": 9, "bold": None},
        {"text": "乙", "font": {"effective": "宋体"}, "size_pt": 12, "bold": None},
    ]
    document.paragraphs[0]["format"] = {"first_line_indent_pt": 6, "first_line_indent_chars": 2}
    assert detect_paragraph_indent(document, check_rule("indent", "paragraph_indent", {"first_line_indent": "2字符"})) == []


def test_structured_target_matches_its_heading_level() -> None:
    document = document_with_paragraph(font="宋体")
    document.paragraphs[0]["heading"] = {"level": 1}
    rule = CheckRule(id="heading-font", type="font", target=RuleTarget(name="heading", heading_level=1), expected={"font": "黑体"})
    assert len(detect_font(document, rule)) == 1


def test_font_errors_for_multiple_runs_have_distinct_locations_and_ids() -> None:
    document = document_with_paragraph()
    document.paragraphs[0]["runs"].append({"text": "续", "font": {"effective": "楷体"}, "size_pt": None, "bold": None})
    errors = detect_font(document, check_rule("font", "font", {"font": "宋体"}))
    assert [error.location for error in errors] == ["p-0001:run-0001", "p-0001:run-0002"]
    assert len({error.error_id for error in errors}) == 2


def test_size_and_bold_errors_for_multiple_runs_have_distinct_ids() -> None:
    document = document_with_paragraph()
    document.paragraphs[0]["runs"] = [
        {"text": "甲", "font": {"effective": "宋体"}, "size_pt": 10, "bold": False},
        {"text": "乙", "font": {"effective": "宋体"}, "size_pt": 9, "bold": False},
    ]
    size_errors = detect_size(document, check_rule("size", "size", {"size_pt": 12}))
    bold_errors = detect_bold(document, check_rule("bold", "bold", {"bold": True}))
    assert len({error.error_id for error in size_errors}) == 2
    assert len({error.error_id for error in bold_errors}) == 2
