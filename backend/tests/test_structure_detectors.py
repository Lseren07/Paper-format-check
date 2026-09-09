from backend.app.models.contracts import Document
from backend.app.rules.contracts import CheckRule
from backend.app.rules.detectors import detect_heading_numbering, detect_toc_consistency


def document_with_headings(headings: list[tuple[str, int]], toc: list[tuple[str, int]] | None = None) -> Document:
    paragraphs = [{
        "paragraph_id": f"p-{index:04d}", "text": text, "heading": {"level": level},
        "numbering": {"label": text.split()[0]}, "style": {"name": f"Heading {level}"},
    } for index, (text, level) in enumerate(headings, start=1)]
    return Document(document_id="D1", source_filename="x.docx", paragraphs=paragraphs, metadata={
        "toc_paragraphs": [{"text": text, "level": level} for text, level in (toc or [])],
    })


def test_heading_numbering_reports_gap() -> None:
    document = document_with_headings([("1", 1), ("3", 1)])
    errors = detect_heading_numbering(document, CheckRule(id="heading", type="heading_numbering", expected={}))
    assert errors[0].type == "heading_numbering_error"
    assert errors[0].current == "3"
    assert errors[0].expected == "2"


def test_toc_consistency_reports_missing_heading() -> None:
    document = document_with_headings([("1 引言", 1), ("2 方法", 1)], toc=[("1 引言", 1)])
    errors = detect_toc_consistency(document, CheckRule(id="toc", type="toc_consistency", expected={}))
    assert errors[0].type == "toc_consistency_error"
    assert "2 方法" in errors[0].content


def test_toc_consistency_ignores_trailing_toc_page_number() -> None:
    document = document_with_headings([("1 引言", 1)], toc=[("1 引言\t1", 1)])
    assert detect_toc_consistency(document, CheckRule(id="toc", type="toc_consistency", expected={})) == []


def test_heading_numbering_supports_punctuated_and_multilevel_decimal_labels() -> None:
    document = document_with_headings([("1.", 1), ("1.1", 2), ("1.3", 2)])
    errors = detect_heading_numbering(document, CheckRule(id="heading", type="heading_numbering", expected={}))
    assert errors[0].current == "1.3"
    assert errors[0].expected == "1.2"
