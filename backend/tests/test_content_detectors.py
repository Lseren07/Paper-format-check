from backend.app.models.contracts import Document
from backend.app.rules.contracts import CheckRule
from backend.app.rules.detectors import detect_reference_baseline, detect_table_figure_format


def test_table_figure_detector_reports_invalid_table_shape() -> None:
    document = Document(document_id="D1", source_filename="x.docx", tables=[{"table_index": 0, "rows": 1, "columns": 4}])
    rule = CheckRule(id="table-shape", type="table_figure_format", expected={"columns": 3})
    errors = detect_table_figure_format(document, rule)
    assert errors[0].current == "1x4"
    assert errors[0].expected == "columns=3"


def test_reference_detector_reports_numbering_gap() -> None:
    document = Document(document_id="D1", source_filename="x.docx", paragraphs=[
        {"paragraph_id": "p-0001", "text": "[1] A", "style": {"name": "References"}},
        {"paragraph_id": "p-0002", "text": "[3] C", "style": {"name": "References"}},
    ])
    errors = detect_reference_baseline(document, CheckRule(id="refs", type="reference_baseline", expected={}))
    assert errors[0].current == "3"
    assert errors[0].expected == "2"


def test_reference_detector_recognizes_chinese_reference_style() -> None:
    document = Document(document_id="D1", source_filename="x.docx", paragraphs=[
        {"paragraph_id": "p-0001", "text": "[1] A", "style": {"name": "参考文献"}},
        {"paragraph_id": "p-0002", "text": "[3] C", "style": {"name": "参考文献"}},
    ])
    errors = detect_reference_baseline(document, CheckRule(id="refs", type="reference_baseline", expected={}))
    assert errors[0].current == "3"


def test_reference_detector_uses_reference_heading_to_include_normal_style_entries() -> None:
    document = Document(document_id="D1", source_filename="x.docx", paragraphs=[
        {"paragraph_id": "p-0001", "text": "[4] 正文引用", "style": {"name": "Normal"}},
        {"paragraph_id": "p-0002", "text": "参考文献", "style": {"name": "Heading 1"}},
        {"paragraph_id": "p-0003", "text": "[1] A", "style": {"name": "Normal"}},
        {"paragraph_id": "p-0004", "text": "[3] C", "style": {"name": "Normal"}},
    ])
    errors = detect_reference_baseline(document, CheckRule(id="refs", type="reference_baseline", expected={}))
    assert len(errors) == 1
    assert errors[0].location == "p-0004"
