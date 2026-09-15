"""Extract page boundaries from Word XML, then attach PAGE-field settings.

Word does not store a finished page list in python-docx. The closest truthful
signal is w:lastRenderedPageBreak, written when Word last paginated the file.
Explicit page breaks and section starts are also hard boundaries. Files without
those markers fall back to a height estimate so pages is not just one item per
section.
"""

from __future__ import annotations

import re
from typing import Any
from xml.etree import ElementTree as ET

from docx.oxml.ns import qn

W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"


def extract_pages(docx, paragraphs: list[dict[str, Any]] | None = None, tables: list[dict[str, Any]] | None = None) -> list[dict[str, Any]]:
    section_settings = [_section_settings(index, section) for index, section in enumerate(docx.sections)]
    paragraphs = paragraphs or []
    tables = tables or []
    body_paras = [item for item in paragraphs if (item.get("location") or {}).get("part", "document") == "document"]
    pages: list[dict[str, Any]] = []
    has_rendered = False
    current_section = 0
    pending_new_page = False
    pending_new_section = False

    def settings(section_index: int) -> dict[str, Any]:
        if 0 <= section_index < len(section_settings):
            return section_settings[section_index]
        return section_settings[-1] if section_settings else {"section_index": 0, "number_format": None, "start": None, "position": "none", "fields": []}

    def start_page(section_index: int, source: str, previous_number: int | None = None, new_section: bool = False) -> dict[str, Any]:
        section = settings(section_index)
        if new_section and section.get("start") is not None:
            number = int(section["start"])
        elif previous_number is None:
            number = int(section["start"]) if section.get("start") is not None else 1
        else:
            number = previous_number + 1
        page = {
            "page_index": len(pages),
            "page_number": number,
            "section_index": section_index,
            "number_format": section.get("number_format"),
            "start": section.get("start"),
            "position": section.get("position"),
            "fields": list(section.get("fields") or []),
            "paragraph_ids": [],
            "source": source,
        }
        pages.append(page)
        return page

    current = start_page(0, "section_settings") if section_settings or body_paras else None
    body_idx = 0
    table_idx = 0
    for child in docx.element.body.iterchildren():
        if current is None:
            current = start_page(current_section, "section_settings")
        if child.tag == qn("w:sectPr"):
            continue
        before, after, rendered = _page_breaks(child)
        has_rendered = has_rendered or rendered
        source = "last_rendered" if rendered else ("explicit_break" if (before or after) else "section_settings")
        if (before or pending_new_page) and current["paragraph_ids"]:
            current = start_page(current_section, source, current["page_number"], new_section=pending_new_section)
            pending_new_page = False
            pending_new_section = False
        elif pending_new_section and not current["paragraph_ids"]:
            current["section_index"] = current_section
            section = settings(current_section)
            current["number_format"] = section.get("number_format")
            current["start"] = section.get("start")
            current["position"] = section.get("position")
            current["fields"] = list(section.get("fields") or [])
            if section.get("start") is not None:
                current["page_number"] = int(section["start"])
            pending_new_section = False
        if child.tag == qn("w:p"):
            if body_idx < len(body_paras):
                current["paragraph_ids"].append(body_paras[body_idx]["paragraph_id"])
                if source != "section_settings":
                    current["source"] = source
                body_idx += 1
            sect_pr = child.find(qn("w:sectPr"))
            if sect_pr is not None and current_section + 1 < len(section_settings):
                current_section += 1
                sect_type = sect_pr.find(qn("w:type"))
                start_type = sect_type.get(qn("w:val")) if sect_type is not None else "nextPage"
                if start_type != "continuous":
                    pending_new_page = True
                    pending_new_section = True
        elif child.tag == qn("w:tbl"):
            if table_idx < len(tables):
                for paragraph in paragraphs:
                    location = paragraph.get("location") or {}
                    if location.get("part") == "table" and location.get("table_index") == table_idx:
                        current["paragraph_ids"].append(paragraph["paragraph_id"])
                table_idx += 1
        if after:
            pending_new_page = True
            current["source"] = "last_rendered" if rendered else "explicit_break"
    if has_rendered:
        for page in pages:
            page["source"] = "last_rendered"
    elif pages:
        pages = _estimate_additional_splits(docx, pages, paragraphs)
    _assign_paragraph_pages(paragraphs, pages)
    if pages:
        return pages
    return [{
        "page_index": index,
        "page_number": item.get("start") or 1,
        "paragraph_ids": [],
        "source": "section_settings",
        **item,
    } for index, item in enumerate(section_settings)]


def _section_settings(index: int, section) -> dict[str, Any]:
    sect_pr = section._sectPr
    pg_num = sect_pr.find(qn("w:pgNumType")) if sect_pr is not None else None
    number_format = pg_num.get(qn("w:fmt")) if pg_num is not None else None
    start = pg_num.get(qn("w:start")) if pg_num is not None else None
    fields: list[dict[str, str]] = []
    for part, obj in (("header", section.header), ("footer", section.footer)):
        fields.extend(_part_fields(obj.paragraphs, part))
    page_fields = [field for field in fields if re.search(r"PAGE", field["instruction"], re.I)]
    footer_hit = any(field["part"] == "footer" for field in page_fields)
    header_hit = any(field["part"] == "header" for field in page_fields)
    if footer_hit and header_hit:
        position = "header_footer"
    elif footer_hit:
        position = "footer"
    elif header_hit:
        position = "header"
    else:
        position = "none"
    return {
        "section_index": index,
        "number_format": number_format,
        "start": int(start) if start else None,
        "position": position,
        "fields": fields,
    }


def _part_fields(paragraphs, part: str) -> list[dict[str, str]]:
    fields = []
    for paragraph in paragraphs:
        root = ET.fromstring(paragraph._p.xml)
        for node in root.iter(f"{W}instrText"):
            instruction = "".join(node.itertext()).strip()
            if instruction:
                fields.append({"instruction": instruction, "part": part})
    return fields


def _page_breaks(element) -> tuple[int, int, bool]:
    before = 0
    after = 0
    seen_text = False
    rendered = False
    for node in element.iter():
        if node.tag == qn("w:t") and (node.text or "").strip():
            seen_text = True
        elif node.tag == qn("w:lastRenderedPageBreak"):
            rendered = True
            if seen_text:
                after += 1
            else:
                before += 1
        elif node.tag == qn("w:br") and node.get(qn("w:type")) == "page":
            if seen_text:
                after += 1
            else:
                before += 1
    return before, after, rendered


def _estimate_additional_splits(docx, pages: list[dict[str, Any]], paragraphs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not docx.sections:
        return pages
    section = docx.sections[0]
    page_height = section.page_height.pt if section.page_height else 792
    margins = (section.top_margin.pt if section.top_margin else 72) + (section.bottom_margin.pt if section.bottom_margin else 72)
    usable_height = max(200.0, page_height - margins - 72)
    page_width = section.page_width.pt if section.page_width else 612
    usable_width = max(100.0, page_width - (section.left_margin.pt if section.left_margin else 72) - (section.right_margin.pt if section.right_margin else 72))
    by_id = {item["paragraph_id"]: item for item in paragraphs if item.get("paragraph_id")}
    split: list[dict[str, Any]] = []
    for page in pages:
        current = None
        used = 0.0
        for paragraph_id in page.get("paragraph_ids") or []:
            height = _paragraph_height(by_id.get(paragraph_id), usable_width)
            if current is None:
                current = {**page, "page_index": len(split), "paragraph_ids": [paragraph_id]}
                split.append(current)
                used = height
                continue
            if used + height > usable_height:
                current = {
                    **page,
                    "page_index": len(split),
                    "page_number": current["page_number"] + 1,
                    "paragraph_ids": [paragraph_id],
                    "source": "estimated",
                }
                split.append(current)
                used = height
            else:
                current["paragraph_ids"].append(paragraph_id)
                used += height
        if current is None:
            split.append({**page, "page_index": len(split)})
    return split or pages


def _paragraph_height(paragraph: dict[str, Any] | None, usable_width: float) -> float:
    if not paragraph:
        return 18.0
    size = next((float(run.get("size_pt")) for run in paragraph.get("runs") or [] if run.get("size_pt")), 12.0)
    spacing = (paragraph.get("format") or {}).get("line_spacing") or 1.5
    try:
        spacing_value = float(spacing)
    except (TypeError, ValueError):
        spacing_value = 1.5
    line_height = size * spacing_value if spacing_value <= 3 else spacing_value
    extra = float((paragraph.get("format") or {}).get("space_before_pt") or 0) + float((paragraph.get("format") or {}).get("space_after_pt") or 0)
    if paragraph.get("drawings"):
        extra += 120
    text = (paragraph.get("text") or "").strip()
    chars_per_line = max(1, int(usable_width / max(size, 1)))
    lines = max(1, (len(text) + chars_per_line - 1) // chars_per_line) if text else 1
    return lines * line_height + extra


def _assign_paragraph_pages(paragraphs: list[dict[str, Any]], pages: list[dict[str, Any]]) -> None:
    by_id = {item["paragraph_id"]: item for item in paragraphs if item.get("paragraph_id")}
    for page in pages:
        for paragraph_id in page.get("paragraph_ids") or []:
            paragraph = by_id.get(paragraph_id)
            if paragraph is None:
                continue
            paragraph["page_index"] = page["page_index"]
            paragraph["page_number"] = page["page_number"]
