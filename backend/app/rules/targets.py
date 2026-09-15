import re
from typing import Any

from ..models.contracts import Document
from ..parser.structure import heading_level_from_style
from .contracts import CheckRule


TITLE_PATTERNS = {
    "abstract-title": re.compile(r"^摘\s*要$"),
    "abstract-en-title": re.compile(r"^ABSTRACT$", re.I),
    "toc-title": re.compile(r"^目\s*录$"),
    "references-title": re.compile(r"^参考文献$"),
    "thanks-title": re.compile(r"^致\s*谢$"),
    "appendix-title": re.compile(r"^附\s*录"),
    "conclusion-title": re.compile(r"^结\s*论$"),
    "foreign-title": re.compile(r"^外文资料原文$|^外文资料译文$|^译\s*文$"),
}
TITLE_BODY_REGION = {
    "abstract-title": "abstract-body",
    "abstract-en-title": "abstract-en-body",
    "toc-title": "toc-body",
    "references-title": "references-entry",
    "thanks-title": "thanks-body",
    "appendix-title": "appendix-body",
    "conclusion-title": "conclusion-body",
    "foreign-title": "foreign-body",
}
BODY_REGIONS = {"body", "abstract-body", "thanks-body", "appendix-body", "conclusion-body"}
KEEP_REGION_ON_HEADING = {"abstract-en-body", "foreign-body"}
CHAPTER_RE = re.compile(r"^第[一二三四五六七八九十百零\d]+\s*章")
KEYWORDS_ZH = re.compile(r"^关键词\s*[：:]")
KEYWORDS_EN = re.compile(r"^Keywords\s*[：:]", re.I)
CAPTION_RE = re.compile(r"^(图|表)\s*[\dA-Za-z]")
CHINESE_SIZES = {
    "初号": 42, "小初": 36, "一号": 26, "小一": 24, "二号": 22, "小二": 18,
    "三号": 16, "小三": 15, "四号": 14, "小四": 12, "五号": 10.5, "小五": 9,
}
HEADING_TARGETS = {f"title{level}" for level in range(1, 10)} | {"heading"}


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


def _location_part(paragraph: dict[str, Any]) -> str:
    return str((paragraph.get("location") or {}).get("part", "document"))


def _style_name(paragraph: dict[str, Any]) -> str:
    return str((paragraph.get("style") or {}).get("name") or "")


def _note_caption_targets(paragraph: dict[str, Any]) -> set[str]:
    style = _style_name(paragraph)
    text = paragraph_text(paragraph)
    if re.match(r"^??", text) or (text.startswith("?") and any(token in style for token in ("??", "??", "??"))):
        return {"table_caption", "table-caption", "caption"}
    if text and any(token in style for token in ("??", "??")):
        return {"figure_caption", "figure-caption", "caption"}
    return set()


def _skip_as_body(paragraph: dict[str, Any]) -> bool:
    style = _style_name(paragraph)
    text = paragraph_text(paragraph)
    if "??" in style:
        return True
    if any(token in style for token in ("??", "??", "??", "??", "??")):
        return True
    if paragraph.get("drawings") and not text:
        return True
    if not text:
        return True
    return False


def _note_caption_targets(paragraph: dict[str, Any]) -> set[str]:
    style = _style_name(paragraph)
    text = paragraph_text(paragraph)
    if re.match(r"^\u7eed\u8868", text) or (text.startswith("\u8868") and any(token in style for token in ("\u56fe\u6ce8", "\u8868\u6ce8", "\u8868\u9898"))):
        return {"table_caption", "table-caption", "caption"}
    if text and any(token in style for token in ("\u56fe\u6ce8", "\u56fe\u9898")):
        return {"figure_caption", "figure-caption", "caption"}
    return set()


def _skip_as_body(paragraph: dict[str, Any]) -> bool:
    style = _style_name(paragraph)
    text = paragraph_text(paragraph)
    if "\u5916\u6587" in style:
        return True
    if any(token in style for token in ("\u56fe\u7247", "\u56fe\u6ce8", "\u56fe\u9898", "\u8868\u6ce8", "\u8868\u9898")):
        return True
    if paragraph.get("drawings") and not text:
        return True
    if not text:
        return True
    return False


def paragraph_targets(document: Document) -> dict[str, set[str]]:
    mapping: dict[str, set[str]] = {}
    region = "body"
    seen_chapter = False
    for paragraph in document.paragraphs:
        pid = str(paragraph.get("paragraph_id", ""))
        if _location_part(paragraph) != "document":
            mapping[pid] = set()
            continue
        text = paragraph_text(paragraph)
        assigned: set[str] = set()
        if _is_toc_style(paragraph):
            assigned.add("toc-body")
        else:
            title = special_title_target(text)
            if title:
                assigned.add(title)
                region = TITLE_BODY_REGION.get(title, "body")
            elif KEYWORDS_ZH.match(text):
                assigned.add("keywords")
            elif KEYWORDS_EN.match(text):
                assigned.add("keywords-en")
            elif CAPTION_RE.match(text):
                assigned.add("figure-caption" if text.startswith("\u56fe") else "table-caption")
                assigned.add("caption")
            else:
                level = (paragraph.get("heading") or {}).get("level") or heading_level_from_style((paragraph.get("style") or {}).get("name"))
                if level:
                    if region in KEEP_REGION_ON_HEADING and not CHAPTER_RE.match(text):
                        assigned = set()
                    else:
                        assigned.add(f"title{level}")
                        assigned.add("heading")
                        region = "body"
                else:
                    assigned.add(region)
                    if region in BODY_REGIONS:
                        assigned.add("body")
        structure = paragraph.get("structure")
        role = paragraph.get("structure_role")
        if structure == "cover":
            assigned = {"cover"}
            if role == "title":
                assigned.add("cover_title")
        elif structure == "abstract":
            assigned = {"abstract", "abstract-body"} if role != "title" else {"abstract-title"}
        elif structure == "keywords":
            assigned = {"keywords"}
        elif structure == "references":
            assigned = {"references", "references-entry"} if role != "title" else {"references-title"}
        elif structure == "toc":
            assigned = {"toc-body"}
        elif structure == "body":
            level = (paragraph.get("heading") or {}).get("level") or heading_level_from_style((paragraph.get("style") or {}).get("name"))
            note = _note_caption_targets(paragraph)
            if note:
                assigned = note
            elif _skip_as_body(paragraph):
                assigned = set()
            elif level:
                if region in KEEP_REGION_ON_HEADING and not CHAPTER_RE.match(paragraph_text(paragraph)):
                    assigned = set()
                else:
                    assigned = {f"title{level}", "heading"}
                    if level == 1:
                        seen_chapter = True
            else:
                assigned.discard("toc-body")
                if seen_chapter:
                    assigned.difference_update({"abstract-title", "abstract-en-title"})
                if not assigned:
                    assigned = {"body"}
            if assigned and level and not (region in KEEP_REGION_ON_HEADING and not CHAPTER_RE.match(paragraph_text(paragraph))):
                region = "body"
        elif structure == "abstract_en":
            assigned = {"abstract-en-title" if role == "title" else "abstract-en-body"}
        elif structure == "foreign":
            assigned = {"foreign-title" if role == "title" else "foreign-body"}
        elif structure == "figure_caption":
            assigned = {"figure_caption", "figure-caption", "caption"}
        elif structure == "table_caption":
            assigned = {"table_caption", "table-caption", "caption"}
        elif structure == "table":
            assigned = set()
        mapping[pid] = assigned
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
