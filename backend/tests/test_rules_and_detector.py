from pathlib import Path
import json

from backend.app.services.detector import detect_format
from backend.app.services.rules import load_rules


RULE_PATH = Path("rules/electronic-tech-cdu-v1.json")


def valid_document() -> dict:
    return {
        "sections": [
            {
                "index": 0,
                "page_width_cm": 21.0,
                "page_height_cm": 29.7,
                "margins_cm": {"top": 3.5, "right": 3.0, "bottom": 3.5, "left": 3.0},
                "header_distance_cm": 2.75,
                "footer_distance_cm": 1.75,
            }
        ],
        "paragraphs": [
            {
                "index": 0,
                "text": "正文",
                "heading_level": None,
                "alignment": "justify",
                "space_before_pt": 6.0,
                "space_after_pt": 0.0,
                "first_line_indent_pt": 24.0,
                "line_spacing_rule": "exactly",
                "line_spacing_pt": 20.0,
                "runs": [{"text": "正文", "font": "宋体", "size_pt": 12.0, "bold": False}],
            },
            {
                "index": 1,
                "text": "第一章",
                "heading_level": 1,
                "alignment": "center",
                "space_before_pt": 30.0,
                "space_after_pt": 30.0,
                "runs": [{"text": "第一章", "font": "黑体", "size_pt": 15.0, "bold": True}],
            },
        ],
    }


def test_load_school_rule_set() -> None:
    rules = load_rules(RULE_PATH)

    assert rules["rule_set_id"] == "electronic-tech-cdu-v1"
    assert rules["page"]["margins_cm"] == {
        "top": 3.5,
        "right": 3.0,
        "bottom": 3.5,
        "left": 3.0,
    }
    assert rules["body"]["line_spacing_pt"] == 20.0
    assert rules["headings"]["1"]["size_pt"] == 15.0


def test_load_rules_rejects_incomplete_nested_structure(tmp_path: Path) -> None:
    source = tmp_path / "incomplete-rules.json"
    source.write_text(
        json.dumps(
            {
                "schema_version": "1.0",
                "rule_set_id": "incomplete",
                "page": {},
                "body": {},
                "headings": {},
            }
        ),
        encoding="utf-8",
    )

    try:
        load_rules(source)
    except ValueError as error:
        assert "page.width_cm" in str(error)
    else:
        raise AssertionError("incomplete nested rules must be rejected")


def test_detector_accepts_document_matching_school_rules() -> None:
    assert detect_format(valid_document(), load_rules(RULE_PATH)) == []


def test_detector_reports_page_body_and_heading_mismatches() -> None:
    document = valid_document()
    document["sections"][0]["margins_cm"]["left"] = 2.5
    document["paragraphs"][0]["runs"][0]["font"] = "黑体"
    document["paragraphs"][1]["runs"][0]["size_pt"] = 12.0
    document["paragraphs"][1]["alignment"] = "left"

    errors = detect_format(document, load_rules(RULE_PATH))

    assert [error["type"] for error in errors] == [
        "margin_error",
        "body_format_error",
        "heading_format_error",
        "heading_format_error",
    ]
    assert errors[0]["current"] == "2.5cm"
    assert errors[0]["expected"] == "3.0cm"
    assert errors[1]["content"] == "字体"
    assert errors[2]["content"] == "对齐方式"
    assert errors[3]["content"] == "字号"
    assert errors[0]["error_id"] == "ERR001"
