from pathlib import Path

from backend.app.models.contracts import Document
from backend.app.rules.loader import load_rules
from backend.app.rules.service import check_document


RULE_PATH = Path("rules/default.json")
BODY_TEXT = "正文"
MISMATCH_FONT = "黑体"


def _plain(paragraph_id: str, text: str) -> dict:
    return {
        "paragraph_id": paragraph_id, "text": text, "heading": {"level": None},
        "style": {"name": "Normal"}, "format": {}, "runs": [],
    }


def valid_document(font: str) -> Document:
    return Document(document_id="D1", source_filename="x.docx", paragraphs=[
        {
            "paragraph_id": "p-0001", "text": BODY_TEXT, "heading": {"level": None},
            "style": {"name": "Normal"}, "format": {},
            "runs": [{"text": BODY_TEXT, "font": {"effective": font}, "size_pt": None, "bold": None}],
        },
        _plain("p-0002", "摘要"),
        _plain("p-0003", "关键词：排队；系统；仿真"),
        _plain("p-0004", "目录"),
        _plain("p-0005", "参考文献"),
        _plain("p-0006", "致谢"),
    ], pages=[{
        "section_index": 0, "number_format": None, "position": "footer",
        "fields": [{"instruction": "PAGE", "part": "footer"}],
    }])


def test_load_school_rule_set() -> None:
    rules = load_rules(RULE_PATH)

    assert rules.name == "电子科技大学成都学院本科毕业论文格式规范"
    assert any(rule.id == "body-font" for rule in rules.checks)


def test_detector_accepts_document_matching_school_rules() -> None:
    rules = load_rules(RULE_PATH)
    expected_font = next(rule.expected["font"] for rule in rules.checks if rule.id == "body-font")

    assert expected_font == "宋体"
    assert check_document(valid_document(expected_font), rules) == []


def test_detector_reports_font_mismatch() -> None:
    rules = load_rules(RULE_PATH)
    expected_font = next(rule.expected["font"] for rule in rules.checks if rule.id == "body-font")
    document = valid_document(expected_font)
    document.paragraphs[0]["runs"][0]["font"]["effective"] = MISMATCH_FONT

    errors = check_document(document, RULE_PATH)

    assert len(errors) == 1
    assert errors[0].type == "font_error"
    assert errors[0].current == MISMATCH_FONT
    assert errors[0].expected == expected_font
