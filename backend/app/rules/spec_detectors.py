import re

from ..models.contracts import Document, ErrorItem
from .contracts import CheckRule
from .errors import make_error
from ..parser.styles import font_for_text, font_matches
from .detectors import _script_font, _script_segments
from .targets import CAPTION_RE, paragraph_text, size_to_pt, target_paragraphs


def detect_required_sections(document: Document, rule: CheckRule) -> list[ErrorItem]:
    titles = rule.expected.get("titles") or []
    present = {re.sub(r"\s+", "", paragraph_text(paragraph)) for paragraph in document.paragraphs}
    errors = []
    for title in titles:
        compact = re.sub(r"\s+", "", str(title))
        if any(item == compact or item.startswith(compact) for item in present):
            continue
        errors.append(make_error(rule, location="structure", content=str(title), current="missing", expected=str(title)))
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
        parts = [item.strip() for item in re.split(r"[;,；]", payload) if item.strip()]
        if not min_count <= len(parts) <= max_count:
            errors.append(make_error(rule, location=paragraph.get("paragraph_id", "paragraph"), content=text, current=str(len(parts)), expected=f"{min_count}-{max_count}"))

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
