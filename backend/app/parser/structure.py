"""Identify thesis regions without adding Document top-level fields."""

from __future__ import annotations

import re
from typing import Any

ABSTRACT_TITLE = re.compile(
    r"^(?:\u3010)?(?:\u4e2d\u6587)?\u6458\s*\u8981(?:\u3011)?(?:[:\uff1a])?$|^abstract(?:[:\uff1a])?\s*$",
    re.I,
)
KEYWORDS = re.compile(r"^\u5173\u952e\u8bcd|^key\s*words?\s*[:\uff1a]?", re.I)
TOC_TITLE = re.compile(r"^\u76ee\s*\u5f55$|^\u76ee\u5f55$", re.I)
REF_TITLE = re.compile(r"^\u53c2\u8003\u6587\u732e")
ACK = re.compile(r"^\u81f4\s*\u8c22$|^\u9644\u5f55")
CHAPTER = re.compile(r"^\u7b2c[\u4e00\u4e8c\u4e09\u56db\u4e94\u516d\u4e03\u516b\u4e5d\u5341\u767e\u96f6\d]+\u7ae0")
COVER_HINT = re.compile(r"\u6bd5\u4e1a\u8bba\u6587|\u5b66\u4f4d\u8bba\u6587|\u6bd5\u4e1a\u8bbe\u8ba1|\u5b66\u58eb\u5b66\u4f4d|\u6307\u5bfc\u6559\u5e08|\u5b66\s*\u53f7")
CAPTION_NUMBER = r"[\d\u4e00\u4e8c\u4e09\u56db\u4e94\u516d\u4e03\u516b\u4e5d\u5341\u767e\u5343]+(?:\s*[-.\u2013\u2014\u2010\uff0e\u00b7]\s*[\d\u4e00\u4e8c\u4e09\u56db\u4e94\u516d\u4e03\u516b\u4e5d\u5341\u767e\u5343]+)*"
FIGURE_CAPTION = re.compile(rf"^(?:\u9644\u56fe|\u56fe|Figure|Fig\.?)\s*{CAPTION_NUMBER}", re.I)
TABLE_CAPTION = re.compile(rf"^(?:\u9644\u8868|\u8868|Table|Tab\.?)\s*{CAPTION_NUMBER}", re.I)
SEQ_FIGURE = re.compile(r"SEQ\s+(Figure|Fig\.?|\u56fe|\u9644\u56fe)", re.I)
SEQ_TABLE = re.compile(r"SEQ\s+(Table|Tab\.?|\u8868|\u9644\u8868)", re.I)


def _is_document(paragraph: dict[str, Any]) -> bool:
    return (paragraph.get("location") or {}).get("part", "document") == "document"


def _text(paragraph: dict[str, Any]) -> str:
    return (paragraph.get("text") or "").strip()


def _style_name(paragraph: dict[str, Any]) -> str:
    return ((paragraph.get("style") or {}).get("name") or "").strip()


def _size(paragraph: dict[str, Any]) -> float:
    sizes = [float(run.get("size_pt")) for run in paragraph.get("runs") or [] if run.get("size_pt") is not None]
    return max(sizes) if sizes else -1.0


def _find(pattern: re.Pattern[str], paragraphs: list[dict[str, Any]], start: int = 0) -> int | None:
    for index in range(start, len(paragraphs)):
        if pattern.match(_text(paragraphs[index])):
            return index
    return None


def _is_cover_style(paragraph: dict[str, Any]) -> bool:
    name = _style_name(paragraph)
    lowered = name.lower()
    if lowered.startswith("heading") or "\u6807\u9898" in name and "\u8bba\u6587\u9898\u76ee" not in name:
        return False
    return "\u5c01\u9762" in name or "\u8bba\u6587\u9898\u76ee" in name or lowered in {"title", "cover"}


def _is_abstract_title(paragraph: dict[str, Any]) -> bool:
    text = _text(paragraph)
    if ABSTRACT_TITLE.match(text):
        return True
    name = _style_name(paragraph)
    return name in {"\u6458\u8981", "Abstract"} and len(text) <= 40


def _fields(paragraph: dict[str, Any]) -> str:
    return " ".join(str(item) for item in (paragraph.get("fields") or []))


def annotate_structure(paragraphs: list[dict[str, Any]], tables: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    body = [paragraph for paragraph in paragraphs if _is_document(paragraph)]
    table_blocks = {table.get("block_index") for table in (tables or []) if table.get("block_index") is not None}
    by_block = {item.get("block_index"): item for item in body if item.get("block_index") is not None}
    for paragraph in paragraphs:
        style_name = _style_name(paragraph)
        if style_name.lower().startswith("toc"):
            paragraph["structure"] = "toc"
        elif not _is_document(paragraph):
            paragraph.setdefault("structure", "table")
        else:
            paragraph.setdefault("structure", "body")

    abstract_idx = next((index for index, paragraph in enumerate(body) if _is_abstract_title(paragraph)), None)
    toc_idx = _find(TOC_TITLE, body)
    ref_idx = _find(REF_TITLE, body)
    keywords_idx = _find(KEYWORDS, body)
    cover_end = _cover_end(body, abstract_idx, toc_idx, keywords_idx)
    if cover_end:
        cover_paras = body[:cover_end]
        for paragraph in cover_paras:
            paragraph["structure"] = "cover"
        if cover_paras:
            title = max(cover_paras, key=lambda item: (_size(item), len(_text(item))))
            title["structure_role"] = "title"

    if abstract_idx is not None:
        body[abstract_idx]["structure"] = "abstract"
        body[abstract_idx]["structure_role"] = "title"
        end = len(body)
        for index in range(abstract_idx + 1, len(body)):
            text = _text(body[index])
            heading_level = (body[index].get("heading") or {}).get("level")
            if KEYWORDS.match(text) or TOC_TITLE.match(text) or REF_TITLE.match(text) or CHAPTER.match(text) or heading_level == 1:
                end = index
                break
            if FIGURE_CAPTION.match(text) or TABLE_CAPTION.match(text) or _caption_kind(body[index], table_blocks, by_block):
                end = index
                break
        for paragraph in body[abstract_idx + 1:end]:
            paragraph["structure"] = "abstract"
            paragraph["structure_role"] = "body"
        if end < len(body) and KEYWORDS.match(_text(body[end])):
            body[end]["structure"] = "keywords"

    if ref_idx is not None:
        body[ref_idx]["structure"] = "references"
        body[ref_idx]["structure_role"] = "title"
        end = len(body)
        for index in range(ref_idx + 1, len(body)):
            if ACK.match(_text(body[index])):
                end = index
                break
        for paragraph in body[ref_idx + 1:end]:
            paragraph["structure"] = "references"
            paragraph["structure_role"] = "body"

    for paragraph in body:
        if paragraph.get("structure") in {"cover", "abstract", "keywords", "references", "toc"}:
            continue
        kind = _caption_kind(paragraph, table_blocks, by_block)
        paragraph["structure"] = kind or "body"

    def ids(name: str, role: str | None = None) -> list[str]:
        result = []
        for paragraph in body:
            if paragraph.get("structure") != name:
                continue
            if role is not None and paragraph.get("structure_role") != role:
                continue
            result.append(paragraph["paragraph_id"])
        return result

    cover_title = next((item for item in body if item.get("structure") == "cover" and item.get("structure_role") == "title"), None)
    abstract_title = next((item for item in body if item.get("structure") == "abstract" and item.get("structure_role") == "title"), None)
    return {
        "cover": {"paragraph_ids": ids("cover"), "title": _text(cover_title) if cover_title else ""},
        "abstract": {"paragraph_ids": ids("abstract"), "title_paragraph_id": abstract_title["paragraph_id"] if abstract_title else None},
        "references": {"paragraph_ids": ids("references")},
        "figure_captions": ids("figure_caption"),
        "table_captions": ids("table_caption"),
    }


def _cover_end(body: list[dict[str, Any]], abstract_idx: int | None, toc_idx: int | None, keywords_idx: int | None) -> int | None:
    marker_ends = [index for index in (abstract_idx, toc_idx, keywords_idx) if index]
    if marker_ends:
        return min(marker_ends)
    boundary = None
    for index, paragraph in enumerate(body):
        heading_level = (paragraph.get("heading") or {}).get("level")
        if CHAPTER.match(_text(paragraph)) or heading_level == 1:
            boundary = index
            break
    prefix = body[:boundary] if boundary is not None else body
    if any(COVER_HINT.search(_text(paragraph)) or _is_cover_style(paragraph) for paragraph in prefix):
        return boundary if boundary is not None else len(body)
    return None


def _caption_kind(paragraph: dict[str, Any], table_blocks: set[Any], by_block: dict[Any, dict[str, Any]]) -> str | None:
    text = _text(paragraph)
    style = _style_name(paragraph)
    fields = _fields(paragraph)
    if FIGURE_CAPTION.match(text) or SEQ_FIGURE.search(fields):
        return "figure_caption"
    if TABLE_CAPTION.match(text) or SEQ_TABLE.search(fields):
        return "table_caption"
    if "\u56fe\u9898" in style:
        return "figure_caption"
    if "\u8868\u9898" in style:
        return "table_caption"
    is_caption_style = style.lower() == "caption" or "\u9898\u6ce8" in style
    if not is_caption_style:
        return None
    block = paragraph.get("block_index")
    previous = by_block.get(block - 1) if isinstance(block, int) else None
    nxt = by_block.get(block + 1) if isinstance(block, int) else None
    if paragraph.get("drawings") or (previous and previous.get("drawings")) or (nxt and nxt.get("drawings")):
        return "figure_caption"
    if isinstance(block, int) and ((block + 1) in table_blocks or (block - 1) in table_blocks):
        return "table_caption"
    return "figure_caption"
