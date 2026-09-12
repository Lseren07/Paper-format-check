from backend.app.models.contracts import Document, ErrorItem
from backend.app.services.location import format_location, relocate_errors


def paragraph(
    paragraph_id: str,
    text: str,
    *,
    level=None,
    numbering=None,
    part="document",
    table_index=None,
) -> dict:
    return {
        "paragraph_id": paragraph_id,
        "text": text,
        "heading": {"level": level},
        "numbering": {"label": numbering} if numbering is not None else None,
        "style": {"name": f"Heading {level}" if level else "Normal"},
        "location": {"part": part, "table_index": table_index},
        "format": {},
        "runs": [],
    }


def sample_document() -> Document:
    return Document(
        document_id="D1",
        source_filename="thesis.docx",
        paragraphs=[
            paragraph("p-0001", "系统设计", level=1, numbering="2"),
            paragraph("p-0002", "接口设计", level=2, numbering="2.1"),
            paragraph("p-0003", "随着人工智能技术的发展"),
            paragraph("p-0004", "表格内文字", part="table", table_index=0),
        ],
        tables=[{"table_index": 0, "rows": 1, "columns": 2}],
        sections=[{"index": 0, "margins_pt": {"top": 72}}],
    )


def test_run_location_uses_nearest_heading_and_chinese_chapter() -> None:
    assert format_location(sample_document(), "p-0003:run-0001") == "第二章 系统设计 2.1 接口设计"


def test_heading_paragraph_uses_its_own_title() -> None:
    assert format_location(sample_document(), "p-0001") == "第二章 系统设计"


def test_existing_chapter_text_is_not_prefixed_again() -> None:
    document = Document(document_id="D1", source_filename="x.docx", paragraphs=[
        paragraph("p-0001", "第二章 系统设计", level=1),
        paragraph("p-0002", "正文"),
    ])
    assert format_location(document, "p-0002:run-0001") == "第二章 系统设计"


def test_body_without_heading_falls_back_to_paragraph_ordinal() -> None:
    document = Document(document_id="D1", source_filename="x.docx", paragraphs=[
        paragraph("p-0001", "正文"),
    ])
    assert format_location(document, "p-0001:run-0001") == "第1段"


def test_table_cell_appends_table_label() -> None:
    assert format_location(sample_document(), "p-0004:run-0001") == "第二章 系统设计 2.1 接口设计 表格1"


def test_page_margin_and_toc_locations_are_readable() -> None:
    document = sample_document()
    assert format_location(document, "section-0:margin-top") == "上边距"
    assert format_location(document, "section-0:margin-left") == "左边距"
    assert format_location(document, "toc") == "目录"
    assert format_location(document, "table-0") == "表格1"


def test_unknown_location_is_kept() -> None:
    assert format_location(sample_document(), "unknown-loc") == "unknown-loc"


def test_relocate_errors_rewrites_display_location_but_keeps_error_id() -> None:
    document = sample_document()
    errors = relocate_errors(document, [
        ErrorItem(
            error_id="body-font:p-0003:run-0001",
            type="font_error",
            location="p-0003:run-0001",
            content="随着人工智能技术的发展",
            current="黑体",
            expected="宋体",
        )
    ])
    assert errors[0].location == "第二章 系统设计 2.1 接口设计"
    assert errors[0].error_id == "body-font:p-0003:run-0001"
