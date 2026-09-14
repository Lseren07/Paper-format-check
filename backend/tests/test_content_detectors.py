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

def test_caption_position_requires_figure_caption_below_drawing() -> None:
    from backend.app.rules.detectors import detect_caption_position
    document = Document(document_id="D1", source_filename="x.docx", paragraphs=[
        {"paragraph_id": "p-0001", "text": "图1 标题", "structure": "figure_caption", "block_index": 0, "drawings": [], "heading": {"level": None}},
        {"paragraph_id": "p-0002", "text": "", "structure": "body", "block_index": 1, "drawings": [{"kind": "drawing"}], "heading": {"level": None}},
    ])
    rule = CheckRule(id="figure-pos", type="caption_position", target="figure_caption", expected={"position": "below"})
    errors = detect_caption_position(document, rule)
    assert errors[0].type == "caption_position_error"
    assert errors[0].expected == "below"


def test_caption_position_accepts_table_caption_above_table() -> None:
    from backend.app.rules.detectors import detect_caption_position
    document = Document(
        document_id="D1", source_filename="x.docx",
        paragraphs=[{"paragraph_id": "p-0001", "text": "表1 结果", "structure": "table_caption", "block_index": 0, "heading": {"level": None}}],
        tables=[{"table_index": 0, "rows": 1, "columns": 2, "block_index": 1}],
    )
    rule = CheckRule(id="table-pos", type="caption_position", target="table_caption", expected={"position": "above"})
    assert detect_caption_position(document, rule) == []


def test_page_number_detector_reports_missing_page_field() -> None:
    from backend.app.rules.detectors import detect_page_number
    document = Document(document_id="D1", source_filename="x.docx", pages=[{"section_index": 0, "number_format": None, "position": "none", "fields": []}])
    rule = CheckRule(id="page-number", type="page_number", expected={"position": "footer"})
    errors = detect_page_number(document, rule)
    assert errors[0].type == "page_number_error"
    assert errors[0].current == "none"


def test_page_number_detector_accepts_matching_footer_field() -> None:
    from backend.app.rules.detectors import detect_page_number
    document = Document(document_id="D1", source_filename="x.docx", pages=[{
        "section_index": 0, "number_format": "upperRoman", "position": "footer",
        "fields": [{"instruction": "PAGE", "part": "footer"}],
    }])
    rule = CheckRule(id="page-number", type="page_number", expected={"position": "footer", "number_format": "upperRoman"})
    assert detect_page_number(document, rule) == []



def test_page_number_detector_reports_discontinuous_rendered_pages() -> None:
    from backend.app.rules.detectors import detect_page_number
    document = Document(document_id='D1', source_filename='x.docx', pages=[
        {'section_index': 0, 'page_index': 0, 'page_number': 1, 'position': 'footer', 'fields': [{'instruction': 'PAGE', 'part': 'footer'}]},
        {'section_index': 0, 'page_index': 1, 'page_number': 3, 'position': 'footer', 'fields': [{'instruction': 'PAGE', 'part': 'footer'}]},
    ])
    rule = CheckRule(id='page-number', type='page_number', expected={'position': 'footer', 'continuous': True})
    errors = detect_page_number(document, rule)
    assert errors[0].type == 'page_number_error'
    assert '3' in errors[0].current
