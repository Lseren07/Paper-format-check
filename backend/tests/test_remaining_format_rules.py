from backend.app.models.contracts import Document
from backend.app.rules.contracts import CheckRule
from backend.app.rules.detectors import detect_alignment, detect_font, detect_toc_consistency
from backend.app.rules.targets import paragraph_targets


def paragraph(*, paragraph_id="p-0001", text="", heading=None, style="Normal", alignment=None, runs=None):
    return {
        "paragraph_id": paragraph_id,
        "text": text,
        "style": {"name": style},
        "heading": {"level": heading},
        "structure": "body",
        "location": {"part": "document"},
        "format": {"alignment": alignment},
        "runs": runs or [{
            "text": text,
            "font": {"effective": "宋体", "ascii": "宋体", "east_asia": "宋体"},
            "size_pt": 12,
            "bold": False,
        }],
    }


def document(paragraphs, toc=None):
    return Document(
        document_id="D1",
        source_filename="x.docx",
        paragraphs=paragraphs,
        metadata={"toc_paragraphs": toc or []},
    )


def test_plain_numbered_second_level_titles_use_title_target_not_body_target():
    doc = document([paragraph(paragraph_id="p-0046", text="1.1 研究背景", alignment="center")])
    targets = paragraph_targets(doc)["p-0046"]

    assert "title2" in targets
    assert "body" not in targets
    errors = detect_alignment(doc, CheckRule(
        id="title2-alignment", type="alignment", target="title2", expected={"alignment": "left"}
    ))
    assert errors[0].current == "center"
    assert errors[0].expected == "left"


def test_mixed_run_uses_times_for_latin_and_song_for_chinese():
    text = "PostgreSQL 和 MySQL 数据库的性能基准测试"
    doc = document([paragraph(
        text=text,
        runs=[{
            "text": text,
            "font": {"effective": "宋体", "ascii": "Times New Roman", "east_asia": "宋体"},
            "size_pt": 12,
            "bold": False,
        }],
    )])

    assert detect_font(doc, CheckRule(
        id="body-font", type="font", target="body", expected={"font": "宋体"}
    )) == []


def test_mixed_run_reports_wrong_latin_font_separately():
    text = "PostgreSQL 和 MySQL 数据库的性能基准测试"
    doc = document([paragraph(
        text=text,
        runs=[{
            "text": text,
            "font": {"effective": "宋体", "ascii": "宋体", "east_asia": "宋体"},
            "size_pt": 12,
            "bold": False,
        }],
    )])
    errors = detect_font(doc, CheckRule(
        id="body-font", type="font", target="body", expected={"font": "宋体"}
    ))

    assert len(errors) == 1
    assert errors[0].location.endswith(":latin")
    assert errors[0].current == "宋体"
    assert errors[0].expected == "Times New Roman"


def test_toc_consistency_compares_numbered_body_title_text_and_ignores_page_number():
    doc = document(
        [paragraph(paragraph_id="p-0001", text="1.2 国内外研究问题", heading=2, style="Heading 2")],
        toc=[{"text": "1.2 国内外研究方向\t12", "level": 2}],
    )
    errors = detect_toc_consistency(doc, CheckRule(
        id="toc-consistency", type="toc_consistency", expected={}
    ))

    assert len(errors) == 1
    assert "国内外研究问题" in errors[0].expected
    assert "国内外研究方向" in errors[0].current


def test_toc_consistency_accepts_matching_numbered_body_title():
    doc = document(
        [paragraph(paragraph_id="p-0001", text="1.2 国内外研究问题", heading=2, style="Heading 2")],
        toc=[{"text": "1.2 国内外研究问题\t12", "level": 2}],
    )

    assert detect_toc_consistency(doc, CheckRule(
        id="toc-consistency", type="toc_consistency", expected={}
    )) == []
