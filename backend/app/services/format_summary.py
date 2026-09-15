"""把解析后的 Document 聚合成「论文当前格式」摘要。

对齐 `论文格式检测系统接口设计文档_V1.0_.md` 第 7 章：只输出页边距、正文与标题的字体字号行距，
不输出论文正文内容，避免把学生论文原文通过接口泄露出去。
"""

from collections import Counter
from typing import Any

from ..models.contracts import Document
from ..rules.targets import CHINESE_SIZES

POINTS_PER_CM = 28.3465
# python-docx 的行距：倍数时是 float（如 1.5），精确值时是 Length，拍平后为磅值（通常 > 10）。
_LINE_SPACING_MULTIPLE_MAX = 10
_PT_TO_CHINESE = {round(points, 2): name for name, points in CHINESE_SIZES.items()}


def _is_toc(paragraph: dict[str, Any]) -> bool:
    return str((paragraph.get("style") or {}).get("name") or "").lower().startswith("toc")


def _is_in_table(paragraph: dict[str, Any]) -> bool:
    return (paragraph.get("location") or {}).get("part") == "table"


def _first_run_style(paragraph: dict[str, Any]) -> tuple[str | None, float | None]:
    """取段落里第一个带文本的 run 的中文字体和字号。"""
    for run in paragraph.get("runs") or []:
        if not (run.get("text") or "").strip():
            continue
        font = (run.get("font") or {}).get("effective")
        return font or None, run.get("size_pt")
    return None, None


def _size_label(size_pt: float | None) -> str | None:
    if size_pt is None:
        return None
    rounded = round(float(size_pt), 2)
    return _PT_TO_CHINESE.get(rounded, f"{rounded:g}pt")


def _centimeters(points: float | None) -> str | None:
    if points is None:
        return None
    return f"{round(points / POINTS_PER_CM, 2):g}cm"


def _spacing_label(value: Any) -> str | None:
    """行距统一转成中文习惯写法：倍数写作「1.5倍」，精确值写作磅值。"""
    if value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if number <= _LINE_SPACING_MULTIPLE_MAX:
        return f"{number:g}倍"
    return f"{number:g}pt"


def _page_summary(document: Document) -> dict[str, Any]:
    sections = document.sections or []
    margins = (sections[0] if sections else {}).get("margins_pt") or {}
    labels = {side: _centimeters(margins.get(side)) for side in ("top", "right", "bottom", "left")}
    if not any(labels.values()):
        return {"margin": None}
    unique = {value for value in labels.values() if value is not None}
    # 四边一致时按接口文档示例返回单个字符串，不一致时保留各边数值。
    return {"margin": unique.pop() if len(unique) == 1 else labels}


def _body_summary(document: Document) -> dict[str, Any]:
    styles: Counter[tuple[str | None, float | None]] = Counter()
    spacings: Counter[Any] = Counter()
    for paragraph in document.paragraphs:
        if (paragraph.get("heading") or {}).get("level"):
            continue
        if _is_toc(paragraph) or _is_in_table(paragraph):
            continue
        if not (paragraph.get("text") or "").strip():
            continue
        font, size_pt = _first_run_style(paragraph)
        if font or size_pt is not None:
            styles[(font, size_pt)] += 1
        spacings[(paragraph.get("format") or {}).get("line_spacing")] += 1

    dominant = styles.most_common(1)[0][0] if styles else (None, None)
    dominant_spacing = spacings.most_common(1)[0][0] if spacings else None
    return {"font": dominant[0], "size": _size_label(dominant[1]), "line_spacing": _spacing_label(dominant_spacing)}


def _title_summary(document: Document) -> dict[str, Any]:
    """论文主标题取首个一级标题；没有一级标题时退回首个标题段落。"""
    headings = [
        paragraph
        for paragraph in document.paragraphs
        if (paragraph.get("heading") or {}).get("level")
        and not _is_toc(paragraph)
        and not _is_in_table(paragraph)
    ]
    if not headings:
        return {"font": None, "size": None}
    level_one = [paragraph for paragraph in headings if (paragraph.get("heading") or {}).get("level") == 1]
    target = (level_one or headings)[0]
    font, size_pt = _first_run_style(target)
    return {"font": font, "size": _size_label(size_pt)}


def summarize_document_format(document: Document) -> dict[str, Any]:
    """返回接口文档第 7 章约定的格式结构摘要。"""
    return {
        "page": _page_summary(document),
        "body": _body_summary(document),
        "title": _title_summary(document),
    }
