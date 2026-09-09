"""将 DOCX 的基础文档结构转换为阶段0 Document 契约。"""

from io import BytesIO
from pathlib import Path
from typing import BinaryIO
from zipfile import BadZipFile, ZipFile
import uuid
import re
from xml.etree import ElementTree as ET

from docx import Document as DocxDocument

from ..models.contracts import Document
from .errors import DocumentParseError
from .styles import parse_styles, parse_theme, resolve_style
from .numbering import parse_numbering
from .numbering import numbering_label
from .relationships import parse_relationships


def _drawings(paragraph, relationships: dict[str, str]) -> list[dict]:
    """从 drawing XML 提取关系目标和 EMU 尺寸，供图表/图片规则使用。"""
    drawings = []
    root = ET.fromstring(paragraph._p.xml)
    for drawing in root.iter("{http://schemas.openxmlformats.org/wordprocessingml/2006/main}drawing"):
        extent = next(iter(drawing.iter("{http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing}extent")), None)
        blip = next(iter(drawing.iter("{http://schemas.openxmlformats.org/drawingml/2006/main}blip")), None)
        rid = blip.get("{http://schemas.openxmlformats.org/officeDocument/2006/relationships}embed") if blip is not None else None
        drawings.append({"kind": "drawing", "relationship_id": rid, "target": relationships.get(rid), "width_emu": int(extent.get("cx")) if extent is not None else None, "height_emu": int(extent.get("cy")) if extent is not None else None})
    return drawings


def _open_source(source: str | Path | BinaryIO) -> tuple[bytes, str | None]:
    """统一读取路径或文件对象；只保留字节，避免后续依赖文件句柄状态。"""
    if isinstance(source, (str, Path)):
        path = Path(source)
        try:
            return path.read_bytes(), path.name
        except OSError as exc:
            raise DocumentParseError("source_unreadable", "无法读取 DOCX 文件") from exc
    try:
        data = source.read()
        if hasattr(data, "__await__"):
            raise TypeError("异步文件对象不受解析核心支持")
        return data, None
    except (OSError, TypeError, AttributeError) as exc:
        raise DocumentParseError("source_unreadable", "无法读取 DOCX 文件") from exc


def parse_docx(
    source: str | Path | BinaryIO,
    *,
    document_id: str | None = None,
    source_filename: str | None = None,
) -> Document:
    """解析 DOCX 的段落和 runs，其他阶段字段先保持契约兼容的空集合。"""
    data, inferred_name = _open_source(source)
    try:
        with ZipFile(BytesIO(data)) as archive:
            if "word/document.xml" not in archive.namelist():
                raise DocumentParseError("missing_document_xml", "DOCX 缺少核心文档 XML")
            resources = {"styles": {}, "defaults": {}, "theme": {}, "numbering": {}, "relationships": {}}
            for name, parser, key in (("word/styles.xml", parse_styles, "styles"), ("word/numbering.xml", parse_numbering, "numbering"), ("word/theme/theme1.xml", parse_theme, "theme"), ("word/_rels/document.xml.rels", parse_relationships, "relationships")):
                if name in archive.namelist():
                    try:
                        parsed = parser(ET.fromstring(archive.read(name)))
                        if key == "styles": resources.update(parsed)
                        else: resources[key] = parsed
                    except ET.ParseError: resources[key] = {}
        docx = DocxDocument(BytesIO(data))
    except DocumentParseError:
        raise
    except (BadZipFile, KeyError, ValueError, OSError) as exc:
        raise DocumentParseError("invalid_docx", "文件不是有效的 DOCX 文档") from exc

    paragraphs: list[dict] = []
    counters: dict[int, list[int]] = {}
    for index, paragraph in enumerate(docx.paragraphs):
        style_id = paragraph.style.style_id
        effective = resolve_style(style_id, resources)
        runs = []
        for run in paragraph.runs:
            font = run.font
            runs.append({"text": run.text, "font": {"effective": font.name or (effective.get("font") or {}).get("eastAsia"), "ascii": (effective.get("font") or {}).get("ascii"), "east_asia": (effective.get("font") or {}).get("eastAsia")}, "size_pt": font.size.pt if font.size else effective.get("size_pt"), "bold": run.bold if run.bold is not None else effective.get("bold"), "italic": run.italic if run.italic is not None else effective.get("italic"), "underline": run.underline})
        pf = paragraph.paragraph_format
        alignment = paragraph.alignment.name.lower() if paragraph.alignment is not None else None
        numbering = None
        num_pr = paragraph._p.pPr.numPr if paragraph._p.pPr is not None else None
        if num_pr is not None:
            num_id_node = num_pr.numId; ilvl_node = num_pr.ilvl
            num_id = num_id_node.val if num_id_node is not None else None
            ilvl = ilvl_node.val if ilvl_node is not None else 0
            definition = resources.get("numbering", {}).get(str(num_id), {}).get(str(ilvl), {})
            current = counters.setdefault(int(num_id), []) if num_id is not None else []
            while len(current) <= ilvl: current.append(0)
            current[ilvl] += 1
            del current[ilvl + 1:]
            numbering = {"num_id": num_id, "ilvl": ilvl, **definition, "label": numbering_label(definition.get("level_text"), current, definition.get("format"))}
        heading_level = None
        match = re.search(r"(?:Heading|标题)\s*([1-9])", paragraph.style.name or "", re.I)
        if match: heading_level = int(match.group(1))
        paragraphs.append(
            {
                "paragraph_id": f"p-{index + 1:04d}",
                "index": index,
                "text": paragraph.text,
                "style": {"id": style_id, "name": paragraph.style.name, "based_on": []},
                "format": {"alignment": alignment, "line_spacing": pf.line_spacing, "space_before_pt": pf.space_before.pt if pf.space_before else None, "space_after_pt": pf.space_after.pt if pf.space_after else None, "first_line_indent_pt": pf.first_line_indent.pt if pf.first_line_indent else None, "left_indent_pt": pf.left_indent.pt if pf.left_indent else None, "right_indent_pt": pf.right_indent.pt if pf.right_indent else None},
                "runs": runs,
                "drawings": _drawings(paragraph, resources.get("relationships", {})),
                "heading": {"level": heading_level, "source": "style" if heading_level else None},
                "numbering": numbering,
                "location": {"part": "document", "section_index": 0, "table_index": None, "row_index": None, "column_index": None},
            }
        )

    tables = []
    for ti, table in enumerate(docx.tables):
        cells = []
        for ri, row in enumerate(table.rows):
            for ci, cell in enumerate(row.cells):
                cells.append({"row_index": ri, "column_index": ci, "text": cell.text, "paragraph_ids": [f"p-{i + 1:04d}" for i, _ in enumerate(cell.paragraphs)]})
        tables.append({"table_index": ti, "rows": len(table.rows), "columns": len(table.columns), "cells": cells})
    headers, footers = [], []
    for si, section in enumerate(docx.sections):
        for kind, obj, target in (("default", section.header, headers), ("default", section.footer, footers)):
            text = "\n".join(p.text for p in obj.paragraphs)
            fields = re.findall(r"w:instrText[^>]*>\s*([^<]+)", "".join(p._p.xml for p in obj.paragraphs))
            target.append({"section_index": si, "variant": kind, "text": text, "fields": [{"type": f.strip(), "display_text": text} for f in fields]})
    toc = [{"paragraph_id": p["paragraph_id"], "text": p["text"], "level": int(re.search(r"([1-9])", p["style"]["name"]).group(1)) if re.search(r"([1-9])", p["style"]["name"]) else None} for p in paragraphs if p["style"]["name"].lower().startswith("toc")]
    return Document(
        document_id=document_id or ("D" + uuid.uuid4().hex[:12]),
        source_filename=source_filename or inferred_name or "document.docx",
        metadata={"toc_paragraphs": toc},
        paragraphs=paragraphs,
        tables=tables,
        headers=headers,
        footers=footers,
        sections=[{"index": i, "orientation": section.orientation.name.lower(), "page_width_pt": section.page_width.pt if section.page_width else None, "page_height_pt": section.page_height.pt if section.page_height else None} for i, section in enumerate(docx.sections)],
    )
