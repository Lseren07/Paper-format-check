import re
from typing import Any

from ..models.contracts import Document
from .contracts import CheckRule


TITLE_PATTERNS = {
    "abstract-title": re.compile(r"^摘\s*要$"),
    "abstract-en-title": re.compile(r"^ABSTRACT$", re.I),
    "toc-title": re.compile(r"^目\s*录$"),
    "references-title": re.compile(r"^参考文献$"),
    "thanks-title": re.compile(r"^致\s*谢$"),
    "appendix-title": re.compile(r"^附\s*录"),
    "conclusion-title": re.compile(r"^结\s*论$"),
}
TITLE_BODY_REGION = {
    "abstract-title": "abstract-body",
    "abstract-en-title": "abstract-en-body",
    "toc-title": "toc-body",
    "references-title": "references-entry",
    "thanks-title": "thanks-body",
    "appendix-title": "appendix-body",
    "conclusion-title": "conclusion-body",
}
BODY_REGIONS = {"body", "abstract-body", "thanks-body", "appendix-body", "conclusion-body"}
KEYWORDS_ZH = re.compile(r"^关键词\s*[：:]")
KEYWORDS_EN = re.compile(r"^Keywords\s*[：:]", re.I)
CAPTION_RE = re.compile(r"^(图|表)\s*[\dA-Za-z]")
CHINESE_SIZES = {
    "初号": 42, "小初": 36, "一号": 26, "小一": 24, "二号": 22, "小二": 18,
    "三号": 16, "小三": 15, "四号": 14, "小四": 12, "五号": 10.5, "小五": 9,
}


def paragraph_text(paragraph: dict[str, Any]) -> str:
    return (paragraph.get("text") or "").strip()


def special_title_target(text: str) -> str | None:
    compact = (text or "").strip()
    for name, pattern in TITLE_PATTERNS.items():
        if pattern.match(compact):
            return name
    return None


def size_to_pt(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, str):
        if value in CHINESE_SIZES:
            return float(CHINESE_SIZES[value])
        try:
            return float(value)
        except ValueError:
            return None
    return float(value)


def _is_toc_style(paragraph: dict[str, Any]) -> bool:
    return str((paragraph.get("style") or {}).get("name") or "").lower().startswith("toc")


def paragraph_targets(document: Document) -> dict[str, set[str]]:
    mapping: dict[str, set[str]] = {}
    region = "body"
    for paragraph in document.paragraphs:
        text = paragraph_text(paragraph)
        assigned: set[str] = set()
        title = special_title_target(text)
        if title:
            assigned.add(title)
            region = TITLE_BODY_REGION.get(title, "body")
        elif KEYWORDS_ZH.match(text):
            assigned.add("keywords")
        elif KEYWORDS_EN.match(text):
            assigned.add("keywords-en")
        elif CAPTION_RE.match(text):
            assigned.add("figure-caption" if text.startswith("图") else "table-caption")
            assigned.add("caption")
        elif _is_toc_style(paragraph):
            assigned.add("toc-body")
        else:
            level = (paragraph.get("heading") or {}).get("level")
            if level:
                assigned.add(f"title{level}")
                assigned.add("heading")
                region = "body"
            else:
                assigned.add(region)
                if region in BODY_REGIONS:
                    assigned.add("body")
        mapping[str(paragraph.get("paragraph_id", ""))] = assigned
    return mapping


def target_paragraphs(document: Document, rule: CheckRule) -> list[dict[str, Any]]:
    assigned = paragraph_targets(document)
    matched: list[dict[str, Any]] = []
    for paragraph in document.paragraphs:
        targets = assigned.get(str(paragraph.get("paragraph_id", "")), set())
        target = rule.target
        if not isinstance(target, str):
            if target.name == "all" or (target.name == "body" and "body" in targets):
                matched.append(paragraph)
            elif target.heading_level is not None and f"title{target.heading_level}" in targets:
                matched.append(paragraph)
            continue
        if target == "all" or target in targets:
            matched.append(paragraph)
    return matched
