from pathlib import Path

from backend.app.models.contracts import Document
from backend.app.rules.loader import load_rules
from backend.app.rules.service import check_document


RULE_PATH = Path("rules/default.json")
BODY_TEXT = "正文"
MISMATCH_FONT = "黑体"


def valid_document(font: str) -> Document:
    return Document(document_id="D1", source_filename="x.docx", paragraphs=[{
        "paragraph_id": "p-0001", "text": BODY_TEXT, "heading": {"level": None},
        "style": {"name": "Normal"}, "format": {},
        "runs": [{"text": BODY_TEXT, "font": {"effective": font}, "size_pt": None, "bold": None}],
    }])


def test_load_school_rule_set() -> None:
    rules = load_rules(RULE_PATH)

    assert rules.name == "default-paper-format-rules"
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
