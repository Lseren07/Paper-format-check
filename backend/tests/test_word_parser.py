from io import BytesIO
from zipfile import ZIP_DEFLATED, ZipFile
from docx import Document as BuildDocument
from docx.shared import Inches
from docx.enum.style import WD_STYLE_TYPE
from docx.oxml.ns import qn
from PIL import Image

import pytest

from backend.app.parser.errors import DocumentParseError
from backend.app.parser.word_parser import parse_docx
from backend.app.parser.numbering import numbering_label
from backend.app.parser.styles import parse_styles, parse_theme, resolve_style
from xml.etree import ElementTree as ET


def make_docx_xml(document_xml: str = "<w:document xmlns:w='http://schemas.openxmlformats.org/wordprocessingml/2006/main'><w:body><w:p><w:r><w:t>Hello</w:t></w:r></w:p></w:body></w:document>") -> bytes:
    stream = BytesIO()
    with ZipFile(stream, "w", ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml", "<Types xmlns='http://schemas.openxmlformats.org/package/2006/content-types'><Default Extension='rels' ContentType='application/vnd.openxmlformats-package.relationships+xml'/><Default Extension='xml' ContentType='application/xml'/><Override PartName='/word/document.xml' ContentType='application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml'/></Types>")
        archive.writestr("_rels/.rels", "<Relationships xmlns='http://schemas.openxmlformats.org/package/2006/relationships'><Relationship Id='rId1' Type='http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument' Target='word/document.xml'/></Relationships>")
        archive.writestr("word/document.xml", document_xml)
    return stream.getvalue()


def test_parse_docx_extracts_paragraph_text_and_run() -> None:
    document = parse_docx(BytesIO(make_docx_xml()), source_filename="thesis.docx", document_id="DOC001")
    assert document.document_id == "DOC001"
    assert document.source_filename == "thesis.docx"
    assert document.paragraphs[0]["text"] == "Hello"
    assert document.paragraphs[0]["runs"][0]["text"] == "Hello"


def test_parse_docx_rejects_missing_document_xml() -> None:
    stream = BytesIO()
    with ZipFile(stream, "w", ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml", "<Types />")
    with pytest.raises(DocumentParseError):
        parse_docx(BytesIO(stream.getvalue()))


def test_parse_docx_extracts_headers_and_footers() -> None:
    source = BuildDocument()
    source.add_paragraph("正文")
    source.sections[0].header.paragraphs[0].text = "页眉"
    source.sections[0].footer.paragraphs[0].text = "页脚"
    stream = BytesIO(); source.save(stream)
    parsed = parse_docx(BytesIO(stream.getvalue()))
    assert parsed.headers[0]["text"] == "页眉"
    assert parsed.footers[0]["text"] == "页脚"


def test_parse_numbered_heading_exposes_numbering_metadata() -> None:
    source = BuildDocument()
    p = source.add_paragraph("第一节")
    p.style = "Heading 1"
    stream = BytesIO(); source.save(stream)
    parsed = parse_docx(BytesIO(stream.getvalue()))
    assert parsed.paragraphs[0]["heading"]["level"] == 1


def test_numbering_label_expands_decimal_multilevel_template() -> None:
    assert numbering_label("%1.%2", [2, 3], "decimal") == "2.3"
    assert numbering_label("%1", [4], "upperRoman") == "IV"
    assert numbering_label("%1", [3], "lowerLetter") == "c"


def test_styles_resolve_doc_defaults_and_theme_font() -> None:
    xml = """<w:styles xmlns:w='http://schemas.openxmlformats.org/wordprocessingml/2006/main'><w:docDefaults><w:rPrDefault><w:rPr><w:rFonts w:eastAsia='宋体'/><w:sz w:val='24'/></w:rPr></w:rPrDefault></w:docDefaults><w:style w:styleId='Body'><w:name w:val='正文'/><w:rPr><w:rFonts w:ascii='Arial'/></w:rPr></w:style></w:styles>"""
    parsed = parse_styles(ET.fromstring(xml))
    assert parsed["defaults"]["font"]["eastAsia"] == "宋体"
    assert resolve_style("Body", parsed)["font"]["ascii"] == "Arial"


def test_theme_font_resolves_minor_east_asia_reference() -> None:
    theme = parse_theme(ET.fromstring("""<a:theme xmlns:a='http://schemas.openxmlformats.org/drawingml/2006/main'><a:themeElements><a:fontScheme><a:minorFont><a:latin typeface='Calibri'/><a:ea typeface='等线'/></a:minorFont></a:fontScheme></a:themeElements></a:theme>"""))
    styles = {"styles": {"Body": {"based_on": None, "rpr": {"font_theme": {"eastAsia": "minorEastAsia"}}}}, "defaults": {}, "theme": theme}
    assert resolve_style("Body", styles)["font"]["eastAsia"] == "等线"


def test_toc_style_is_recorded_in_metadata() -> None:
    source = BuildDocument(); source.styles.add_style("TOC 1", WD_STYLE_TYPE.PARAGRAPH); p = source.add_paragraph("第一章 绪论"); p.style = "TOC 1"
    stream = BytesIO(); source.save(stream)
    parsed = parse_docx(BytesIO(stream.getvalue()))
    assert parsed.metadata["toc_paragraphs"][0]["text"] == "第一章 绪论"


def test_parse_docx_keeps_drawing_relationship_metadata() -> None:
    source = BuildDocument(); source.add_paragraph("图示")
    image = BytesIO(); Image.new("RGB", (20, 10), "red").save(image, format="PNG"); image.seek(0)
    source.paragraphs[0].add_run().add_picture(image, width=Inches(1))
    stream = BytesIO(); source.save(stream)
    parsed = parse_docx(BytesIO(stream.getvalue()))
    drawing = parsed.paragraphs[0]["drawings"][0]
    assert drawing["target"].endswith(".png")
    assert drawing["width_emu"] > 0
    assert drawing["height_emu"] > 0


def test_parse_docx_extracts_page_margins_and_table_cell_paragraphs() -> None:
    source = BuildDocument()
    source.sections[0].top_margin = Inches(1)
    cell = source.add_table(rows=1, cols=1).cell(0, 0)
    cell.paragraphs[0].text = "表格正文"
    cell.paragraphs[0].runs[0].font.name = "黑体"
    ind = cell.paragraphs[0]._p.get_or_add_pPr().get_or_add_ind()
    ind.set(qn("w:firstLineChars"), "200")
    stream = BytesIO(); source.save(stream)
    parsed = parse_docx(BytesIO(stream.getvalue()))
    table_paragraph = next(paragraph for paragraph in parsed.paragraphs if paragraph["location"]["part"] == "table")
    assert parsed.sections[0]["margins_pt"]["top"] == 72
    assert table_paragraph["text"] == "表格正文"
    assert table_paragraph["format"]["first_line_indent_chars"] == 2
