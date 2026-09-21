"""Identify thesis regions without adding Document top-level fields."""

from __future__ import annotations

import re
from typing import Any

ABSTRACT_TITLE = re.compile(
    r"^(?:\u3010)?(?:\u4e2d\u6587)?\u6458\s*\u8981(?:\u3011)?(?:[:\uff1a])?$|^abstract(?:[:\uff1a])?\s*$",
    re.I,
)
KEYWORDS = re.compile(r"^(?:\u5173\u952e\u8bcd\s*[:\uff1a]|Keywords\s*[:\uff1a])", re.I)
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
ABSTRACT_EN = re.compile(r"^ABSTRACT(?:[:\uff1a])?\s*$", re.I)
FOREIGN_TITLE = re.compile(r"^\u5916\u6587\u8d44\u6599\u539f\u6587$|^\u5916\u6587\u8d44\u6599\u8bd1\u6587$|^\u8bd1\s*\u6587$")
COVER_TITLE_LABEL = re.compile(r"^\u9898\s*\u76ee\s*[:\uff1a]")
SCHOOL_NAME = re.compile(r"\u7535\u5b50\u79d1\u6280\u5927\u5b66\u6210\u90fd\u5b66\u9662")
COVER_FIELD = re.compile(r"^(?:\u5b66\s*\u9662|\u4e13\s*\u4e1a|\u5b66\s*\u53f7|\u59d3\s*\u540d|\u6307\u5bfc|\u804c\s*\u79f0|\u7cfb\s*\u522b|\u5b8c\u6210\u65e5\u671f)")
COVER_BANNER = re.compile(r"\u672c\u79d1\u6bd5\u4e1a|\u6bd5\u4e1a\u8bba\u6587|\u6bd5\u4e1a\u8bbe\u8ba1")
SPECIAL_STRUCTURES = {"cover", "abstract", "abstract_en", "keywords", "keywords_en", "references", "toc", "foreign"}



def heading_level_from_style(name: str | None) -> int | None:
    style = (name or "").strip()
    if not style:
        return None
    if any(token in style for token in ("目录", "摘要", "外文", "封面", "toc")):
        return None
    numbered = re.search(r"([1-9])\s*级标题", style)
    if numbered:
        return int(numbered.group(1)) + 1
    match = re.search(r"(?:Heading|标题)\s*([1-9])", style, re.I)
    if match:
        return int(match.group(1))
    if "大标题" in style:
        return 1
    return None


def heading_level_from_style(name: str | None) -> int | None:
    style = (name or "").strip()
    if not style:
        return None
    if any(token in style for token in ("\u76ee\u5f55", "\u6458\u8981", "\u5916\u6587", "\u5c01\u9762", "toc")):
        return None
    numbered = re.search(r"([1-9])\s*\u7ea7\u6807\u9898", style)
    if numbered:
        return int(numbered.group(1)) + 1
    match = re.search(r"(?:Heading|\u6807\u9898)\s*([1-9])", style, re.I)
    if match:
        return int(match.group(1))
    if "\u5927\u6807\u9898" in style:
        return 1
    return None


_HEADING_NUMBER_RE = re.compile(
    r"^\s*(\d+(?:\.\d+)+)(?:\s*[.)\u3001\uff0e:]?)?(?=\s|[\u3400-\u9fff]|[A-Za-z]|$)"
)


def heading_level_from_text(text: str | None) -> int | None:
    """Infer a decimal numbered heading level when Word has no heading style."""
    match = _HEADING_NUMBER_RE.match((text or "").strip())
    return len(match.group(1).split(".")) if match else None


def _is_document(paragraph: dict[str, Any]) -> bool:
    return (paragraph.get("location") or {}).get("part", "document") == "document"


def _text(paragraph: dict[str, Any]) -> str:
    return (paragraph.get("text") or "").strip()


def _style_name(paragraph: dict[str, Any]) -> str:
    return ((paragraph.get("style") or {}).get("name") or "").strip()


def _size(paragraph: dict[str, Any]) -> float:
    sizes = [float(run.get("size_pt")) for run in paragraph.get("runs") or [] if run.get("size_pt") is not None]
    return max(sizes) if sizes else -1.0


TOC_PAGE_SUFFIX = re.compile(r"(?:\t|\s{2,})[\divxIVX]+\s*$", re.I)


def _is_toc_like(paragraph: dict[str, Any]) -> bool:
    if _style_name(paragraph).lower().startswith("toc"):
        return True
    return bool(TOC_PAGE_SUFFIX.search(_text(paragraph)))


def _find(pattern: re.Pattern[str], paragraphs: list[dict[str, Any]], start: int = 0) -> int | None:
    for index in range(start, len(paragraphs)):
        paragraph = paragraphs[index]
        if _is_toc_like(paragraph):
            continue
        if pattern.match(_text(paragraph)):
            return index
    return None


def _is_cover_style(paragraph: dict[str, Any]) -> bool:
    name = _style_name(paragraph)
    lowered = name.lower()
    if lowered.startswith("heading") or "\u6807\u9898" in name and "\u8bba\u6587\u9898\u76ee" not in name:
        return False
    return "\u5c01\u9762" in name or "\u8bba\u6587\u9898\u76ee" in name or lowered in {"title", "cover"}


def _is_zh_abstract_title(paragraph: dict[str, Any]) -> bool:
    text = _text(paragraph)
    if re.match(r"^(?:\u3010)?(?:\u4e2d\u6587)?\u6458\s*\u8981(?:\u3011)?(?:[:\uff1a])?$", text):
        return True
    return _style_name(paragraph) == "\u6458\u8981" and len(text) <= 40


def _is_en_abstract_title(paragraph: dict[str, Any]) -> bool:
    text = _text(paragraph)
    if ABSTRACT_EN.match(text):
        return True
    return _style_name(paragraph) == "Abstract" and 0 < len(text) <= 40


def _is_abstract_title(paragraph: dict[str, Any]) -> bool:
    return _is_zh_abstract_title(paragraph) or _is_en_abstract_title(paragraph)


def _fields(paragraph: dict[str, Any]) -> str:
    return " ".join(str(item) for item in (paragraph.get("fields") or []))



COVER_TOPIC = re.compile(r"^题\s*目")
COVER_META = re.compile(
    r"^(?:学\s*院|专\s*业|姓\s*名|学\s*号|指导教师|电子科技大学|毕业论文|本科毕业|学术诚信|版权)"
)


def _pick_cover_titles(cover_paras: list[dict[str, Any]]) -> list[dict[str, Any]]:
    styled = [
        paragraph for paragraph in cover_paras
        if "论文题目" in _style_name(paragraph) or "封面题目" in _style_name(paragraph)
    ]
    if styled:
        return styled
    topic = next((paragraph for paragraph in cover_paras if COVER_TOPIC.match(_text(paragraph))), None)
    if topic is not None:
        chosen = [topic]
        start = cover_paras.index(topic)
        for paragraph in cover_paras[start + 1:]:
            text = _text(paragraph)
            if not text:
                continue
            if COVER_META.match(text) or COVER_TOPIC.match(text):
                break
            chosen.append(paragraph)
            break
        return chosen
    scored: list[tuple[float, int, dict[str, Any]]] = []
    for paragraph in cover_paras:
        text = _text(paragraph)
        if not text or COVER_META.match(text):
            continue
        scored.append((abs(_size(paragraph) - 16.0), -len(text), paragraph))
    if not scored:
        return []
    scored.sort(key=lambda item: (item[0], item[1]))
    return [scored[0][2]]


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

    abstract_idx = next((index for index, paragraph in enumerate(body) if not _is_toc_like(paragraph) and _is_zh_abstract_title(paragraph)), None)
    zh_idx = abstract_idx
    toc_idx = _find(TOC_TITLE, body)
    ref_idx = _find(REF_TITLE, body)
    cover_end = _cover_end(body, abstract_idx, toc_idx, None)
    if cover_end:
        cover_paras = body[:cover_end]
        for paragraph in cover_paras:
            paragraph["structure"] = "cover"
        for title in _pick_cover_titles(cover_paras):
            title["structure_role"] = "title"

    if zh_idx is not None:
        body[zh_idx]["structure"] = "abstract"
        body[zh_idx]["structure_role"] = "title"
        end = len(body)
        for index in range(zh_idx + 1, len(body)):
            text = _text(body[index])
            heading_level = (body[index].get("heading") or {}).get("level")
            if (
                KEYWORDS.match(text) or TOC_TITLE.match(text) or REF_TITLE.match(text)
                or CHAPTER.match(text) or heading_level == 1 or ABSTRACT_EN.match(text)
                or FOREIGN_TITLE.match(text) or _is_en_abstract_title(body[index])
            ):
                end = index
                break
            if FIGURE_CAPTION.match(text) or TABLE_CAPTION.match(text) or _caption_kind(body[index], table_blocks, by_block):
                end = index
                break
        for paragraph in body[zh_idx + 1:end]:
            paragraph["structure"] = "abstract"
            paragraph["structure_role"] = "body"
        if end < len(body) and KEYWORDS.match(_text(body[end])):
            body[end]["structure"] = "keywords"

    if ref_idx is not None:
        body[ref_idx]["structure"] = "references"
        body[ref_idx]["structure_role"] = "title"
        end = len(body)
        for index in range(ref_idx + 1, len(body)):
            paragraph = body[index]
            if _is_toc_like(paragraph):
                continue
            if ACK.match(_text(paragraph)) or FOREIGN_TITLE.match(_text(paragraph)):
                end = index
                break
        for paragraph in body[ref_idx + 1:end]:
            if _is_toc_like(paragraph):
                continue
            paragraph["structure"] = "references"
            paragraph["structure_role"] = "body"

    _annotate_english_abstract(body, table_blocks, by_block)
    _annotate_foreign(body)

    for paragraph in body:
        if paragraph.get("structure") in SPECIAL_STRUCTURES:
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

def _is_excluded_cover_line(paragraph: dict[str, Any]) -> bool:
    text = _text(paragraph)
    if not text or SCHOOL_NAME.search(text):
        return True
    if COVER_TITLE_LABEL.match(text):
        return False
    if COVER_FIELD.match(text):
        return True
    return bool(COVER_BANNER.search(text) and "\u9898\u76ee" not in text)


def _pick_cover_title(cover_paras: list[dict[str, Any]]) -> dict[str, Any] | None:
    if not cover_paras:
        return None
    for paragraph in cover_paras:
        if "\u8bba\u6587\u9898\u76ee" in _style_name(paragraph) and _text(paragraph):
            return paragraph
    for paragraph in cover_paras:
        if COVER_TITLE_LABEL.match(_text(paragraph)):
            return paragraph
    candidates = [item for item in cover_paras if not _is_excluded_cover_line(item)]
    pool = candidates or cover_paras
    sized = [item for item in pool if 14 <= _size(item) <= 18]
    if sized:
        return max(sized, key=lambda item: len(_text(item)))
    return max(pool, key=lambda item: len(_text(item)))


def _stop_region(paragraph: dict[str, Any]) -> bool:
    text = _text(paragraph)
    return bool(
        KEYWORDS.match(text) or TOC_TITLE.match(text) or REF_TITLE.match(text)
        or CHAPTER.match(text) or ACK.match(text) or FOREIGN_TITLE.match(text)
        or _is_zh_abstract_title(paragraph) or ABSTRACT_EN.match(text)
    )


def _annotate_block(body: list[dict[str, Any]], start: int, structure: str, *, stop_heading1: bool = False) -> None:
    body[start]["structure"] = structure
    body[start]["structure_role"] = "title"
    end = len(body)
    for index in range(start + 1, len(body)):
        heading_level = (body[index].get("heading") or {}).get("level")
        if _stop_region(body[index]) or (stop_heading1 and heading_level == 1):
            end = index
            break
    for paragraph in body[start + 1:end]:
        if (paragraph.get("heading") or {}).get("level"):
            continue
        paragraph["structure"] = structure
        paragraph["structure_role"] = "body"


def _annotate_english_abstract(body: list[dict[str, Any]], table_blocks: set[Any], by_block: dict[Any, dict[str, Any]]) -> None:
    start = next((index for index, paragraph in enumerate(body) if _is_en_abstract_title(paragraph)), None)
    if start is None:
        return
    body[start]["structure"] = "abstract_en"
    body[start]["structure_role"] = "title"
    end = len(body)
    for index in range(start + 1, len(body)):
        text = _text(body[index])
        if _stop_region(body[index]):
            end = index
            break
        if FIGURE_CAPTION.match(text) or TABLE_CAPTION.match(text) or _caption_kind(body[index], table_blocks, by_block):
            end = index
            break
    for paragraph in body[start + 1:end]:
        if (paragraph.get("heading") or {}).get("level"):
            continue
        paragraph["structure"] = "abstract_en"
        paragraph["structure_role"] = "body"
    if end < len(body) and KEYWORDS.match(_text(body[end])):
        body[end]["structure"] = "keywords_en"


def _annotate_foreign(body: list[dict[str, Any]]) -> None:
    starts = [index for index, paragraph in enumerate(body) if FOREIGN_TITLE.match(_text(paragraph))]
    for start in starts:
        _annotate_block(body, start, "foreign")
