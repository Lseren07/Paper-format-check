import re
from typing import Any

from ..models.contracts import Document, ErrorItem
from .contracts import CheckRule
from .errors import make_error
from .targets import size_to_pt, target_paragraphs, paragraph_text


def _paragraphs(document: Document, rule: CheckRule):
    return target_paragraphs(document, rule)


def _format_error(rule: CheckRule, paragraph: dict[str, Any], current: Any, expected: Any, *, location: str | None = None) -> ErrorItem:
    return make_error(rule, location=location or paragraph.get("paragraph_id", "paragraph"), content=paragraph.get("text", ""), current=str(current), expected=str(expected))


def _run_location(paragraph: dict[str, Any], index: int) -> str:
    return f"{paragraph.get('paragraph_id', 'paragraph')}:run-{index:04d}"


def _values_equal(current: Any, expected: Any) -> bool:
    try:
        return abs(float(current) - float(expected)) <= 0.05
    except (TypeError, ValueError):
        return str(current) == str(expected)


def _cm_to_pt(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value) * 72 / 2.54
    match = re.fullmatch(r"(\d+(?:\.\d+)?)cm", str(value).strip())
    return float(match.group(1)) * 72 / 2.54 if match else None


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
        if not _values_equal(current, expected) and str(current) != str(expected):
            errors.append(_format_error(rule, paragraph, current, expected))
    return errors


def detect_alignment(document: Document, rule: CheckRule) -> list[ErrorItem]:
    expected = rule.expected.get("alignment")
    if expected is None:
        return []
    errors = []
    for paragraph in _paragraphs(document, rule):
        current = paragraph.get("format", {}).get("alignment")
        if current is None:
            continue
        if str(current) != str(expected):
            errors.append(_format_error(rule, paragraph, current, expected))
    return errors


def detect_line_spacing(document: Document, rule: CheckRule) -> list[ErrorItem]:
    return _paragraph_value(document, rule, "line_spacing")


def detect_paragraph_spacing(document: Document, rule: CheckRule) -> list[ErrorItem]:
    errors = []
    for paragraph in _paragraphs(document, rule):
        fmt = paragraph.get("format") or {}
        for key in ("space_before_pt", "space_after_pt"):
            expected = rule.expected.get(key)
            current = fmt.get(key)
            if expected is None or current is None:
                continue
            if not _values_equal(current, expected):
                errors.append(_format_error(rule, paragraph, current, expected))
    return errors


def _compare_char_indent(paragraph: dict[str, Any], expected_value: Any, chars_key: str, pt_key: str) -> tuple[Any, Any] | None:
    characters = re.fullmatch(r"(\d+(?:\.\d+)?)字符", str(expected_value))
    if characters is None:
        return None
    expected_characters = float(characters.group(1))
    actual_characters = paragraph.get("format", {}).get(chars_key)
    if actual_characters is not None:
        return None if float(actual_characters) == expected_characters else (actual_characters, expected_characters)
    current = paragraph.get("format", {}).get(pt_key)
    size_pt = next((run.get("size_pt") for run in paragraph.get("runs", []) if run.get("size_pt") is not None), None)
    if current is None or size_pt is None:
        return None
    expected_pt = expected_characters * float(size_pt)
    if abs(float(current) - expected_pt) <= 0.05:
        return None
    return current, int(expected_pt) if float(expected_pt).is_integer() else expected_pt


def detect_paragraph_indent(document: Document, rule: CheckRule) -> list[ErrorItem]:
    errors = []
    for paragraph in _paragraphs(document, rule):
        for key, chars_key, pt_key in (
            ("first_line_indent", "first_line_indent_chars", "first_line_indent_pt"),
            ("hanging_indent", "hanging_indent_chars", "hanging_indent_pt"),
        ):
            if key not in rule.expected:
                continue
            mismatch = _compare_char_indent(paragraph, rule.expected[key], chars_key, pt_key)
            if mismatch:
                errors.append(_format_error(rule, paragraph, mismatch[0], mismatch[1]))
    if "first_line_indent_pt" in rule.expected and "first_line_indent" not in rule.expected:
        errors.extend(_paragraph_value(document, rule, "first_line_indent_pt"))
    return errors


def detect_size(document: Document, rule: CheckRule) -> list[ErrorItem]:
    expected = rule.expected.get("size_pt", rule.expected.get("size"))
    expected_pt = size_to_pt(expected)
    if expected_pt is None:
        return []
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


def _heading_number_parts(paragraph: dict[str, Any]) -> tuple[int, ...] | None:
    text = paragraph_text(paragraph)
    label = str((paragraph.get("numbering") or {}).get("label") or "")
    chapter = re.match(r"第\s*(\d+)\s*章", text) or re.match(r"第\s*(\d+)\s*章", label)
    if chapter:
        return (int(chapter.group(1)),)
    match = re.fullmatch(r"(\d+(?:\.\d+)*)\.?", label)
    if match is None:
        match = re.match(r"^(\d+(?:\.\d+)*)(?:[.\s]|$)", text)
    if match is None or paragraph.get("heading", {}).get("level") is None:
        return None
    return tuple(int(part) for part in match.group(1).split("."))


def detect_heading_numbering(document: Document, rule: CheckRule) -> list[ErrorItem]:
    expected_by_parent: dict[tuple[int, ...], int] = {}
    errors = []
    for paragraph in document.paragraphs:
        parts = _heading_number_parts(paragraph)
        if parts is None:
            continue
        parent, current = parts[:-1], parts[-1]
        expected = expected_by_parent.get(parent, 0) + 1
        expected_by_parent[parent] = current
        if current != expected:
            current_label = ".".join(str(part) for part in parts)
            prefix = ".".join(str(part) for part in parent)
            expected_label = f"{prefix}.{expected}" if prefix else str(expected)
            errors.append(_format_error(rule, paragraph, current_label, expected_label))
    return errors


def _normalized(text: str) -> str:
    return " ".join(text.split())


def _toc_text(text: str) -> str:
    return re.sub(r"\s+\d+$", "", _normalized(text))


def detect_toc_consistency(document: Document, rule: CheckRule) -> list[ErrorItem]:
    toc = {(_toc_text(item.get("text", "")), item.get("level")) for item in document.metadata.get("toc_paragraphs", [])}
    headings = {(_normalized(p.get("text", "")), p.get("heading", {}).get("level")) for p in document.paragraphs if p.get("heading", {}).get("level") is not None}
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
    page = rule.expected.get("page") or {}
    errors = []
    for section in document.sections:
        index = section.get("index", 0)
        for side, expected in margins.items():
            current = section.get("margins_pt", {}).get(side)
            expected_pt = _cm_to_pt(expected)
            if current is None or expected_pt is None:
                continue
            if abs(float(current) - expected_pt) > 0.01:
                errors.append(make_error(rule, location=f"section-{index}:margin-{side}", content="", current=str(current), expected=str(expected)))
        for key, expected in (("width_cm", page.get("width_cm")), ("height_cm", page.get("height_cm"))):
            current = section.get("page_width_pt" if key.startswith("width") else "page_height_pt")
            expected_pt = _cm_to_pt(expected)
            if current is None or expected_pt is None:
                continue
            if abs(float(current) - expected_pt) > 0.6:
                errors.append(make_error(rule, location=f"section-{index}:{key}", content="", current=str(current), expected=str(expected)))
        for name, expected in (("header", rule.expected.get("header")), ("footer", rule.expected.get("footer"))):
            current = section.get(f"{name}_distance_pt")
            expected_pt = _cm_to_pt(expected)
            if current is None or expected_pt is None:
                continue
            if abs(float(current) - expected_pt) > 0.05:
                errors.append(make_error(rule, location=f"section-{index}:{name}", content="", current=str(current), expected=str(expected)))
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


def detect_caption_position(document: Document, rule: CheckRule) -> list[ErrorItem]:
    expected = rule.expected.get("position")
    if expected is None:
        return []
    target = rule.target if isinstance(rule.target, str) else "figure_caption"
    errors = []
    paragraphs = document.paragraphs
    by_block = {item.get("block_index"): item for item in paragraphs if item.get("block_index") is not None}
    table_blocks = {table.get("block_index") for table in document.tables if table.get("block_index") is not None}
    for paragraph in paragraphs:
        if paragraph.get("structure") != target:
            continue
        block = paragraph.get("block_index")
        ok = False
        current = "missing"
        if target == "figure_caption":
            neighbor = by_block.get((block - 1) if expected == "below" and block is not None else (block + 1) if expected == "above" and block is not None else None)
            ok = bool(neighbor and neighbor.get("drawings"))
            current = "drawing" if ok else "missing-drawing"
        elif target == "table_caption" and block is not None:
            neighbor_block = block + 1 if expected == "above" else block - 1
            ok = neighbor_block in table_blocks
            current = "table" if ok else "missing-table"
        if not ok:
            errors.append(make_error(rule, location=paragraph.get("paragraph_id", target), content=paragraph.get("text", ""), current=current, expected=str(expected)))
    return errors


def detect_page_number(document: Document, rule: CheckRule) -> list[ErrorItem]:
    expected_position = rule.expected.get("position")
    expected_format = rule.expected.get("number_format")
    errors = []
    pages = document.pages or []
    if not pages:
        return [make_error(rule, location="page-number", content="", current="missing", expected=str(expected_position or "page field"))]
    seen_sections = set()
    for page in pages:
        section_index = page.get("section_index", 0)
        if section_index in seen_sections:
            continue
        seen_sections.add(section_index)
        current_pos = page.get("position") or "none"
        current_fmt = page.get("number_format")
        location = f"section-{section_index}:page-number"
        if expected_position and expected_position not in {current_pos, "header_footer"} and current_pos != "header_footer":
            errors.append(make_error(rule, location=location, content="", current=str(current_pos), expected=str(expected_position)))
            continue
        if expected_format and current_fmt != expected_format:
            errors.append(make_error(rule, location=location, content="", current=str(current_fmt), expected=str(expected_format)))
    if rule.expected.get("continuous"):
        grouped: dict[Any, list[dict[str, Any]]] = {}
        for page in pages:
            if page.get("page_number") is None:
                continue
            grouped.setdefault(page.get("section_index", 0), []).append(page)
        for section_index, group in grouped.items():
            expected_number = group[0]["page_number"]
            for page in group:
                current = page["page_number"]
                if current != expected_number:
                    errors.append(make_error(rule, location=f"section-{section_index}:page-number", content="", current=str(current), expected=str(expected_number)))
                expected_number += 1
    return errors
