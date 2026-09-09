import re
from typing import Any

from ..models.contracts import Document, ErrorItem
from .contracts import CheckRule
from .errors import make_error


def _target_matches(paragraph: dict[str, Any], target: str | Any) -> bool:
    if not isinstance(target, str):
        if target.name == "all":
            return True
        if target.name == "body":
            return paragraph.get("heading", {}).get("level") is None
        return target.heading_level is not None and paragraph.get("heading", {}).get("level") == target.heading_level
    if target in {"all", "body"}:
        return target == "all" or paragraph.get("heading", {}).get("level") is None
    level = paragraph.get("heading", {}).get("level")
    return target.lower().replace("title", "") == str(level)


def _paragraphs(document: Document, rule: CheckRule):
    return [p for p in document.paragraphs if _target_matches(p, rule.target)]


def _format_error(rule: CheckRule, paragraph: dict[str, Any], current: Any, expected: Any, *, location: str | None = None) -> ErrorItem:
    return make_error(rule, location=location or paragraph.get("paragraph_id", "paragraph"), content=paragraph.get("text", ""), current=str(current), expected=str(expected))


def _run_location(paragraph: dict[str, Any], index: int) -> str:
    return f"{paragraph.get('paragraph_id', 'paragraph')}:run-{index:04d}"


def detect_font(document: Document, rule: CheckRule) -> list[ErrorItem]:
    expected = rule.expected.get("font")
    if expected is None:
        return []
    errors = []
    for paragraph in _paragraphs(document, rule):
        for index, run in enumerate(paragraph.get("runs", []), start=1):
            current = (run.get("font") or {}).get("effective")
            if current is not None and current != expected:
                errors.append(_format_error(rule, paragraph, current, expected, location=_run_location(paragraph, index)))
    return errors


def _paragraph_value(document: Document, rule: CheckRule, key: str) -> list[ErrorItem]:
    expected = rule.expected.get(key)
    if expected is None:
        return []
    errors = []
    for paragraph in _paragraphs(document, rule):
        current = paragraph.get("format", {}).get(key)
        if current is None:
            continue
        if str(current) != str(expected):
            errors.append(_format_error(rule, paragraph, current, expected))
    return errors


def detect_alignment(document: Document, rule: CheckRule) -> list[ErrorItem]:
    return _paragraph_value(document, rule, "alignment")


def detect_line_spacing(document: Document, rule: CheckRule) -> list[ErrorItem]:
    return _paragraph_value(document, rule, "line_spacing")


def detect_paragraph_indent(document: Document, rule: CheckRule) -> list[ErrorItem]:
    expected = rule.expected.get("first_line_indent_pt")
    if expected is None and "first_line_indent" in rule.expected:
        characters = re.fullmatch(r"(\d+(?:\.\d+)?)字符", str(rule.expected["first_line_indent"]))
        if characters is None:
            return []
        expected_characters = float(characters.group(1))
        errors = []
        for paragraph in _paragraphs(document, rule):
            actual_characters = paragraph.get("format", {}).get("first_line_indent_chars")
            if actual_characters is not None:
                if float(actual_characters) != expected_characters:
                    errors.append(_format_error(rule, paragraph, actual_characters, expected_characters))
                continue
            current = paragraph.get("format", {}).get("first_line_indent_pt")
            size_pt = next((run.get("size_pt") for run in paragraph.get("runs", []) if run.get("size_pt") is not None), None)
            if current is None or size_pt is None:
                continue
            expected_pt = expected_characters * float(size_pt)
            if float(current) != expected_pt:
                errors.append(_format_error(rule, paragraph, current, int(expected_pt) if expected_pt.is_integer() else expected_pt))
        return errors
    return _paragraph_value(document, rule, "first_line_indent_pt")


def detect_size(document: Document, rule: CheckRule) -> list[ErrorItem]:
    expected = rule.expected.get("size_pt", rule.expected.get("size"))
    if expected is None:
        return []
    chinese_sizes = {"初号": 42, "小初": 36, "一号": 26, "小一": 24, "二号": 22, "小二": 18, "三号": 16, "小三": 15, "四号": 14, "小四": 12, "五号": 10.5, "小五": 9}
    expected_pt = chinese_sizes.get(expected, expected) if isinstance(expected, str) else expected
    errors = []
    for paragraph in _paragraphs(document, rule):
        for index, run in enumerate(paragraph.get("runs", []), start=1):
            current = run.get("size_pt")
            if current is not None and float(current) != float(expected_pt):
                errors.append(_format_error(rule, paragraph, current, expected_pt, location=_run_location(paragraph, index)))
    return errors


def detect_bold(document: Document, rule: CheckRule) -> list[ErrorItem]:
    expected = rule.expected.get("bold")
    if expected is None:
        return []
    errors = []
    for paragraph in _paragraphs(document, rule):
        for index, run in enumerate(paragraph.get("runs", []), start=1):
            current = run.get("bold")
            if current is not None and current != expected:
                errors.append(_format_error(rule, paragraph, current, expected, location=_run_location(paragraph, index)))
    return errors


def detect_heading_numbering(document: Document, rule: CheckRule) -> list[ErrorItem]:
    expected_by_parent: dict[tuple[int, ...], int] = {}
    errors = []
    for paragraph in document.paragraphs:
        level = paragraph.get("heading", {}).get("level")
        label = (paragraph.get("numbering") or {}).get("label")
        match = re.fullmatch(r"(\d+(?:\.\d+)*)\.?", str(label or ""))
        if level is None or match is None:
            continue
        parts = tuple(int(part) for part in match.group(1).split("."))
        parent, current = parts[:-1], parts[-1]
        expected = expected_by_parent.get(parent, 0) + 1
        expected_by_parent[parent] = current
        if current != expected:
            prefix = ".".join(str(part) for part in parent)
            expected_label = f"{prefix + '.' if prefix else ''}{expected}"
            errors.append(_format_error(rule, paragraph, match.group(1), expected_label))
    return errors


def _normalized(text: str) -> str:
    return " ".join(text.split())


def _toc_text(text: str) -> str:
    normalized = _normalized(text)
    return re.sub(r"\s+\d+$", "", normalized)


def detect_toc_consistency(document: Document, rule: CheckRule) -> list[ErrorItem]:
    toc = {(_toc_text(item.get("text", "")), item.get("level")) for item in document.metadata.get("toc_paragraphs", [])}
    headings = {( _normalized(p.get("text", "")), p.get("heading", {}).get("level")) for p in document.paragraphs if p.get("heading", {}).get("level") is not None}
    errors = []
    for text, level in sorted(headings - toc):
        errors.append(make_error(rule, location="toc", content=text, current="missing", expected=f"level={level}"))
    for text, level in sorted(toc - headings):
        errors.append(make_error(rule, location="toc", content=text, current=f"level={level}", expected="no extra entry"))
    return errors


def detect_table_figure_format(document: Document, rule: CheckRule) -> list[ErrorItem]:
    expected_columns = rule.expected.get("columns")
    if expected_columns is None:
        return []
    errors = []
    for table in document.tables:
        columns = table.get("columns")
        if columns is None or columns == expected_columns:
            continue
        rows = table.get("rows", "?")
        errors.append(make_error(rule, location=f"table-{table.get('table_index', 0)}", content="", current=f"{rows}x{columns}", expected=f"columns={expected_columns}"))
    return errors


def detect_page_margin(document: Document, rule: CheckRule) -> list[ErrorItem]:
    margins = rule.expected.get("margin", {})
    errors = []
    for section in document.sections:
        for side, expected in margins.items():
            current = section.get("margins_pt", {}).get(side)
            if current is None:
                continue
            match = re.fullmatch(r"(\d+(?:\.\d+)?)cm", str(expected))
            expected_pt = float(match.group(1)) * 72 / 2.54 if match else None
            if expected_pt is not None and abs(float(current) - expected_pt) > 0.01:
                errors.append(make_error(rule, location=f"section-{section.get('index', 0)}:margin-{side}", content="", current=str(current), expected=str(expected)))
    return errors


def detect_reference_baseline(document: Document, rule: CheckRule) -> list[ErrorItem]:
    expected = 1
    errors = []
    in_references = False
    for paragraph in document.paragraphs:
        style = paragraph.get("style", {}).get("name", "")
        text = paragraph.get("text", "")
        if "参考文献" in text.strip():
            in_references = True
            continue
        match = re.match(r"\[(\d+)\]", text)
        has_reference_style = "reference" in style.lower() or "参考文献" in style
        if match is None or not (has_reference_style or in_references):
            continue
        current = int(match.group(1))
        if current != expected:
            errors.append(_format_error(rule, paragraph, current, expected))
        expected = current + 1
    return errors
