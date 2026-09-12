"""Turn machine error locations into readable paper positions."""

from __future__ import annotations

import re

from ..models.contracts import Document, ErrorItem

_PARAGRAPH_RE = re.compile(r"^(p-\d+)(?::run-\d+)?$")
_MARGIN_RE = re.compile(r"^section-\d+:margin-(top|right|bottom|left)$")
_TABLE_RE = re.compile(r"^table-(\d+)$")
_DIGITS = "零一二三四五六七八九"

_MARGIN_LABELS = {
    "top": "上边距",
    "right": "右边距",
    "bottom": "下边距",
    "left": "左边距",
}


def format_location(document: Document, location: str) -> str:
    margin = _MARGIN_RE.fullmatch(location)
    if margin:
        return _MARGIN_LABELS[margin.group(1)]
    if location == "toc":
        return "目录"
    table = _TABLE_RE.fullmatch(location)
    if table:
        return f"表格{int(table.group(1)) + 1}"
    match = _PARAGRAPH_RE.fullmatch(location)
    if match is None:
        return location
    return _format_paragraph_location(document, match.group(1)) or location


def relocate_errors(document: Document, errors: list[ErrorItem]) -> list[ErrorItem]:
    return [
        error.model_copy(update={"location": format_location(document, error.location)})
        for error in errors
    ]


def _format_paragraph_location(document: Document, paragraph_id: str) -> str:
    parts = [_format_heading(item) for item in _heading_chain(document, paragraph_id)]
    paragraph = _find_paragraph(document, paragraph_id)
    table_label = _table_label(paragraph)
    if table_label:
        parts.append(table_label)
    readable = " ".join(part for part in parts if part)
    if readable:
        return readable
    ordinal = _paragraph_ordinal(paragraph_id)
    return ordinal or ""


def _heading_chain(document: Document, paragraph_id: str) -> list[dict]:
    index = _find_paragraph_index(document, paragraph_id)
    if index is None:
        return []
    current: dict[int, dict] = {}
    for paragraph in document.paragraphs[: index + 1]:
        if _is_toc(paragraph):
            continue
        level = (paragraph.get("heading") or {}).get("level")
        if not level:
            continue
        current = {key: value for key, value in current.items() if key < level}
        current[int(level)] = paragraph
    return [current[level] for level in sorted(current)]


def _format_heading(paragraph: dict) -> str:
    text = (paragraph.get("text") or "").strip()
    level = (paragraph.get("heading") or {}).get("level")
    numbering = paragraph.get("numbering") or {}
    label = numbering.get("label") if isinstance(numbering, dict) else None
    if label:
        formatted = _humanize_number_label(str(label), level)
        if formatted and formatted not in text:
            return f"{formatted} {text}".strip()
    return text


def _humanize_number_label(label: str, level: int | None) -> str:
    if re.fullmatch(r"\d+", label):
        number = _chinese_num(int(label))
        if level == 1:
            return f"第{number}章"
        if level == 2:
            return f"第{number}节"
    return label


def _chinese_num(value: int) -> str:
    if value < 0:
        return str(value)
    if value < 10:
        return _DIGITS[value]
    if value == 10:
        return "十"
    if value < 20:
        return "十" + _DIGITS[value - 10]
    if value < 100:
        tens, ones = divmod(value, 10)
        return _DIGITS[tens] + "十" + (_DIGITS[ones] if ones else "")
    return str(value)


def _table_label(paragraph: dict | None) -> str:
    if not paragraph:
        return ""
    location = paragraph.get("location") or {}
    if location.get("part") != "table":
        return ""
    index = location.get("table_index")
    if index is None:
        return "表格"
    return f"表格{int(index) + 1}"


def _paragraph_ordinal(paragraph_id: str) -> str:
    match = re.fullmatch(r"p-(\d+)", paragraph_id)
    if match is None:
        return ""
    return f"第{int(match.group(1))}段"


def _find_paragraph(document: Document, paragraph_id: str) -> dict | None:
    index = _find_paragraph_index(document, paragraph_id)
    if index is None:
        return None
    return document.paragraphs[index]


def _find_paragraph_index(document: Document, paragraph_id: str) -> int | None:
    for index, paragraph in enumerate(document.paragraphs):
        if paragraph.get("paragraph_id") == paragraph_id:
            return index
    return None


def _is_toc(paragraph: dict) -> bool:
    name = ((paragraph.get("style") or {}).get("name") or "")
    return name.lower().startswith("toc")
