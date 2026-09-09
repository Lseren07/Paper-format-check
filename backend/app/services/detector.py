"""Rule-driven checks for the first DOCX format-checking slice."""

from __future__ import annotations

from typing import Any


def detect_format(document: dict[str, Any], rules: dict[str, Any]) -> list[dict[str, str]]:
    errors: list[dict[str, str]] = []
    _check_pages(document, rules["page"], errors)
    _check_paragraphs(document, rules, errors)
    return [_with_error_id(index, error) for index, error in enumerate(errors, start=1)]


def _check_pages(
    document: dict[str, Any], page_rules: dict[str, Any], errors: list[dict[str, str]]
) -> None:
    for section in document.get("sections", []):
        location = f"第{section.get('index', 0) + 1}节页面设置"
        _compare(errors, "page_format_error", location, "页面尺寸", section.get("page_width_cm"), page_rules["width_cm"])
        _compare(errors, "page_format_error", location, "页面高度", section.get("page_height_cm"), page_rules["height_cm"])
        for side, expected in page_rules["margins_cm"].items():
            _compare(
                errors,
                "margin_error",
                location,
                f"{side}页边距",
                section.get("margins_cm", {}).get(side),
                expected,
                suffix="cm",
            )
        _compare(errors, "header_footer_error", location, "页眉距离", section.get("header_distance_cm"), page_rules["header_distance_cm"], suffix="cm")
        _compare(errors, "header_footer_error", location, "页脚距离", section.get("footer_distance_cm"), page_rules["footer_distance_cm"], suffix="cm")


def _check_paragraphs(
    document: dict[str, Any], rules: dict[str, Any], errors: list[dict[str, str]]
) -> None:
    body_rules = rules["body"]
    heading_rules = rules["headings"]
    for paragraph in document.get("paragraphs", []):
        if not paragraph.get("text", "").strip():
            continue
        level = paragraph.get("heading_level")
        expected = heading_rules.get(str(level), body_rules) if level else body_rules
        kind = "heading_format_error" if level else "body_format_error"
        location = f"第{paragraph.get('index', 0) + 1}段"
        _compare(errors, kind, location, "对齐方式", paragraph.get("alignment"), expected.get("alignment"))
        _compare(errors, kind, location, "段前间距", paragraph.get("space_before_pt"), expected.get("space_before_pt"), suffix="pt")
        _compare(errors, kind, location, "段后间距", paragraph.get("space_after_pt"), expected.get("space_after_pt"), suffix="pt")
        if not level:
            _compare(errors, kind, location, "首行缩进", paragraph.get("first_line_indent_pt"), expected.get("first_line_indent_pt"), suffix="pt")
            _compare(errors, kind, location, "行距规则", paragraph.get("line_spacing_rule"), expected.get("line_spacing_rule"))
            _compare(errors, kind, location, "行距", paragraph.get("line_spacing_pt"), expected.get("line_spacing_pt"), suffix="pt")
        for run in paragraph.get("runs", []):
            if not run.get("text", ""):
                continue
            _compare(errors, kind, location, "字体", run.get("font"), expected.get("font"))
            _compare(errors, kind, location, "字号", run.get("size_pt"), expected.get("size_pt"), suffix="pt")
            if expected.get("bold") is not None:
                _compare(errors, kind, location, "加粗", run.get("bold"), expected["bold"])


def _compare(
    errors: list[dict[str, str]],
    error_type: str,
    location: str,
    label: str,
    current: Any,
    expected: Any,
    suffix: str = "",
) -> None:
    if expected is None or _same_value(current, expected):
        return
    current_text = _format_value(current, suffix)
    expected_text = _format_value(expected, suffix)
    errors.append(
        {
            "type": error_type,
            "location": location,
            "content": label,
            "current": current_text,
            "expected": expected_text,
        }
    )


def _same_value(current: Any, expected: Any) -> bool:
    if isinstance(current, (int, float)) and isinstance(expected, (int, float)):
        return abs(float(current) - float(expected)) < 0.01
    return current == expected


def _format_value(value: Any, suffix: str) -> str:
    if value is None:
        return "未设置"
    return f"{value}{suffix}"


def _with_error_id(index: int, error: dict[str, str]) -> dict[str, str]:
    return {"error_id": f"ERR{index:03d}", **error}
