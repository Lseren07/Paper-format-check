import re

from ..models.contracts import Document, ErrorItem
from .contracts import CheckRule
from .errors import make_error
from .targets import CAPTION_RE, paragraph_text, size_to_pt


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
    lowercase = bool(rule.expected.get("lowercase"))
    errors = []
    matched = False
    for paragraph in document.paragraphs:
        text = paragraph_text(paragraph)
        match = pattern.match(text)
        if match is None:
            continue
        matched = True
        payload = text[match.end():].strip()
        if payload.endswith(("。", ".", ";", "；", "，", ",")):
            errors.append(make_error(rule, location=paragraph.get("paragraph_id", "paragraph"), content=text, current=payload[-1], expected="no trailing punctuation"))
        parts = [item.strip() for item in re.split(r"[;；]", payload) if item.strip()]
        if not min_count <= len(parts) <= max_count:
            errors.append(make_error(rule, location=paragraph.get("paragraph_id", "paragraph"), content=text, current=str(len(parts)), expected=f"{min_count}-{max_count}"))
        if lowercase and any(any(char.isalpha() and char.isupper() for char in item) for item in parts):
            errors.append(make_error(rule, location=paragraph.get("paragraph_id", "paragraph"), content=text, current=payload, expected="lowercase keywords"))
    if rule.expected.get("required") and not matched:
        errors.append(make_error(rule, location="keywords", content="", current="missing", expected=pattern.pattern))
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
            current_font = (run.get("font") or {}).get("effective")
            if expected_font and current_font and current_font != expected_font:
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
    return [make_error(rule, location="header", content="", current="|".join(texts), expected=str(needle))]
