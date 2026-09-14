"""Build a human-readable format summary from a parsed Document."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from ..models.contracts import Document

CHINESE_SIZES = {
    "\u521d\u53f7": 42,
    "\u5c0f\u521d": 36,
    "\u4e00\u53f7": 26,
    "\u5c0f\u4e00": 24,
    "\u4e8c\u53f7": 22,
    "\u5c0f\u4e8c": 18,
    "\u4e09\u53f7": 16,
    "\u5c0f\u4e09": 15,
    "\u56db\u53f7": 14,
    "\u5c0f\u56db": 12,
    "\u4e94\u53f7": 10.5,
    "\u5c0f\u4e94": 9,
}
MISSING = "\u672a\u63d0\u4f9b"


def _majority(values: Iterable[Any]) -> Any | None:
    items = [value for value in values if value not in (None, "")]
    if not items:
        return None
    return max(set(items), key=items.count)


def size_name(size_pt: Any) -> str | None:
    if size_pt is None:
        return None
    number = float(size_pt)
    for name, value in CHINESE_SIZES.items():
        if abs(number - value) < 0.05:
            return name
    if number.is_integer():
        return str(int(number))
    return str(number)


def line_spacing_label(value: Any) -> str | None:
    if value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return str(value)
    if number <= 3:
        if number.is_integer():
            return f"{int(number)}\u500d"
        return f"{number}\u500d"
    return f"{number}\u78c5"


def _group(paragraphs: list[dict[str, Any]]) -> dict[str, str]:
    fonts = []
    sizes = []
    spacings = []
    for paragraph in paragraphs:
        fonts.extend((run.get("font") or {}).get("effective") for run in paragraph.get("runs") or [])
        sizes.extend(size_name(run.get("size_pt")) for run in paragraph.get("runs") or [])
        spacings.append(line_spacing_label((paragraph.get("format") or {}).get("line_spacing")))
    return {
        "font": _majority(fonts) or MISSING,
        "size": _majority(sizes) or MISSING,
        "line_spacing": _majority(spacings) or MISSING,
    }


def _cm(value: Any) -> str | None:
    if value is None:
        return None
    return f"{round(float(value) * 2.54 / 72, 2)}cm"


def build_format_summary(document: Document) -> dict[str, Any]:
    paragraphs = document.paragraphs
    body = [item for item in paragraphs if item.get("structure", "body") == "body" and not (item.get("heading") or {}).get("level")]
    title = [item for item in paragraphs if (item.get("heading") or {}).get("level") == 1]
    abstract = [item for item in paragraphs if item.get("structure") == "abstract" and item.get("structure_role") != "title"]
    cover = [item for item in paragraphs if item.get("structure") == "cover" and item.get("structure_role") == "title"]
    structured: dict[str, Any] = {}
    if body:
        structured["body"] = _group(body)
    if title:
        structured["title"] = _group(title)
    if abstract:
        structured["abstract"] = _group(abstract)
    if cover:
        structured["cover"] = _group(cover)
    if document.sections:
        margins = document.sections[0].get("margins_pt") or {}
        structured.setdefault("page", {})["margin"] = " ".join(
            f"{side}={_cm(value)}" for side, value in margins.items() if value is not None
        ) or MISSING
    if document.pages:
        page = document.pages[0]
        count = len(document.pages)
        numbers = [item.get("page_number") for item in document.pages if item.get("page_number") is not None]
        structured.setdefault("page", {})["count"] = count
        label = f"{page.get('position') or 'none'}/{page.get('number_format') or 'default'}\uff0c\u5171{count}\u9875"
        if numbers:
            label += f"\uff08{numbers[0]}-{numbers[-1]}\uff09"
        structured["page"]["page_number"] = label

    labels = {
        "body": "\u6b63\u6587\u683c\u5f0f",
        "title": "\u6807\u9898\u683c\u5f0f",
        "abstract": "\u6458\u8981\u683c\u5f0f",
        "cover": "\u5c01\u9762\u9898\u76ee\u683c\u5f0f",
        "page": "\u9875\u9762\u683c\u5f0f",
    }
    lines: list[str] = []
    for key in ("body", "title", "abstract", "cover", "page"):
        block = structured.get(key)
        if not block:
            continue
        lines.append(f"{labels[key]}\uff1a")
        if key == "page":
            if block.get("margin"):
                lines.append(f"\u9875\u8fb9\u8ddd\uff1a{block['margin']}")
            if block.get("page_number"):
                lines.append(f"\u9875\u7801\uff1a{block['page_number']}")
        else:
            lines.append(f"\u5b57\u4f53\uff1a{block.get('font', MISSING)}")
            lines.append(f"\u5b57\u53f7\uff1a{block.get('size', MISSING)}")
            lines.append(f"\u884c\u8ddd\uff1a{block.get('line_spacing', MISSING)}")
        lines.append("")
    return {"structured": structured, "text": "\n".join(lines).strip()}
