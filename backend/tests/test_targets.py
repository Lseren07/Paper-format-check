from backend.app.models.contracts import Document
from backend.app.parser.structure import annotate_structure
from backend.app.rules.contracts import CheckRule, RuleSet
from backend.app.rules.detectors import detect_font, detect_paragraph_indent, detect_size
from backend.app.rules.service import check_document
from backend.app.rules.targets import paragraph_targets


def _paragraph(
    paragraph_id: str,
    text: str,
    *,
    heading=None,
    font="Times New Roman",
    size_pt=12,
    indent_pt=12,
    style="Normal",
    structure=None,
    role=None,
):
    paragraph = {
        "paragraph_id": paragraph_id,
        "text": text,
        "style": {"name": style},
        "heading": {"level": heading},
        "format": {"first_line_indent_pt": indent_pt},
        "runs": [{"text": text, "font": {"effective": font}, "size_pt": size_pt, "bold": None}],
        "location": {"part": "document"},
    }
    if structure is not None:
        paragraph["structure"] = structure
        paragraph["structure_role"] = role
    return paragraph


def _document(paragraphs: list[dict]) -> Document:
    return Document(document_id="D1", source_filename="x.docx", paragraphs=paragraphs)


def test_english_abstract_keeps_one_char_indent_after_inner_heading() -> None:
    paragraphs = [
        _paragraph("p-0001", "ABSTRACT", heading=None, indent_pt=0, size_pt=15),
        _paragraph("p-0002", "A Study on Format Checking", heading=2, indent_pt=0, size_pt=14),
        _paragraph("p-0003", "This paper studies the detector.", heading=None, indent_pt=12, size_pt=12),
        _paragraph("p-0004", "第一章 绪论", heading=1, font="黑体", indent_pt=0, size_pt=15),
        _paragraph("p-0005", "这是中文正文。", heading=None, font="宋体", indent_pt=24, size_pt=12),
    ]
    annotate_structure(paragraphs)
    document = _document(paragraphs)
    assigned = paragraph_targets(document)
    assert assigned["p-0001"] == {"abstract-en-title"}
    assert "body" not in assigned["p-0002"]
    assert "title2" not in assigned["p-0002"]
    assert assigned["p-0003"] == {"abstract-en-body"}
    assert paragraphs[2]["structure"] == "abstract_en"
    assert "title1" in assigned["p-0004"]
    assert "body" in assigned["p-0005"]

    body_indent = CheckRule(
        id="body-first-line-indent",
        type="paragraph_indent",
        target="body",
        expected={"first_line_indent": "2字符"},
    )
    en_indent = CheckRule(
        id="abstract-en-first-line-indent",
        type="paragraph_indent",
        target="abstract-en-body",
        expected={"first_line_indent": "1字符"},
    )
    assert detect_paragraph_indent(document, body_indent) == []
    assert detect_paragraph_indent(document, en_indent) == []


def test_foreign_materials_are_not_checked_as_chinese_body() -> None:
    paragraphs = [
        _paragraph("p-0001", "参考文献", heading=1, font="黑体", indent_pt=0, size_pt=15),
        _paragraph("p-0002", "[1] 张三. 测试文献.", heading=None, font="宋体", indent_pt=0, size_pt=10.5),
        _paragraph("p-0003", "外文资料原文", heading=1, font="黑体", indent_pt=0, size_pt=15),
        _paragraph("p-0004", "1 Introduction", heading=2, indent_pt=0, size_pt=12),
        _paragraph("p-0005", "The original English text.", heading=None, indent_pt=12, size_pt=12),
        _paragraph("p-0006", "译文", heading=1, font="黑体", indent_pt=0, size_pt=15),
        _paragraph("p-0007", "This is the translated text.", heading=None, indent_pt=12, size_pt=12),
    ]
    annotate_structure(paragraphs)
    document = _document(paragraphs)
    assigned = paragraph_targets(document)
    assert assigned["p-0003"] == {"foreign-title"}
    assert "body" not in assigned["p-0004"]
    assert "title2" not in assigned["p-0004"]
    assert assigned["p-0005"] == {"foreign-body"}
    assert assigned["p-0006"] == {"foreign-title"}
    assert assigned["p-0007"] == {"foreign-body"}

    rules = RuleSet(schema_version="1.0", name="t", checks=[
        CheckRule(id="body-font", type="font", target="body", expected={"font": "宋体"}),
        CheckRule(id="body-size", type="size", target="body", expected={"size": "小四"}),
        CheckRule(id="body-first-line-indent", type="paragraph_indent", target="body", expected={"first_line_indent": "2字符"}),
        CheckRule(id="foreign-title-font", type="font", target="foreign-title", expected={"font": "黑体"}),
        CheckRule(id="foreign-title-size", type="size", target="foreign-title", expected={"size": "小三"}),
        CheckRule(id="foreign-body-font", type="font", target="foreign-body", expected={"font": "Times New Roman"}),
        CheckRule(id="foreign-body-first-line-indent", type="paragraph_indent", target="foreign-body", expected={"first_line_indent": "1字符"}),
    ])
    errors = check_document(document, rules)
    assert [error.rule_id for error in errors] == []
    assert detect_font(document, rules.checks[0]) == []
    assert detect_size(document, rules.checks[1]) == []


def test_cover_title_uses_title_line_not_school_name() -> None:
    paragraphs = [
        {
            "paragraph_id": "p-0001",
            "text": "电子科技大学成都学院",
            "style": {"name": "华文行楷"},
            "runs": [{"text": "电子科技大学成都学院", "size_pt": 36}],
            "location": {"part": "document"},
        },
        {
            "paragraph_id": "p-0002",
            "text": "题目：面向格式检测的论文题目",
            "style": {"name": "论文题目"},
            "runs": [{"text": "题目：面向格式检测的论文题目", "size_pt": 16}],
            "location": {"part": "document"},
        },
        {
            "paragraph_id": "p-0003",
            "text": "摘要",
            "style": {"name": "Normal"},
            "runs": [{"text": "摘要"}],
            "location": {"part": "document"},
        },
    ]
    annotate_structure(paragraphs)
    assert paragraphs[0]["structure"] == "cover"
    assert paragraphs[1]["structure"] == "cover"
    assert paragraphs[0].get("structure_role") != "title"
    assert paragraphs[1]["structure_role"] == "title"
    document = _document(paragraphs)
    assigned = paragraph_targets(document)
    assert "cover_title" in assigned["p-0002"]
    assert "cover_title" not in assigned["p-0001"]
