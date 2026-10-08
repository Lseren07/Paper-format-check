import re

from ..models.contracts import Document, ErrorItem
from .contracts import CheckRule
from .errors import make_error
from ..parser.styles import font_for_text, font_matches
from .detectors import _script_font, _script_segments
from .targets import CAPTION_RE, paragraph_text, size_to_pt, target_paragraphs


def detect_required_sections(document: Document, rule: CheckRule) -> list[ErrorItem]:
    titles = rule.expected.get("titles") or []
    present = {re.sub(r"\s+", "", paragraph_text(paragraph)): index for index, paragraph in enumerate(document.paragraphs)}
    errors: list[ErrorItem] = []
    found_positions: list[tuple[str, int]] = []
    for title in titles:
        compact = re.sub(r"\s+", "", str(title))
        boundary = re.compile(rf"^{re.escape(compact)}(?:$|[：:\s])")
        found = next(((item, index) for item, index in present.items() if item == compact or boundary.match(item)), None)
        if found:
            found_positions.append((compact, found[1]))
            continue
        errors.append(make_error(rule, location="structure", content=str(title), current="missing", expected=str(title)))
    if rule.expected.get("ordered"):
        positions = dict(found_positions)
        for title in rule.expected.get("optional_titles") or []:
            compact = re.sub(r"\s+", "", str(title))
            match = next(((item, index) for item, index in present.items() if item == compact), None)
            if match:
                positions[compact] = match[1]
        order = [re.sub(r"\s+", "", str(title)) for title in (rule.expected.get("order") or titles)]
        ordered_found = [(title, positions[title]) for title in order if title in positions]
        for (previous_title, previous_index), (current_title, current_index) in zip(ordered_found, ordered_found[1:]):
            if current_index < previous_index:
                errors.append(make_error(rule, location=f"structure:{current_title}", content=current_title, current="out-of-order", expected=f"after {previous_title}"))
    return errors


def detect_keyword_format(document: Document, rule: CheckRule) -> list[ErrorItem]:
    pattern = re.compile(str(rule.expected.get("pattern") or r"^关键词\s*[：:]"))
    min_count = int(rule.expected.get("min", 3))
    max_count = int(rule.expected.get("max", 8))
    errors: list[ErrorItem] = []
    matched = False
    for paragraph in target_paragraphs(document, rule):
        text = paragraph_text(paragraph)
        match = pattern.match(text)
        if match is None:
            continue
        matched = True
        fmt = paragraph.get("format") or {}
        expected_alignment = rule.expected.get("alignment")
        if expected_alignment and fmt.get("alignment") and fmt["alignment"] != expected_alignment:
            errors.append(make_error(rule, location=paragraph.get("paragraph_id", "paragraph"), content=text, current=str(fmt["alignment"]), expected=str(expected_alignment)))
        expected_indent = rule.expected.get("first_line_indent")
        current_indent = fmt.get("first_line_indent_chars")
        if expected_indent is not None and current_indent is not None and abs(float(current_indent) - float(expected_indent)) > 0.05:
            errors.append(make_error(rule, location=paragraph.get("paragraph_id", "paragraph"), content=text, current=str(current_indent), expected=str(expected_indent)))
        payload = text[match.end():].strip()
        if payload.endswith(("。", ".", ";", "；", "，", ",")):
            errors.append(make_error(rule, location=paragraph.get("paragraph_id", "paragraph"), content=text, current=payload[-1], expected="no trailing punctuation"))
        separator = rule.expected.get("separator")
        if separator == "semicolon" and re.search(r"[,，]", payload):
            errors.append(make_error(rule, location=paragraph.get("paragraph_id", "paragraph"), content=text, current="comma", expected="semicolon"))
        parts = [item.strip() for item in re.split(r"[;,；，,]", payload) if item.strip()]
        if not min_count <= len(parts) <= max_count:
            errors.append(make_error(rule, location=paragraph.get("paragraph_id", "paragraph"), content=text, current=str(len(parts)), expected=f"{min_count}-{max_count}"))
        if rule.expected.get("lowercase"):
            for keyword in parts:
                if keyword != keyword.lower():
                    errors.append(make_error(rule, location=f"{paragraph.get('paragraph_id', 'paragraph')}:keyword", content=text, current=keyword, expected=keyword.lower()))

        label_spec = rule.expected.get("label") or {}
        content_spec = rule.expected.get("content") or {}
        if not paragraph.get("runs"):
            continue
        offset = 0
        for index, run in enumerate(paragraph.get("runs") or [], start=1):
            run_text = run.get("text") or ""
            start, end = offset, offset + len(run_text)
            offset = end
            if not run_text:
                continue
            for area, fragment_start, fragment_end, spec in (
                ("label", start, min(end, match.end()), label_spec),
                ("content", max(start, match.end()), end, content_spec),
            ):
                if fragment_start >= fragment_end:
                    continue
                fragment = run_text[fragment_start - start:fragment_end - start]
                reported_scripts: set[str] = set()
                for script, segment in _script_segments(fragment):
                    if script == "neutral":
                        continue
                    current_font = _script_font(run.get("font") or {}, script, segment)
                    expected_font = spec.get("font")
                    expected_for_script = "Times New Roman" if script == "latin" else ("宋体" if script == "cjk" else expected_font)
                    if expected_font and current_font and current_font != expected_for_script and script not in reported_scripts:
                        location = f"{paragraph.get('paragraph_id', 'paragraph')}:run-{index:04d}:{area}:{script}"
                        errors.append(make_error(rule, location=location, content=segment, current=str(current_font), expected=str(expected_for_script)))
                        reported_scripts.add(script)
                expected_size = size_to_pt(spec.get("size"))
                current_size = run.get("size_pt")
                if expected_size is not None and current_size is not None and abs(float(current_size) - expected_size) > 0.05:
                    location = f"{paragraph.get('paragraph_id', 'paragraph')}:run-{index:04d}:{area}"
                    errors.append(make_error(rule, location=location, content=fragment, current=str(current_size), expected=str(expected_size)))
                if area == "label" and spec.get("bold") is not None and run.get("bold") is not None and bool(run.get("bold")) != bool(spec["bold"]):
                    location = f"{paragraph.get('paragraph_id', 'paragraph')}:run-{index:04d}:label"
                    errors.append(make_error(rule, location=location, content=fragment, current=str(bool(run.get("bold"))), expected=str(bool(spec["bold"]))))
    abstract_structure = "abstract_en" if str(rule.target) == "keywords-en" else "abstract"
    has_abstract_region = any(paragraph.get("structure") == abstract_structure for paragraph in document.paragraphs)
    if rule.expected.get("required") and has_abstract_region and not matched:
        errors.append(make_error(rule, location="keywords", content="", current="missing", expected="以“关键词：”开头"))
    return errors


def _word_count(text: str) -> int:
    """Count Latin words and individual CJK characters, ignoring punctuation/space."""
    cjk = re.findall(r"[\u3400-\u4dbf\u4e00-\u9fff\u3040-\u30ff]", text)
    latin = re.findall(r"[A-Za-z]+(?:['’][A-Za-z]+)?", text)
    return len(cjk) + len(latin)


def _cjk_character_count(text: str) -> int:
    return len(re.findall(r"[\u3400-\u4dbf\u4e00-\u9fff\u3040-\u30ff]", text))


def detect_abstract_length(document: Document, rule: CheckRule) -> list[ErrorItem]:
    structure = "abstract_en" if str(rule.target) == "abstract-en-body" else "abstract"
    paragraphs = [p for p in document.paragraphs if p.get("structure") == structure and p.get("structure_role") != "title"]
    content = " ".join(paragraph_text(p) for p in paragraphs)
    unit_name = rule.expected.get("unit")
    count = _cjk_character_count(content) if unit_name == "cjk_characters" else len(re.findall(r"[A-Za-z]+(?:['’][A-Za-z]+)?", content)) if unit_name == "english_words" else _word_count(content)
    minimum = rule.expected.get("min")
    maximum = rule.expected.get("max")
    if not content or (minimum is not None and count < int(minimum)) or (maximum is not None and count > int(maximum)):
        unit = "汉字" if rule.expected.get("unit") == "cjk_characters" else "词"
        expected = f"{minimum if minimum is not None else 0}-{maximum if maximum is not None else 'unbounded'}{unit}"
        return [make_error(rule, location="abstract-length", content=content, current=str(count), expected=expected)]
    return []


def detect_abstract_consistency(document: Document, rule: CheckRule) -> list[ErrorItem]:
    """Only verify both language versions exist; semantic equivalence is not machine-asserted."""
    zh = [p for p in document.paragraphs if p.get("structure") == "abstract" and p.get("structure_role") != "title"]
    en = [p for p in document.paragraphs if p.get("structure") == "abstract_en" and p.get("structure_role") != "title"]
    has_zh = any(paragraph_text(p) for p in zh)
    has_en = any(paragraph_text(p) for p in en)
    if has_zh == has_en:
        return []
    missing = "英文摘要" if has_zh else "中文摘要"
    return [make_error(rule, location="abstract-pair", content="", current=f"缺少{missing}", expected="中英文摘要均存在；语义一致需人工核对")]


def detect_page_break_after_heading(document: Document, rule: CheckRule) -> list[ErrorItem]:
    level = int(rule.expected.get("heading_level", 1))
    errors: list[ErrorItem] = []
    page_by_index = {page.get("page_index"): page for page in document.pages}
    paragraphs = [p for p in document.paragraphs if (p.get("location") or {}).get("part", "document") == "document"]
    for index, paragraph in enumerate(paragraphs):
        heading = paragraph.get("heading") or {}
        text = paragraph_text(paragraph)
        is_chapter = heading.get("level") == level and (level != 1 or re.match(r"^第\s*[一二三四五六七八九十百零\d]+\s*章", text))
        if not is_chapter or index == 0:
            continue
        previous = next((candidate for candidate in reversed(paragraphs[:index]) if paragraph_text(candidate)), None)
        if previous is None:
            continue
        if (paragraph.get("format") or {}).get("page_break_before") is True:
            continue
        current_page, previous_page = paragraph.get("page_index"), previous.get("page_index")
        if current_page is None or previous_page is None:
            continue
        current_page_data = page_by_index.get(current_page, {})
        previous_page_data = page_by_index.get(previous_page, {})
        sources = {paragraph.get("page_source"), previous.get("page_source"), current_page_data.get("page_source"), previous_page_data.get("page_source")}
        if "estimated" in sources or current_page_data.get("source") == "estimated" or previous_page_data.get("source") == "estimated":
            continue
        if current_page == previous_page:
            errors.append(make_error(rule, location=paragraph.get("paragraph_id", "paragraph"), content=text, current="same-page", expected="new-page"))
    return errors


def detect_formula_format(document: Document, rule: CheckRule) -> list[ErrorItem]:
    errors: list[ErrorItem] = []
    pattern = re.compile(str(rule.expected.get("number_pattern") or r"\(\d+(?:[-.]\d+)?\)$"))
    for paragraph in document.paragraphs:
        if not paragraph.get("formula"):
            continue
        pid = paragraph.get("paragraph_id", "formula")
        fmt = paragraph.get("format") or {}
        alignment = fmt.get("alignment")
        expected_alignment = rule.expected.get("alignment", "center")
        if alignment is not None and alignment != expected_alignment:
            errors.append(make_error(rule, location=f"{pid}:alignment", content=paragraph_text(paragraph), current=str(alignment), expected=str(expected_alignment)))
        for key in ("space_before_pt", "space_after_pt"):
            expected = rule.expected.get(key)
            current = fmt.get(key)
            if expected is not None and current is not None and abs(float(current) - float(expected)) > 0.05:
                errors.append(make_error(rule, location=f"{pid}:{key}", content=paragraph_text(paragraph), current=str(current), expected=str(expected)))
        minimum = rule.expected.get("min_line_spacing")
        current_line = fmt.get("line_spacing")
        if minimum is not None and current_line is not None and float(current_line) < float(minimum):
            errors.append(make_error(rule, location=f"{pid}:line-spacing", content=paragraph_text(paragraph), current=str(current_line), expected=f">={minimum}"))
        expected_rule = rule.expected.get("line_spacing_rule")
        current_rule = fmt.get("line_spacing_rule")
        if expected_rule and current_rule and str(current_rule).lower() != str(expected_rule).lower():
            errors.append(make_error(rule, location=f"{pid}:line-spacing-rule", content=paragraph_text(paragraph), current=str(current_rule), expected=str(expected_rule)))
        if not pattern.search(paragraph_text(paragraph).rstrip()):
            errors.append(make_error(rule, location=f"{pid}:number", content=paragraph_text(paragraph), current="missing-or-invalid", expected=str(rule.expected.get("number_pattern"))))
    return errors


def detect_caption_format(document: Document, rule: CheckRule) -> list[ErrorItem]:
    specs = {"图": rule.expected.get("figure") or {}, "表": rule.expected.get("table") or {}}
    errors = []
    for paragraph in document.paragraphs:
        match = CAPTION_RE.match(paragraph_text(paragraph))
        if match is None:
            continue
        spec = specs.get(match.group(1), {})
        expected_alignment = spec.get("alignment")
        current_alignment = (paragraph.get("format") or {}).get("alignment")
        if expected_alignment and current_alignment and current_alignment != expected_alignment:
            errors.append(make_error(rule, location=paragraph.get("paragraph_id", "paragraph"), content=paragraph.get("text", ""), current=str(current_alignment), expected=str(expected_alignment)))
        expected_font = spec.get("font")
        expected_pt = size_to_pt(spec.get("size"))
        for index, run in enumerate(paragraph.get("runs") or [], start=1):
            location = f"{paragraph.get('paragraph_id', 'paragraph')}:run-{index:04d}"
            current_font = font_for_text(run.get("font") or {}, run.get("text"))
            if expected_font and current_font and not font_matches(current_font, expected_font, run.get("text")):
                errors.append(make_error(rule, location=location, content=paragraph.get("text", ""), current=str(current_font), expected=str(expected_font)))
            current_size = run.get("size_pt")
            if expected_pt is not None and current_size is not None and float(current_size) != float(expected_pt):
                errors.append(make_error(rule, location=location, content=paragraph.get("text", ""), current=str(current_size), expected=str(expected_pt)))
    return errors


def detect_header_text(document: Document, rule: CheckRule) -> list[ErrorItem]:
    needle = rule.expected.get("contains")
    if not needle or not document.headers:
        return []
    items = document.headers
    variant = rule.expected.get("variant")
    if variant:
        items = [item for item in items if item.get("variant") == variant] or items
    texts = [str(item.get("text") or "") for item in items]
    if any(str(needle) in text for text in texts):
        return []
    return [make_error(rule, location="header", content="", current="|".join(texts) or "\u672a\u627e\u5230\u9875\u7709\u6587\u5b57", expected=str(needle))]
