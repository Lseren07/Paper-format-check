import re
from typing import Any, Callable

from ..models.contracts import Document, ErrorItem
from .contracts import CheckRule
from .errors import make_error
from ..parser.styles import CJK, EAST_ASIAN_FONTS, font_for_text, font_matches
from .targets import size_to_pt, target_paragraphs, paragraph_text


_CJK_SCRIPT = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff\u3040-\u30ff]")


def _paragraphs(document: Document, rule: CheckRule):
    return target_paragraphs(document, rule)


def _format_error(rule: CheckRule, paragraph: dict[str, Any], current: Any, expected: Any, *, location: str | None = None, display: Callable[[Any], str] = str) -> ErrorItem:
    return make_error(rule, location=location or paragraph.get("paragraph_id", "paragraph"), content=paragraph.get("text", ""), current=display(current), expected=display(expected))


def _run_location(paragraph: dict[str, Any], index: int) -> str:
    return f"{paragraph.get('paragraph_id', 'paragraph')}:run-{index:04d}"


def _values_equal(current: Any, expected: Any) -> bool:
    try:
        return abs(float(current) - float(expected)) <= 0.05
    except (TypeError, ValueError):
        return str(current) == str(expected)


def _pt_to_cm(value: Any) -> str:
    return f"{float(value) * 2.54 / 72:.2f}cm"


def _cm_display(value: Any) -> str:
    text = str(value).strip()
    if text.endswith("cm"):
        return text
    try:
        return f"{float(text):.2f}cm"
    except ValueError:
        return text


def _cm_to_pt(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value) * 72 / 2.54
    match = re.fullmatch(r"(\d+(?:\.\d+)?)cm", str(value).strip())
    return float(match.group(1)) * 72 / 2.54 if match else None


def _number(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _trim(value: float) -> str:
    return f"{value:g}"


def _line_spacing_display(value: Any) -> str:
    """行距的数值本身不带单位：既可能是倍数也可能是固定磅值。

    Word 读出来的倍数不会超过 3（最大 3 倍），规范里的固定行距都是 17 磅以上，
    所以以 3 为界区分，与 format_summary.line_spacing_label 保持一致。
    """
    number = _number(value)
    if number is None:
        return str(value)
    return f"{_trim(number)}倍" if number <= 3 else f"{_trim(number)}磅"


def _pt_display(value: Any) -> str:
    number = _number(value)
    return str(value) if number is None else f"{_trim(number)}磅"


def _char_display(value: Any) -> str:
    number = _number(value)
    return str(value) if number is None else f"{_trim(number)}字符"


COVER_LABEL_RUN = re.compile(r"^题\s*目$")


def _run_is_checkable(run: dict[str, Any]) -> bool:
    text = (run.get("text") or "").strip()
    if not text:
        return False
    if COVER_LABEL_RUN.fullmatch(text):
        return False
    return True


def _script_segments(text: str) -> list[tuple[str, str]]:
    segments: list[tuple[str, str]] = []
    current_script: str | None = None
    current: list[str] = []
    for char in text:
        if _CJK_SCRIPT.search(char):
            script = "cjk"
        elif char.isalpha() or char.isdigit():
            script = "latin"
        else:
            script = current_script or "neutral"
        if script != current_script and current:
            segments.append((current_script or "neutral", "".join(current)))
            current = []
        current_script = script
        current.append(char)
    if current:
        segments.append((current_script or "neutral", "".join(current)))
    return segments


def _script_font(font: dict[str, Any], script: str, text: str) -> str | None:
    if script == "cjk":
        return font.get("east_asia") or font.get("eastAsia") or font_for_text(font, text)
    if script == "latin":
        return font.get("ascii") or font.get("hAnsi") or font_for_text(font, text)
    return None


def detect_font(document: Document, rule: CheckRule) -> list[ErrorItem]:
    expected = rule.expected.get("font")
    if expected is None:
        return []
    errors = []
    for paragraph in _paragraphs(document, rule):
        for index, run in enumerate(paragraph.get("runs", []), start=1):
            text = run.get("text") or ""
            if not _run_is_checkable(run):
                continue
            font = run.get("font") or {}
            mismatches: dict[str, str] = {}
            segments = _script_segments(text)
            is_heading = (paragraph.get("heading") or {}).get("level") is not None
            for script, segment in segments:
                current = _script_font(font, script, segment)
                if current is None or script == "neutral":
                    continue
                if is_heading and script == "latin" and re.fullmatch(r"\d+(?:\.\d+)*\.?", segment.strip()):
                    continue
                if script == "cjk" and expected not in EAST_ASIAN_FONTS:
                    continue
                expected_for_script = "Times New Roman" if script == "latin" else expected
                if current == expected_for_script:
                    continue
                if script == "cjk" and expected in {"\u5b8b\u4f53", "SimSun"} and current in {"\u5b8b\u4f53", "SimSun"}:
                    continue
                mismatches.setdefault(script, current)
            for script, current in mismatches.items():
                expected_for_script = "Times New Roman" if script == "latin" else expected
                has_mixed_script = any(item_script == "cjk" for item_script, _ in segments) and any(item_script == "latin" for item_script, _ in segments)
                location = f"{_run_location(paragraph, index)}:{script}" if has_mixed_script else _run_location(paragraph, index)
                errors.append(_format_error(rule, paragraph, current, expected_for_script, location=location))
    return errors


def _paragraph_value(document: Document, rule: CheckRule, key: str, *, display: Callable[[Any], str] = str) -> list[ErrorItem]:
    expected = rule.expected.get(key)
    if expected is None:
        return []
    errors = []
    for paragraph in _paragraphs(document, rule):
        current = paragraph.get("format", {}).get(key)
        if current is None:
            continue
        if not _values_equal(current, expected) and str(current) != str(expected):
            errors.append(_format_error(rule, paragraph, current, expected, display=display))
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
        if expected == "left" and current == "justify" and str(rule.target) in {"title2", "title3", "title4"}:
            continue
        if str(current) != str(expected):
            errors.append(_format_error(rule, paragraph, current, expected))
    return errors


def detect_line_spacing(document: Document, rule: CheckRule) -> list[ErrorItem]:
    return _paragraph_value(document, rule, "line_spacing", display=_line_spacing_display)


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
                errors.append(_format_error(rule, paragraph, current, expected, display=_pt_display))
    return errors


def _compare_char_indent(paragraph: dict[str, Any], expected_value: Any, chars_key: str, pt_key: str) -> tuple[Any, Any, Callable[[Any], str]] | None:
    """规范里的缩进以字符计，而段落上记的可能就是字符数，也可能只有磅值。

    两条分支的数值单位不同，所以把显示方式一并返回，避免把磅值标成字符。
    """
    characters = re.fullmatch(r"(\d+(?:\.\d+)?)字符", str(expected_value))
    if characters is None:
        return None
    expected_characters = float(characters.group(1))
    actual_characters = paragraph.get("format", {}).get(chars_key)
    if actual_characters is not None:
        if float(actual_characters) == expected_characters:
            return None
        return actual_characters, expected_characters, _char_display
    current = paragraph.get("format", {}).get(pt_key)
    size_pt = next((run.get("size_pt") for run in paragraph.get("runs", []) if run.get("size_pt") is not None), None)
    if current is None or size_pt is None:
        return None
    expected_pt = expected_characters * float(size_pt)
    if abs(float(current) - expected_pt) <= 0.05:
        return None
    return current, expected_pt, _pt_display


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
                errors.append(_format_error(rule, paragraph, mismatch[0], mismatch[1], display=mismatch[2]))
    if "first_line_indent_pt" in rule.expected and "first_line_indent" not in rule.expected:
        errors.extend(_paragraph_value(document, rule, "first_line_indent_pt", display=_pt_display))
    return errors


def detect_size(document: Document, rule: CheckRule) -> list[ErrorItem]:
    expected = rule.expected.get("size_pt", rule.expected.get("size"))
    expected_pt = size_to_pt(expected)
    if expected_pt is None:
        return []
    errors = []
    for paragraph in _paragraphs(document, rule):
        for index, run in enumerate(paragraph.get("runs", []), start=1):
            if not _run_is_checkable(run):
                continue
            current = run.get("size_pt")
            if current is not None and float(current) != float(expected_pt):
                errors.append(_format_error(rule, paragraph, current, expected_pt, location=_run_location(paragraph, index), display=_pt_display))
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
    match = re.match(r"^\s*(\d+(?:\.\d+)*)(?:\s*[.)、．:]|\s+|(?=[^\d.]|$))", text)
    if match is None:
        match = re.fullmatch(r"(\d+(?:\.\d+)*)\.?", label)
    if match is None or paragraph.get("heading", {}).get("level") is None:
        return None
    return tuple(int(part) for part in match.group(1).split("."))


def detect_heading_numbering(document: Document, rule: CheckRule) -> list[ErrorItem]:
    expected_by_parent: dict[tuple[int, ...], int] = {}
    errors = []
    for paragraph in document.paragraphs:
        if (paragraph.get("structure") == "toc") or str((paragraph.get("style") or {}).get("name") or "").lower().startswith("toc"):
            continue
        if (paragraph.get("location") or {}).get("part", "document") != "document":
            continue
        parts = _heading_number_parts(paragraph)
        if parts is None:
            continue
        if rule.expected.get("require_title"):
            text = paragraph_text(paragraph)
            label = str((paragraph.get("numbering") or {}).get("label") or "")
            chapter_title = re.match(r"^第\s*[一二三四五六七八九十百零\d]+\s*章\s*(\S.*)$", text)
            decimal_title = re.match(r"^\s*\d+(?:\.\d+)*[.)、．:]?\s*([^\d.\s].*)$", text)
            has_title = bool(chapter_title or decimal_title or (label and text and not re.match(r"^\s*(?:第\s*\d+\s*章|\d+(?:\.\d+)*)\s*$", text)))
            if not has_title:
                errors.append(_format_error(rule, paragraph, "missing-title", "title"))
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


_HEADING_LABEL = re.compile(r"^\s*(\d+(?:\.\d+)+)(?:\s*[.)\u3001\uff0e:]?\s*)(.*?)\s*$")
_PLAIN_HEADING_LABEL = re.compile(r"^\s*(\d+)(?:\s*[.)\u3001\uff0e:]?\s+)(.*?)\s*$")
_CHAPTER_LABEL = re.compile(r"^\s*第([一二三四五六七八九十百零\d]+)\s*章\s*(.*?)\s*$")
_TOC_PAGE_SUFFIX = re.compile(r"(?:\t+|\s{2,})[\divxIVX]+\s*$", re.I)


def _heading_key_and_title(text: str, *, allow_plain_number: bool = False) -> tuple[str, str] | None:
    raw = str(text or "").strip()
    raw = _TOC_PAGE_SUFFIX.sub("", raw).strip()
    raw = re.sub(r"(\d+(?:\.\d+)*)\s*([\u4e00-\u9fff])", r"\1 \2", raw)
    match = _HEADING_LABEL.match(_normalized(raw))
    if match:
        return match.group(1), _normalized(match.group(2))
    if allow_plain_number:
        match = _PLAIN_HEADING_LABEL.match(_normalized(raw))
        if match:
            return match.group(1), _normalized(match.group(2))
    chapter = _CHAPTER_LABEL.match(_normalized(raw))
    if chapter:
        return f"chapter:{chapter.group(1)}", _normalized(chapter.group(2))
    return None


def detect_toc_consistency(document: Document, rule: CheckRule) -> list[ErrorItem]:
    body_titles: dict[str, str] = {}
    for paragraph in document.paragraphs:
        if (paragraph.get("location") or {}).get("part", "document") != "document":
            continue
        if str((paragraph.get("style") or {}).get("name") or "").lower().startswith("toc") or paragraph.get("structure") == "toc":
            continue
        heading_level = (paragraph.get("heading") or {}).get("level")
        parsed = _heading_key_and_title(paragraph.get("text", ""), allow_plain_number=heading_level is not None)
        if heading_level is None and (parsed is None or parsed[0].startswith("chapter:")):
            continue
        if parsed:
            body_titles[parsed[0]] = parsed[1]
    toc_titles: dict[str, str] = {}
    for item in document.metadata.get("toc_paragraphs", []):
        if isinstance(item, dict):
            toc_text = item.get("text", "")
        elif isinstance(item, (tuple, list)) and item:
            toc_text = item[0]
        else:
            toc_text = ""
        parsed = _heading_key_and_title(toc_text, allow_plain_number=True)
        if parsed:
            toc_titles[parsed[0]] = parsed[1]
        elif str(toc_text).strip().isdigit():
            toc_titles[str(toc_text).strip()] = ""
    errors = []
    for number, title in sorted(body_titles.items()):
        toc_title = toc_titles.get(number)
        if toc_title is None:
            errors.append(make_error(rule, location=f"toc:{number}", content=f"{number} {title}".strip(), current="missing", expected=title))
        elif toc_title != title:
            errors.append(make_error(rule, location=f"toc:{number}", content=number, current=toc_title, expected=title))
    for number, title in sorted(toc_titles.items()):
        if number not in body_titles:
            errors.append(make_error(rule, location=f"toc:{number}", content=number, current=title, expected="no extra entry"))
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
        errors.append(make_error(rule, location=f"table-{table.get('table_index', 0)}", content="", current=f"{rows}行{columns}列", expected=f"{expected_columns}列"))
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
            if abs(float(current) - expected_pt) > 0.5:
                errors.append(make_error(rule, location=f"section-{index}:margin-{side}", content="", current=_pt_to_cm(current), expected=_cm_display(expected)))
        for key, expected in (("width_cm", page.get("width_cm")), ("height_cm", page.get("height_cm"))):
            current = section.get("page_width_pt" if key.startswith("width") else "page_height_pt")
            expected_pt = _cm_to_pt(expected)
            if current is None or expected_pt is None:
                continue
            if abs(float(current) - expected_pt) > 0.6:
                errors.append(make_error(rule, location=f"section-{index}:{key}", content="", current=_pt_to_cm(current), expected=_cm_display(expected)))
        for name, expected in (("header", rule.expected.get("header")), ("footer", rule.expected.get("footer"))):
            current = section.get(f"{name}_distance_pt")
            expected_pt = _cm_to_pt(expected)
            if current is None or expected_pt is None:
                continue
            if abs(float(current) - expected_pt) > 0.05:
                errors.append(make_error(rule, location=f"section-{index}:{name}", content="", current=_pt_to_cm(current), expected=_cm_display(expected)))
    return errors


def detect_reference_baseline(document: Document, rule: CheckRule) -> list[ErrorItem]:
    expected = 1
    errors = []
    in_references = False
    reference_numbers: set[int] = set()
    citation_numbers: list[tuple[str, int]] = []
    for paragraph in document.paragraphs:
        style = paragraph.get("style", {}).get("name", "")
        text = paragraph.get("text", "")
        if "参考文献" in text.strip():
            in_references = True
            continue
        if not in_references and rule.expected.get("check_citations"):
            citation_numbers.extend((paragraph.get("paragraph_id", "paragraph"), int(number)) for number in re.findall(r"\[(\d+)\]", text))
        match = re.match(r"\[(\d+)\]", text)
        has_reference_style = "reference" in style.lower() or "参考文献" in style
        if match is None or not (has_reference_style or in_references):
            continue
        current = int(match.group(1))
        if current != expected:
            errors.append(_format_error(rule, paragraph, current, expected))
        expected = current + 1
        reference_numbers.add(current)
        ending = rule.expected.get("entry_ending")
        if ending and text.rstrip() and not text.rstrip().endswith(str(ending)):
            errors.append(make_error(rule, location=f"{paragraph.get('paragraph_id', 'paragraph')}:ending", content=text, current=text.rstrip()[-1], expected=str(ending)))
    if rule.expected.get("check_citations") and reference_numbers:
        unknown = sorted({number for _, number in citation_numbers if number not in reference_numbers})
        if unknown:
            errors.append(make_error(rule, location="citation-order", content=",".join(map(str, unknown)), current=f"未著录序号 {unknown}", expected="正文引用序号均能在参考文献中找到"))
        first_occurrence = list(dict.fromkeys(number for _, number in citation_numbers if number in reference_numbers))
        expected_order = list(range(1, len(first_occurrence) + 1))
        if first_occurrence and first_occurrence != expected_order:
            errors.append(make_error(rule, location="citation-order", content=",".join(map(str, first_occurrence)), current=f"首次引用顺序 {first_occurrence}", expected=f"{expected_order}（按正文首次引用顺序编号）"))
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
            errors.append(make_error(rule, location=paragraph.get("paragraph_id", target), content=paragraph.get("text", ""), current=current, expected=_caption_position_label(target, expected)))
    return errors


def _caption_position_label(target: str, position: Any) -> str:
    """规则里写的是 below/above，端到用户面前得说清是谁的哪一侧。"""
    subject = "表题" if target == "table_caption" else "图题"
    neighbour = "表格" if target == "table_caption" else "图片"
    side = {"below": "下方", "above": "上方"}.get(str(position))
    return f"{subject}应在{neighbour}{side}" if side else str(position)


def detect_page_number(document: Document, rule: CheckRule) -> list[ErrorItem]:
    expected_position = rule.expected.get("position")
    expected_format = rule.expected.get("number_format")
    errors = []
    pages = document.pages or []
    if not pages:
        return [make_error(rule, location="page-number", content="", current="missing", expected=str(expected_position or "page field"))]
    if expected_position:
        positions = {(page.get("position") or "none") for page in pages}
        if expected_position not in positions and "header_footer" not in positions:
            current = "none" if positions <= {"none"} else ",".join(sorted(positions))
            errors.append(make_error(rule, location="page-number", content="", current=current, expected=str(expected_position)))
    if expected_format:
        numbered = [page for page in pages if (page.get("position") or "none") != "none"]
        if numbered and not any(page.get("number_format") == expected_format for page in numbered):
            errors.append(make_error(rule, location="page-number", content="", current=str(numbered[0].get("number_format")), expected=str(expected_format)))
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


def _part_for_page(document: Document, page: dict[str, Any], part: str) -> dict[str, Any] | None:
    variant = page.get(f"{part}_variant")
    if variant is None:
        return None
    return next((item for item in getattr(document, f"{part}s", []) if item.get("section_index") == page.get("section_index") and item.get("variant") == variant), None)


def _style_value(run: dict[str, Any], key: str) -> Any:
    if key == "font":
        font = run.get("font") or {}
        return font.get("effective") or font.get("east_asia") or font.get("eastAsia") or font.get("ascii")
    return run.get(key)


def _format_mismatch(rule: CheckRule, *, location: str, current: Any, expected: Any, content: str = "") -> ErrorItem:
    return make_error(rule, location=location, content=content, current=str(current), expected=str(expected))


def _is_front_paragraph(paragraph: dict[str, Any]) -> bool:
    return paragraph.get("structure") in {"abstract", "abstract_en", "toc"}


def detect_header_footer_format(document: Document, rule: CheckRule) -> list[ErrorItem]:
    expected_header = rule.expected.get("front_header") or {}
    expected_page = rule.expected.get("page_number") or {}
    errors: list[ErrorItem] = []
    expected_texts = expected_header.get("text_by_structure") or {}
    front_page_indexes = {
        paragraph.get("page_index")
        for paragraph in document.paragraphs
        if _is_front_paragraph(paragraph) and paragraph.get("page_index") is not None
    }
    for page in document.pages:
        if page.get("page_index") not in front_page_indexes or page.get("page_source") == "estimated":
            continue
        header = _part_for_page(document, page, "header")
        if header is None:
            errors.append(_format_mismatch(rule, location="header", current="missing", expected=expected_header))
        else:
            if expected_texts:
                page_structures = {
                    str(paragraph.get("structure"))
                    for paragraph in document.paragraphs
                    if paragraph.get("page_index") == page.get("page_index") and paragraph.get("structure") in expected_texts
                }
                expected_text = next((str(expected_texts[name]) for name in ("abstract", "abstract_en", "toc") if name in page_structures), None)
                actual_text = str(header.get("text") or "")
                if expected_text is not None and re.sub(r"\s+", "", actual_text) != re.sub(r"\s+", "", expected_text):
                    errors.append(_format_mismatch(rule, location="header:text", current=actual_text or "missing", expected=expected_text, content=actual_text))
            paragraphs = header.get("paragraphs") or []
            for paragraph in paragraphs:
                content = paragraph.get("text", "")
                alignment = (paragraph.get("format") or {}).get("alignment")
                if expected_header.get("alignment") and alignment != expected_header["alignment"]:
                    errors.append(_format_mismatch(rule, location="header", current=alignment or "none", expected=expected_header["alignment"], content=content))
                for run in paragraph.get("runs") or []:
                    if not (run.get("text") or "").strip():
                        continue
                    for key in ("font", "size_pt"):
                        expected = expected_header.get(key)
                        current = _style_value(run, key)
                        if expected is not None and (not _values_equal(current, expected) if key == "size_pt" else current != expected):
                            errors.append(_format_mismatch(rule, location="header", current=current or "missing", expected=expected, content=content))
        footer = _part_for_page(document, page, "footer")
        if footer is not None:
            for paragraph in footer.get("paragraphs") or []:
                has_page = any("PAGE" in str(field).upper() for run in paragraph.get("runs") or [] for field in run.get("fields") or [])
                if not has_page:
                    continue
                expected_alignment = expected_page.get("alignment")
                alignment = (paragraph.get("format") or {}).get("alignment")
                if expected_alignment and alignment != expected_alignment:
                    errors.append(_format_mismatch(rule, location="page-number", current=alignment or "none", expected=expected_alignment, content=paragraph.get("text", "")))
                for run in paragraph.get("runs") or []:
                    if not any("PAGE" in str(field).upper() for field in run.get("fields") or []):
                        continue
                    for key in ("font", "size_pt"):
                        expected = expected_page.get(key)
                        current = _style_value(run, key)
                        if expected is not None and (not _values_equal(current, expected) if key == "size_pt" else current != expected):
                            errors.append(_format_mismatch(rule, location="page-number", current=current or "missing", expected=expected, content=paragraph.get("text", "")))
    if rule.expected.get("odd_even") is not None:
        for section in document.sections:
            if section.get("odd_and_even_pages_header_footer") is not True:
                errors.append(_format_mismatch(rule, location=f"section-{section.get('index', 0)}:odd-even", current="false", expected="true"))
    return errors


def _format_family(value: Any) -> str | None:
    if value in {"upperRoman", "lowerRoman", "roman"}:
        return "roman"
    if value in {"decimal", "arabic", "number"}:
        return "decimal"
    return None


def _body_start_page(document: Document) -> int | None:
    for paragraph in document.paragraphs:
        text = str(paragraph.get("text") or "").strip()
        if text in {"引言", "绪论"} or re.match(r"^第\s*1\s*章\s*(?:引言|绪论)", text):
            return paragraph.get("page_index")
    return None


def _has_page_field(page: dict[str, Any]) -> bool:
    for field in page.get("fields") or []:
        instruction = field.get("instruction", "") if isinstance(field, dict) else field
        if re.search(r"\bPAGE\b", str(instruction), re.I):
            return True
    return False


def detect_page_number_segments(document: Document, rule: CheckRule) -> list[ErrorItem]:
    pages = [
        page for page in document.pages
        if page.get("page_source") != "estimated"
        and page.get("page_number") is not None
        and _has_page_field(page)
    ]
    if not pages:
        return []
    expected_front = rule.expected.get("front_format", "roman")
    expected_body = rule.expected.get("body_format", "decimal")
    body_start = _body_start_page(document)
    errors: list[ErrorItem] = []
    for page in pages:
        is_body = body_start is not None and page.get("page_index", -1) >= body_start
        expected = expected_body if is_body else expected_front
        if _format_family(page.get("number_format")) != expected:
            errors.append(_format_mismatch(rule, location=f"section-{page.get('section_index', 0)}:page-number", current=page.get("number_format") or "none", expected=expected))
        if is_body and page.get("page_index") == body_start and page.get("page_number") != rule.expected.get("start", 1):
            errors.append(_format_mismatch(rule, location=f"section-{page.get('section_index', 0)}:page-number", current=page.get("page_number"), expected=rule.expected.get("start", 1)))
    return errors


_CHAPTER_HEADER = re.compile(r"^第\s*([一二三四五六七八九十百零\d]+)\s*章\s*(.*)$")


def _chapter_from_text(text: str) -> str | None:
    match = _CHAPTER_HEADER.match(text.strip())
    return f"第{match.group(1)}章 {match.group(2).strip()}".strip() if match else None


def detect_page_header_pattern(document: Document, rule: CheckRule) -> list[ErrorItem]:
    expected_even = rule.expected.get("even_text")
    errors: list[ErrorItem] = []
    current_chapter: str | None = None
    for page in sorted(document.pages, key=lambda item: item.get("page_index", 0)):
        for paragraph in document.paragraphs:
            if paragraph.get("page_index") != page.get("page_index"):
                continue
            chapter = _chapter_from_text(str(paragraph.get("text") or ""))
            if chapter:
                current_chapter = chapter
        if page.get("page_source") == "estimated":
            continue
        actual = str(page.get("header_text") or "").strip()
        location = f"header:page-{page.get('page_index', 0) + 1}"
        if (page.get("page_index", 0) + 1) % 2 == 0:
            if expected_even and actual != expected_even:
                errors.append(_format_mismatch(rule, location=location, current=actual or "missing", expected=expected_even, content=actual))
        elif current_chapter and actual != current_chapter:
            errors.append(_format_mismatch(rule, location=location, current=actual or "missing", expected=current_chapter, content=actual))
    return errors
